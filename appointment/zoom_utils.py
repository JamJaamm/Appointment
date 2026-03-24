import requests
import base64
import uuid
from datetime import datetime
from django.conf import settings

def get_zoom_access_token():
    """
    Obtain a Server-to-Server OAuth token from Zoom.
    """
    url = "https://zoom.us/oauth/token"
    
    # Encode Client ID and Client Secret
    auth_str = f"{settings.ZOOM_CLIENT_ID}:{settings.ZOOM_CLIENT_SECRET}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    params = {
        "grant_type": "account_credentials",
        "account_id": settings.ZOOM_ACCOUNT_ID
    }
    
    response = requests.post(url, headers=headers, params=params)
    
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        print(f"Zoom OAuth Error: {response.status_code} - {response.text}")
        return None

def create_zoom_meeting(topic, start_time, duration=30):
    """
    Create a scheduled Zoom meeting.
    Falls back to mock meeting if Zoom API fails.
    """
    # Try real Zoom API first
    token = get_zoom_access_token()
    if token:
        url = f"{settings.ZOOM_BASE_URL}users/me/meetings"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        payload = {
            "topic": topic,
            "type": 2,  # Scheduled meeting
            "start_time": start_time.isoformat(),
            "duration": duration,
            "timezone": "UTC",
            "settings": {
                "join_before_host": True,
                "approval_type": 2, # 0=Automatic, 1=Manual, 2=No Registration Required
                "audio": "both",
                "auto_recording": "none",
                "waiting_room": False, # Optional: disable waiting room for easier testing
            }
        }

        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 201:
            print("Real Zoom meeting created successfully")
            return response.json()
        else:
            print(f"Zoom API failed: {response.status_code} - Creating mock meeting")
    
    # Fallback: Create mock meeting data
    meeting_id = str(uuid.uuid4())[:11]  # Generate mock meeting ID
    mock_meeting = {
        "id": meeting_id,
        "topic": topic,
        "start_time": start_time.isoformat(),
        "duration": duration,
        "timezone": "UTC",
        "join_url": f"https://zoom.us/j/{meeting_id}?pwd={str(uuid.uuid4())[:8]}",
        "start_url": f"https://zoom.us/s/{meeting_id}?pwd={str(uuid.uuid4())[:8]}",
        "uuid": str(uuid.uuid4()),
        "created_at": datetime.now().isoformat(),
        "mock": True  # Flag to indicate this is a mock meeting
    }
    
    print("Created mock Zoom meeting for testing")
    return mock_meeting
