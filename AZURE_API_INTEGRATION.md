# Azure API Integration Guide for Frontend

This guide explains how to integrate your frontend dashboard with the Azure-deployed Emergency Vehicle Detection System.

## API Base URL

Update your frontend configuration to use the Azure VM's public IP or domain:

```javascript
// For development (using public IP)
const API_BASE_URL = "http://YOUR_AZURE_VM_IP:5000";

// For production (using domain with SSL)
const API_BASE_URL = "https://your-domain.com";
```

## API Endpoints

### 1. Get System Status
```http
GET /api/status
```

**Response Example:**
```json
{
  "audio": {
    "status": "Normal traffic",
    "score": 0.02,
    "is_emergency": false
  },
  "video": {
    "front": {
      "vehicle_type": "none",
      "siren_light": "none",
      "is_emergency": false,
      "ocr_text": []
    },
    "top": {...},
    "upload_front": {...},
    "upload_top": {...}
  },
  "is_emergency": false,
  "emergency_type": "none",
  "detected_objects": [],
  "location": "City, Region"
}
```

### 2. Upload Video for Analysis
```http
POST /api/upload_video
Content-Type: multipart/form-data

Parameters:
- video: <file>  (mp4, avi, mov, mkv)
- view: "front" or "top"
```

**JavaScript Example:**
```javascript
async function uploadVideo(file, view) {
  const formData = new FormData();
  formData.append('video', file);
  formData.append('view', view);

  const response = await fetch(`${API_BASE_URL}/api/upload_video`, {
    method: 'POST',
    body: formData
  });
  
  const data = await response.json();
  console.log(data); // {"status": "success", "message": "...", "filename": "..."}
  return data;
}
```

### 3. Control Video Processing
```http
POST /api/video/control
Content-Type: application/json

Body:
{
  "view": "front|top|upload_front|upload_top",
  "action": "start|stop"
}
```

**JavaScript Example:**
```javascript
async function controlVideo(view, action) {
  const response = await fetch(`${API_BASE_URL}/api/video/control`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      view: view,
      action: action
    })
  });
  
  return await response.json();
}

// Usage
controlVideo('upload_front', 'start');  // Start processing
controlVideo('upload_front', 'stop');   // Stop processing
```

### 4. Get Analytics Data
```http
GET /api/analytics?date=YYYY-MM-DD
```

**Response Example:**
```json
{
  "trends": [
    {
      "timestamp": "2026-04-27T10:30:00",
      "vehicle_type": "ambulance",
      "is_emergency": true
    }
  ],
  "breakdown": {
    "ambulance": 5,
    "fire": 2,
    "police": 3
  }
}
```

### 5. Get Recent Alerts
```http
GET /api/alerts
```

**Response Example:**
```json
[
  {
    "_id": "507f1f77bcf86cd799439011",
    "timestamp": "2026-04-27T10:30:00",
    "vehicle_type": "ambulance",
    "location": "City, Region",
    "details": {
      "audio_status": "SIREN DETECTED",
      "siren_light": "RED",
      "ocr_texts": ["AMBULANCE", "1990"]
    }
  }
]
```

### 6. Get Latest Detection
```http
GET /api/latest_detection
```

### 7. Delete Alert
```http
DELETE /api/alerts/{alert_id}
```

---

## Frontend Implementation Example

### HTML Video Upload Form

```html
<div class="video-upload-section">
  <h2>Upload Video for Analysis</h2>
  
  <form id="uploadForm">
    <div class="form-group">
      <label>Select View:</label>
      <select id="viewSelect">
        <option value="front">Front View</option>
        <option value="top">Top View</option>
      </select>
    </div>
    
    <div class="form-group">
      <label>Upload Video:</label>
      <input type="file" id="videoInput" accept=".mp4,.avi,.mov,.mkv" />
    </div>
    
    <button type="submit">Upload & Analyze</button>
    <div id="uploadStatus"></div>
  </form>
  
  <div id="results" class="results-container" style="display:none;">
    <h3>Analysis Results</h3>
    <div id="resultsContent"></div>
  </div>
</div>
```

### JavaScript Upload Handler

```javascript
document.getElementById('uploadForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const file = document.getElementById('videoInput').files[0];
  const view = document.getElementById('viewSelect').value;
  const statusDiv = document.getElementById('uploadStatus');
  
  if (!file) {
    statusDiv.innerHTML = '<p class="error">Please select a video file</p>';
    return;
  }
  
  try {
    statusDiv.innerHTML = '<p class="loading">Uploading...</p>';
    
    const formData = new FormData();
    formData.append('video', file);
    formData.append('view', view);
    
    const response = await fetch(`${API_BASE_URL}/api/upload_video`, {
      method: 'POST',
      body: formData
    });
    
    const data = await response.json();
    
    if (data.status === 'success') {
      statusDiv.innerHTML = `<p class="success">✓ Video uploaded: ${data.filename}</p>`;
      
      // Poll for results
      pollResults(view);
    } else {
      statusDiv.innerHTML = `<p class="error">✗ ${data.message}</p>`;
    }
  } catch (error) {
    statusDiv.innerHTML = `<p class="error">Error: ${error.message}</p>`;
  }
});

async function pollResults(view) {
  // Poll status every 2 seconds for up to 30 seconds
  for (let i = 0; i < 15; i++) {
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    const response = await fetch(`${API_BASE_URL}/api/status`);
    const data = await response.json();
    
    const viewData = data.video[`upload_${view}`];
    if (viewData && viewData.is_emergency) {
      displayResults(viewData);
      return;
    }
  }
}

function displayResults(viewData) {
  const resultsDiv = document.getElementById('results');
  const content = document.getElementById('resultsContent');
  
  content.innerHTML = `
    <p><strong>Vehicle Type:</strong> ${viewData.vehicle_type}</p>
    <p><strong>Siren Light:</strong> ${viewData.siren_light}</p>
    <p><strong>OCR Text:</strong> ${viewData.ocr_text.join(', ')}</p>
    <p><strong>Emergency Detected:</strong> ${viewData.is_emergency ? '✓ YES' : '✗ NO'}</p>
  `;
  
  resultsDiv.style.display = 'block';
}
```

### Real-time Status Dashboard

```javascript
// Fetch and display status every 5 seconds
async function updateDashboard() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/status`);
    const data = await response.json();
    
    // Update UI elements
    document.getElementById('audioStatus').textContent = data.audio.status;
    document.getElementById('isEmergency').textContent = data.is_emergency ? 'YES' : 'NO';
    document.getElementById('location').textContent = data.location;
    
    if (data.is_emergency) {
      showEmergencyAlert(data);
    }
  } catch (error) {
    console.error('Dashboard update failed:', error);
  }
}

// Update every 5 seconds
setInterval(updateDashboard, 5000);

function showEmergencyAlert(data) {
  const alertBox = document.createElement('div');
  alertBox.className = 'emergency-alert';
  alertBox.innerHTML = `
    <h2>🚨 EMERGENCY DETECTED</h2>
    <p>Type: ${data.emergency_type}</p>
    <p>Location: ${data.location}</p>
  `;
  document.body.prepend(alertBox);
  
  // Auto-hide after 10 seconds
  setTimeout(() => alertBox.remove(), 10000);
}
```

### CSS Styling

```css
.video-upload-section {
  max-width: 600px;
  margin: 20px auto;
  padding: 20px;
  border: 1px solid #ddd;
  border-radius: 8px;
}

.form-group {
  margin-bottom: 15px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}

.form-group input[type="file"],
.form-group select {
  width: 100%;
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
}

button {
  background-color: #007bff;
  color: white;
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}

button:hover {
  background-color: #0056b3;
}

.loading {
  color: #ff9800;
}

.success {
  color: #4caf50;
}

.error {
  color: #f44336;
}

.results-container {
  margin-top: 20px;
  padding: 15px;
  background-color: #f5f5f5;
  border-radius: 4px;
}

.emergency-alert {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  background-color: #f44336;
  color: white;
  padding: 20px;
  text-align: center;
  animation: slideDown 0.3s ease-in-out;
  z-index: 1000;
}

@keyframes slideDown {
  from {
    transform: translateY(-100%);
  }
  to {
    transform: translateY(0);
  }
}
```

---

## CORS Configuration

The Flask app has CORS enabled, so you can call it from any frontend domain:

```javascript
// These calls work from any domain
fetch('http://YOUR_AZURE_VM_IP:5000/api/status')
```

## Error Handling

Always handle API errors gracefully:

```javascript
async function apiCall(endpoint) {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error(`API Error on ${endpoint}:`, error);
    // Show user-friendly error message
    alert('Failed to fetch data. Check your connection.');
    return null;
  }
}
```

## Testing Endpoints

### Using cURL (from terminal)

```bash
# Get status
curl http://YOUR_AZURE_VM_IP:5000/api/status

# Upload video
curl -X POST \
  -F "video=@sample_video.mp4" \
  -F "view=front" \
  http://YOUR_AZURE_VM_IP:5000/api/upload_video

# Get analytics
curl "http://YOUR_AZURE_VM_IP:5000/api/analytics?date=2026-04-27"

# Get alerts
curl http://YOUR_AZURE_VM_IP:5000/api/alerts
```

### Using Postman

1. Create a new request collection
2. Set Base URL: `http://YOUR_AZURE_VM_IP:5000`
3. Add requests for each endpoint
4. Test with sample data

---

## Performance Tips

1. **Limit Video Size**: Keep uploaded videos under 500MB
2. **Batch Requests**: Don't poll /api/status more than every 2 seconds
3. **Cache Status**: Store last status locally, only update on changes
4. **Connection Pooling**: Use persistent connections in production
5. **Rate Limiting**: Consider implementing rate limiting on frontend

---

## Deployment Notes

- Update `API_BASE_URL` to your Azure VM's public IP
- For production, use your domain with HTTPS
- Keep MongoDB URI secure (never expose in frontend code)
- Implement authentication if needed (JWT, API keys)
- Monitor API response times and failures

