from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import folium
import datetime
import ee
import io
import base64
from PIL import Image
import numpy as np
import requests
from typing import Optional

# --- Initialize Earth Engine with Service Account ---
service_account = 'gemini-prod-api@gemini-prod-api-462407.iam.gserviceaccount.com'
key_file = 'gemini-prod-api-462407-b5f5e844fb8f.json'
credentials = ee.ServiceAccountCredentials(service_account, key_file)
ee.Initialize(credentials)

# --- FastAPI App ---
app = FastAPI(title="Sentinel-2 Crop Stress Detection API", version="1.0.0")

# --- Pydantic Models ---
class LocationRequest(BaseModel):
    latitude: float
    longitude: float
    buffer_distance: Optional[int] = 50  # meters
    days_back: Optional[int] = 90
    cloud_threshold: Optional[int] = 20
    image_width: Optional[int] = 800
    image_height: Optional[int] = 600

class NDVIResponse(BaseModel):
    status: str
    message: str
    location: dict
    ndvi_stats: Optional[dict] = None

# --- Helper Functions ---
def get_ndvi_image_url(lat: float, lon: float, buffer_distance: int, days_back: int, cloud_threshold: int) -> tuple:
    """Generate NDVI visualization and return image URL and stats"""
    try:
        # Create geometry
        point = ee.Geometry.Point([lon, lat])
        aoi = point.buffer(buffer_distance).bounds()
        
        # Date range
        end = datetime.date.today()
        start = end - datetime.timedelta(days=days_back)
        
        # Sentinel-2 Collection
        s2_collection = ee.ImageCollection("COPERNICUS/S2_HARMONIZED") \
            .filterBounds(aoi) \
            .filterDate(start.isoformat(), end.isoformat()) \
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_threshold))
        
        if s2_collection.size().getInfo() == 0:
            raise HTTPException(status_code=404, detail="No suitable Sentinel-2 images found for the specified criteria")
        
        s2 = s2_collection.median().clip(aoi)
        band_names = s2.bandNames().getInfo()
        
        if "B8" not in band_names or "B4" not in band_names:
            raise HTTPException(status_code=400, detail="Required bands (B4 and B8) not found in the image")
        
        # Calculate NDVI
        ndvi = s2.normalizedDifference(["B8", "B4"]).rename("NDVI")
        
        # Get NDVI statistics
        ndvi_stats = ndvi.reduceRegion(
            reducer=ee.Reducer.mean().combine(
                ee.Reducer.minMax().combine(
                    ee.Reducer.stdDev(), sharedInputs=True
                ), sharedInputs=True
            ),
            geometry=aoi,
            scale=10,
            maxPixels=1e9
        ).getInfo()
        
        # Visualization parameters
        vis_params = {
            "min": 0.0,
            "max": 1.0,
            "palette": ["red", "orange", "yellow", "green", "darkgreen"],
            "dimensions": "800x600",
            "format": "png"
        }
        
        # Get the image URL
        image_url = ndvi.getThumbURL(vis_params)
        
        return image_url, ndvi_stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing NDVI: {str(e)}")

def download_and_convert_image(image_url: str, width: int, height: int) -> io.BytesIO:
    """Download image from URL and convert to JPEG"""
    try:
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        # Open image with PIL
        img = Image.open(io.BytesIO(response.content))
        
        # Convert to RGB if necessary (for JPEG)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize if needed
        if img.size != (width, height):
            img = img.resize((width, height), Image.Resampling.LANCZOS)
        
        # Save as JPEG
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=95)
        output.seek(0)
        
        return output
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")

# --- API Endpoints ---
@app.get("/")
async def root():
    return {"message": "Sentinel-2 Crop Stress Detection API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "earth_engine": "initialized"}

@app.post("/generate-ndvi-image")
async def generate_ndvi_image(request: LocationRequest):
    """Generate NDVI heatmap image from coordinates"""
    try:
        # Validate coordinates
        if not (-90 <= request.latitude <= 90):
            raise HTTPException(status_code=400, detail="Invalid latitude. Must be between -90 and 90")
        if not (-180 <= request.longitude <= 180):
            raise HTTPException(status_code=400, detail="Invalid longitude. Must be between -180 and 180")
        
        # Get NDVI image URL and stats
        image_url, ndvi_stats = get_ndvi_image_url(
            request.latitude, 
            request.longitude, 
            request.buffer_distance,
            request.days_back,
            request.cloud_threshold
        )
        
        # Download and convert image
        jpeg_image = download_and_convert_image(image_url, request.image_width, request.image_height)
        
        # Return JPEG image
        return StreamingResponse(
            jpeg_image, 
            media_type="image/jpeg",
            headers={
                "Content-Disposition": f"inline; filename=ndvi_{request.latitude}_{request.longitude}.jpg",
                "X-NDVI-Stats": str(ndvi_stats)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/get-ndvi-stats")
async def get_ndvi_stats(request: LocationRequest):
    """Get NDVI statistics for a location (JSON response)"""
    try:
        # Validate coordinates
        if not (-90 <= request.latitude <= 90):
            raise HTTPException(status_code=400, detail="Invalid latitude. Must be between -90 and 90")
        if not (-180 <= request.longitude <= 180):
            raise HTTPException(status_code=400, detail="Invalid longitude. Must be between -180 and 180")
        
        # Get NDVI stats
        _, ndvi_stats = get_ndvi_image_url(
            request.latitude, 
            request.longitude, 
            request.buffer_distance,
            request.days_back,
            request.cloud_threshold
        )
        
        # Interpret NDVI values
        mean_ndvi = ndvi_stats.get('NDVI_mean', 0)
        health_status = "Unknown"
        
        if mean_ndvi < 0.2:
            health_status = "Severe Stress / Bare Soil"
        elif mean_ndvi < 0.4:
            health_status = "Stressed Vegetation"
        elif mean_ndvi < 0.6:
            health_status = "Moderate Health"
        elif mean_ndvi < 0.8:
            health_status = "Healthy"
        else:
            health_status = "Very Healthy"
        
        return NDVIResponse(
            status="success",
            message="NDVI analysis completed successfully",
            location={
                "latitude": request.latitude,
                "longitude": request.longitude,
                "buffer_distance_m": request.buffer_distance
            },
            ndvi_stats={
                "mean_ndvi": mean_ndvi,
                "min_ndvi": ndvi_stats.get('NDVI_min', 0),
                "max_ndvi": ndvi_stats.get('NDVI_max', 0),
                "std_ndvi": ndvi_stats.get('NDVI_stdDev', 0),
                "health_status": health_status,
                "analysis_period_days": request.days_back
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# --- Run the app ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
