# Crop Stress Detection API - Documentation

## Overview
This API provides NDVI (Normalized Difference Vegetation Index) analysis for crop health monitoring using Sentinel-2 satellite imagery through Google Earth Engine.

## Base URL
```
http://localhost:8000
```

## Authentication
Currently uses Google Earth Engine Service Account authentication (configured server-side).

---

## Endpoints

### 1. Health Check
**Endpoint:** `GET /health`

**Description:** Check if the API and Earth Engine are properly initialized.

**Response:**
```json
{
  "status": "healthy",
  "earth_engine": "initialized"
}
```

---

### 2. Analyze NDVI (Combined)
**Endpoint:** `POST /analyze-ndvi`

**Description:** Generates NDVI heatmap visualization and calculates vegetation health statistics for a specified location. Returns both the image (as base64) and statistical analysis in a single response.

#### Request Body
```json
{
  "latitude": 37.7749,
  "longitude": -122.4194,
  "buffer_distance": 50,
  "days_back": 90,
  "cloud_threshold": 20,
  "image_width": 800,
  "image_height": 600
}
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `latitude` | float | Yes | - | Latitude coordinate (-90 to 90) |
| `longitude` | float | Yes | - | Longitude coordinate (-180 to 180) |
| `buffer_distance` | int | No | 50 | Buffer radius around the point in meters |
| `days_back` | int | No | 90 | Number of days to look back for imagery |
| `cloud_threshold` | int | No | 20 | Maximum cloud coverage percentage (0-100) |
| `image_width` | int | No | 800 | Output image width in pixels |
| `image_height` | int | No | 600 | Output image height in pixels |

#### Response
```json
{
  "status": "success",
  "message": "NDVI analysis completed successfully",
  "location": {
    "latitude": 37.7749,
    "longitude": -122.4194,
    "buffer_distance_m": 50
  },
  "ndvi_stats": {
    "mean_ndvi": 0.65,
    "min_ndvi": 0.12,
    "max_ndvi": 0.89,
    "std_ndvi": 0.15,
    "health_status": "Healthy",
    "analysis_period_days": 90
  },
  "ndvi_image_base64": "/9j/4AAQSkZJRgABAQEAYABgAAD..."
}
```

#### NDVI Health Status Interpretation

| NDVI Range | Health Status |
|------------|---------------|
| < 0.2 | Severe Stress / Bare Soil |
| 0.2 - 0.4 | Stressed Vegetation |
| 0.4 - 0.6 | Moderate Health |
| 0.6 - 0.8 | Healthy |
| > 0.8 | Very Healthy |

#### Displaying the Image
To display the base64 image in HTML:
```html
<img src="data:image/jpeg;base64,{ndvi_image_base64}" alt="NDVI Heatmap" />
```

In JavaScript:
```javascript
const img = new Image();
img.src = `data:image/jpeg;base64,${response.ndvi_image_base64}`;
document.body.appendChild(img);
```

#### Error Responses

**400 Bad Request**
```json
{
  "detail": "Invalid latitude. Must be between -90 and 90"
}
```

**404 Not Found**
```json
{
  "detail": "No suitable images found for the specified criteria"
}
```

**500 Internal Server Error**
```json
{
  "detail": "Error processing NDVI: {error_message}"
}
```

---

## Example Usage

### cURL
```bash
curl -X POST "http://localhost:8000/analyze-ndvi" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 37.7749,
    "longitude": -122.4194,
    "buffer_distance": 100,
    "days_back": 60,
    "cloud_threshold": 15
  }'
```

### Python
```python
import requests
import base64
from PIL import Image
from io import BytesIO

url = "http://localhost:8000/analyze-ndvi"
payload = {
    "latitude": 37.7749,
    "longitude": -122.4194,
    "buffer_distance": 100,
    "days_back": 60,
    "cloud_threshold": 15,
    "image_width": 1024,
    "image_height": 768
}

response = requests.post(url, json=payload)
data = response.json()

# Print statistics
print(f"Health Status: {data['ndvi_stats']['health_status']}")
print(f"Mean NDVI: {data['ndvi_stats']['mean_ndvi']:.2f}")

# Save image
img_data = base64.b64decode(data['ndvi_image_base64'])
img = Image.open(BytesIO(img_data))
img.save('ndvi_output.jpg')
```

### JavaScript (Fetch API)
```javascript
const analyzeNDVI = async (lat, lon) => {
  const response = await fetch('http://localhost:8000/analyze-ndvi', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      latitude: lat,
      longitude: lon,
      buffer_distance: 100,
      days_back: 60,
      cloud_threshold: 15
    })
  });
  
  const data = await response.json();
  
  // Display statistics
  console.log('Health Status:', data.ndvi_stats.health_status);
  console.log('Mean NDVI:', data.ndvi_stats.mean_ndvi);
  
  // Display image
  const img = document.createElement('img');
  img.src = `data:image/jpeg;base64,${data.ndvi_image_base64}`;
  document.body.appendChild(img);
};

analyzeNDVI(37.7749, -122.4194);
```

---

## Technical Details

### Data Source
- **Satellite**: Sentinel-2 (Harmonized Collection)
- **Bands Used**: 
  - B8 (Near-Infrared): 842 nm
  - B4 (Red): 665 nm
- **Spatial Resolution**: 10 meters
- **Temporal Resolution**: 5 days (at equator)

### NDVI Calculation
```
NDVI = (NIR - Red) / (NIR + Red)
NDVI = (B8 - B4) / (B8 + B4)
```

### Image Processing
1. Filters imagery by date range and cloud coverage
2. Creates median composite from available images
3. Calculates NDVI for each pixel
4. Applies color palette (red to dark green)
5. Converts to JPEG format
6. Encodes as base64 string

### Color Palette
- **Red**: Very low NDVI (bare soil, stressed crops)
- **Orange**: Low NDVI
- **Yellow**: Moderate NDVI
- **Green**: Good vegetation
- **Dark Green**: Excellent vegetation health

---

## Installation & Setup

### Prerequisites
```bash
pip install fastapi uvicorn pillow numpy requests earthengine-api
```

### Service Account Setup
1. Create a Google Cloud Project
2. Enable Earth Engine API
3. Create a Service Account
4. Download JSON key file
5. Place key file in project directory
6. Update `service_account` and `key_file` variables in code

### Running the Server
```bash
python app.py
# or
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

---

## Rate Limits
- Earth Engine quota applies
- Recommended: Implement caching for frequently requested locations
- Consider rate limiting for production deployments

## Best Practices
1. **Buffer Distance**: Use 50-500m for field-level analysis
2. **Days Back**: 30-90 days for seasonal analysis, 7-14 days for recent changes
3. **Cloud Threshold**: Keep below 20% for accurate results
4. **Image Size**: Balance between quality and response size (800x600 recommended)

## Support
For issues or questions, please refer to:
- Google Earth Engine Documentation: https://developers.google.com/earth-engine
- FastAPI Documentation: https://fastapi.tiangolo.com/