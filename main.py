from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.hardware_service import get_hardware_info
from services.activity_service import start_activity_tracking, get_activity_snapshot
from services.screenshot_service import capture_screenshot
from sync.data_sync import send_device_info, send_activity, send_screenshot
from auto_sync import start_auto_sync, stop_auto_sync
from services.app_monitor_service import get_active_app_info
from local_state import save_state, load_state, clear_state
from db.local_db import init_db, queue_count



app = FastAPI(title="LogDay WFH Local Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    init_db()
    start_activity_tracking()
    # Auto-resume background syncing loops if session state was already running
    state = load_state()
    if state.get("token"):
        print("Restoring active auto-sync Loops on daemon startup...")
        start_auto_sync()


@app.get("/")
def root():
    return {
        "status": "running",
        "service": "LogDay WFH Agent"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/hardware")
def hardware():
    return get_hardware_info()


@app.get("/activity")
def activity():
    from auto_sync import get_consecutive_idle_seconds
    res = get_activity_snapshot(reset=False)
    res["consecutive_idle_seconds"] = get_consecutive_idle_seconds()
    return res



@app.get("/screenshot")
def screenshot():
    import base64
    import os
    res = capture_screenshot()
    file_path = res.get("file_path")
    if file_path and os.path.exists(file_path):
        with open(file_path, "rb") as img_f:
            encoded_string = base64.b64encode(img_f.read()).decode("utf-8")
        res["image_base64"] = f"data:image/jpeg;base64,{encoded_string}"
    return res



@app.get("/screenshots")
def screenshots_alias():
    """Alias used by Electron UI. Returns latest captured screenshot."""
    return screenshot()

@app.post("/sync/device")
def sync_device(data: dict):
    token = data.get("token")
    payload = data.get("payload")

    if not token:
        return {"status": "error", "message": "token missing"}

    return send_device_info(token, payload)


@app.post("/sync/activity")
def sync_activity(data: dict):
    token = data.get("token")
    payload = data.get("payload")

    if not token:
        return {"status": "error", "message": "token missing"}

    return send_activity(token, payload)


@app.post("/sync/screenshot")
def sync_screenshot(data: dict):
    token = data.get("token")
    payload = data.get("payload")

    if not token:
        return {"status": "error", "message": "token missing"}

    return send_screenshot(token, payload)

@app.post("/auto-sync/start")
def start_sync():
    return start_auto_sync()


@app.post("/auto-sync/stop")
def stop_sync():
    return stop_auto_sync()

@app.get("/active-app")
def active_app():
    return get_active_app_info()



@app.get("/apps")
def apps_usage_snapshot(date: str = None):
    """Lightweight local response for Electron app usage page."""
    app = get_active_app_info()
    return {
        "date": date,
        "apps": [
            {
                "name": app.get("active_app", "unknown"),
                "active_window": app.get("active_window", "unknown"),
                "active_domain": app.get("active_domain"),
                "duration_seconds": 0
            }
        ]
    }

@app.post("/auth/save")
def save_auth(data: dict):
    token = data.get("token")
    device_id = data.get("device_id", "wfh-device-001")
    session_id = data.get("session_id")
    policy = data.get("policy")

    if not token:
        return {"status": "error", "message": "token missing"}

    state = load_state()
    state.update({
        "token": token,
        "device_id": device_id,
        "session_id": session_id
    })
    if policy:
        state["policy"] = policy

    save_state(state)

    return {
        "status": "success",
        "message": "Auth saved",
        "device_id": device_id,
        "session_id": session_id
    }


@app.get("/auth/status")
def auth_status():
    state = load_state()

    return {
        "logged_in": bool(state.get("token")),
        "device_id": state.get("device_id"),
        "session_id": state.get("session_id")
    }


@app.post("/auth/clear")
def auth_clear():
    state = load_state()
    state["session_id"] = None
    save_state(state)
    return {
        "status": "success",
        "message": "Session cleared"
    }


@app.post("/auth/logout")
def auth_logout():
    clear_state()
    return {
        "status": "success",
        "message": "Logged out"
    }
    
@app.get("/queue/count")
def get_queue_count():
    return {
        "pending": queue_count()
    }

# --- NEW ENHANCED MONITORING ENDPOINTS ---

@app.get("/webcam")
def webcam_capture():
    from services.webcam_service import capture_webcam
    return capture_webcam()

@app.get("/meeting")
def meeting_status():
    from services.meeting_service import check_meeting_status
    return check_meeting_status()

@app.post("/challenge/generate")
def challenge_generate():
    from services.verification_service import generate_random_question
    return generate_random_question()

@app.post("/challenge/respond")
def challenge_respond(data: dict):
    from services.verification_service import submit_challenge_response
    answer = data.get("answer", "")
    return submit_challenge_response(answer)

@app.get("/challenge/status")
def challenge_status():
    from services.verification_service import get_current_challenge_status
    return get_current_challenge_status()

@app.get("/productivity")
def get_productivity():
    from services.productivity_service import calculate_productivity_score
    from services.activity_service import get_activity_snapshot
    from services.app_monitor_service import get_active_app_info
    
    activity = get_activity_snapshot(reset=False)
    app_info = get_active_app_info()
    
    score = calculate_productivity_score(
        activity_data={
            "keystrokes": activity.get("keystrokes", 0),
            "mouse_clicks": activity.get("mouse_clicks", 0),
            "scroll_events": activity.get("scroll_events", 0),
            "idle_seconds": activity.get("idle_seconds", 0),
            "active_seconds": activity.get("active_seconds", 300),
        },
        active_app=app_info.get("active_app", "unknown")
    )
    return {
        "score": score
    }

@app.get("/cadence")
def get_cadence():
    from services.activity_service import get_typing_cadence_stats
    return get_typing_cadence_stats()

@app.post("/auth/check")
def auth_check(data: dict = None):
    if data is None:
        data = {}
    state = load_state()
    token = state.get("token") or data.get("token")
    if not token:
        return {"status": "error", "message": "token missing"}
    
    from config import MAIN_BACKEND_URL
    import requests
    try:
        response = requests.post(
            f"{MAIN_BACKEND_URL}/auth/check",
            headers={"Authorization": f"Bearer {token}"},
            timeout=20
        )
        res_data = response.json()
        if response.status_code == 200:
            checked_in = res_data.get("checked_in")
            session_id = res_data.get("session_id")
            
            # Update local agent state
            current_state = load_state()
            current_state["session_id"] = session_id
            if token and not current_state.get("token"):
                current_state["token"] = token
            save_state(current_state)
            
            # Start/stop auto sync based on check-in state
            if checked_in:
                start_auto_sync()
            else:
                stop_auto_sync()
                
            return res_data
        else:
            return {"status": "error", "message": res_data.get("detail", "Backend request failed")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=7890, log_level="info")
