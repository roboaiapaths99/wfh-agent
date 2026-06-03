import threading
import time
import base64
import collections
import requests

from config import ACTIVITY_SYNC_SECONDS, SCREENSHOT_SYNC_SECONDS, MAIN_BACKEND_URL
from local_state import load_state

from services.activity_service import get_activity_snapshot
from services.screenshot_service import capture_screenshot
from services.app_monitor_service import get_active_app_info
from services.productivity_service import calculate_productivity_score, get_app_category
from services.hardware_service import get_hardware_info
from db.local_db import add_to_queue, get_pending_items, mark_done, mark_failed
from sync.data_sync import send_activity, send_screenshot, send_productivity, send_app_usage

# Get real hardware device ID once at startup
try:
    _REAL_DEVICE_ID = get_hardware_info().get("device_id", "wfh-device-001")
except Exception:
    _REAL_DEVICE_ID = "wfh-device-001"
print(f"Agent started with hardware device_id: {_REAL_DEVICE_ID}")

_activity_running = False
_screenshot_running = False
_active_sampling_running = False
_app_usage_running = False
_queue_running = False
_face_check_running = False

_app_samples = collections.defaultdict(int)
_app_samples_lock = threading.Lock()

consecutive_idle_seconds = 0
_idle_alert_fired = False

def get_consecutive_idle_seconds():
    global consecutive_idle_seconds
    return consecutive_idle_seconds

def face_check_loop():
    global _face_check_running
    _face_check_running = True
    
    from services.webcam_service import capture_webcam

    while _face_check_running:
        try:
            state = load_state()
            token = state.get("token")
            session_id = state.get("session_id")
            policy = state.get("policy", {})
            
            interval_mins = policy.get("face_check_interval_minutes", 30)
            interval_secs = max(60, interval_mins * 60)
            
            for _ in range(int(interval_secs / 5)):
                if not _face_check_running:
                    return
                time.sleep(5)
                
            if not _face_check_running:
                break
                
            if token and session_id:
                print("Executing periodic WFH face check...")
                cam_res = capture_webcam()
                
                face_count = cam_res.get("face_count", 0)
                liveness = cam_res.get("liveness_passed", False)
                fake_cam = cam_res.get("fake_webcam_detected", False)
                image_base64 = cam_res.get("image_base64")
                
                passed = (face_count == 1) and liveness and not fake_cam
                
                failure_reason = ""
                if face_count == 0:
                    failure_reason = "No face detected in webcam."
                elif face_count > 1:
                    failure_reason = f"Multiple faces ({face_count}) detected."
                elif not liveness:
                    failure_reason = "Liveness check failed (spoofing risk)."
                elif fake_cam:
                    failure_reason = "Virtual camera software detected."
                    
                payload = {
                    "session_id": session_id,
                    "passed": passed,
                    "face_score": 1.0 if passed else 0.0,
                    "failure_reason": failure_reason,
                    "image_base64": image_base64
                }
                
                headers = {"Authorization": f"Bearer {token}"}
                requests.post(
                    f"{MAIN_BACKEND_URL}/api/wfh/face-check",
                    json=payload,
                    headers=headers,
                    timeout=20
                )
                print("Periodic WFH face check synced successfully.")
        except Exception as e:
            print("Face check loop error:", str(e))


def active_app_sampling_loop():
    global _active_sampling_running
    _active_sampling_running = True

    while _active_sampling_running:
        try:
            state = load_state()
            token = state.get("token")
            if token:
                app_info = get_active_app_info()
                app_name = app_info.get("active_app", "unknown")
                domain = app_info.get("active_domain")

                if domain:
                    key = f"{app_name} ({domain})"
                else:
                    key = app_name

                with _app_samples_lock:
                    _app_samples[key] += 1
        except Exception as e:
            print("Active app sampling error:", str(e))

        time.sleep(30)


def app_usage_sync_loop():
    global _app_usage_running
    _app_usage_running = True

    while _app_usage_running:
        time.sleep(300)

        if not _app_usage_running:
            break

        try:
            state = load_state()
            token = state.get("token")
            device_id = _REAL_DEVICE_ID  # Always use real hardware device ID
            session_id = state.get("session_id")

            if token:
                with _app_samples_lock:
                    samples = dict(_app_samples)
                    _app_samples.clear()

                if not samples:
                    app_info = get_active_app_info()
                    app_name = app_info.get("active_app", "unknown")
                    samples[app_name] = 1

                apps_list = []
                for name, count in samples.items():
                    clean_name = name.split(" (")[0] if " (" in name else name
                    category = get_app_category(clean_name)
                    apps_list.append({
                        "name": name,
                        "duration_seconds": count * 30,
                        "category": category
                    })

                payload = {
                    "device_id": device_id,
                    "session_id": session_id,
                    "date": time.strftime("%Y-%m-%d"),
                    "apps": apps_list
                }

                try:
                    result = send_app_usage(token, payload)
                    print("App usage synced:", result)
                except Exception as e:
                    print("App usage sync failed:", str(e))
        except Exception as e:
            print("App usage sync loop error:", str(e))


def activity_sync_loop():
    global _activity_running, consecutive_idle_seconds, _idle_alert_fired
    _activity_running = True

    while _activity_running:
        try:
            state = load_state()

            token = state.get("token")
            device_id = _REAL_DEVICE_ID  # Always use real hardware device ID
            session_id = state.get("session_id")

            if token:
                activity = get_activity_snapshot()

                activity["device_id"] = device_id
                activity["session_id"] = session_id

                # Idle Tracking
                keystrokes = activity.get("keystrokes", 0)
                clicks = activity.get("mouse_clicks", 0)
                
                if keystrokes == 0 and clicks == 0:
                    consecutive_idle_seconds += ACTIVITY_SYNC_SECONDS
                else:
                    consecutive_idle_seconds = 0
                    _idle_alert_fired = False

                policy = state.get("policy", {})
                max_idle_mins = policy.get("max_idle_minutes", 20)
                
                if consecutive_idle_seconds >= (max_idle_mins * 60) and not _idle_alert_fired:
                    print(f"Extended idle threshold hit! ({consecutive_idle_seconds}s). Dispatching idle alert...")
                    try:
                        idle_mins = int(consecutive_idle_seconds / 60)
                        alert_payload = {
                            "device_id": device_id,
                            "session_id": session_id,
                            "type": "WFH_IDLE_EXTENDED",
                            "severity": "medium",
                            "details": f"No keyboard or mouse activity detected for {idle_mins} minutes. Employee may be away from their desk.",
                            "metadata": {
                                "idle_seconds": consecutive_idle_seconds,
                                "idle_minutes": idle_mins
                            }
                        }
                        requests.post(
                            f"{MAIN_BACKEND_URL}/api/wfh/alert",
                            json=alert_payload,
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=10
                        )
                        _idle_alert_fired = True
                    except Exception as e:
                        print("Failed to dispatch idle alert:", str(e))

                try:
                    from services.activity_service import get_typing_cadence_stats
                    cadence = get_typing_cadence_stats()
                    if cadence.get("anomaly"):
                        print("Keystroke biometric cadence anomaly detected! Triggering silent webcam audit...")
                        from services.webcam_service import capture_webcam
                        cam_check = capture_webcam()
                        
                        face_status = "passed" if cam_check.get('liveness_passed') else "failed"
                        alert_payload = {
                            "device_id": device_id,
                            "type": "WFH_IDENTITY_MISMATCH",
                            "severity": "high",
                            "details": f"Typing pattern looks different from this employee's usual style — someone else might be using the computer. Webcam face check: {face_status}.",
                            "metadata": {
                                "cadence_mean": cadence.get("mean"),
                                "cadence_variance": cadence.get("variance"),
                                "liveness_passed": cam_check.get("liveness_passed")
                            }
                        }
                        
                        requests.post(
                            f"{MAIN_BACKEND_URL}/api/wfh/alert",
                            json=alert_payload,
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=20
                        )
                        print("Identity mismatch alert synced to backend.")
                except Exception as cadence_err:
                    print("Error running typing cadence continuous auth hook:", str(cadence_err))

                try:
                    result = send_activity(token, activity)
                    print("Activity synced:", result)
                except Exception as e:
                    activity["token"] = token
                    add_to_queue("activity", activity)
                    print("Activity queued:", str(e))

                try:
                    app_info = get_active_app_info()
                    active_app = app_info.get("active_app", "unknown")
                    
                    score = calculate_productivity_score(
                        activity_data=activity,
                        active_app=active_app
                    )

                    prod_payload = {
                        "device_id": device_id,
                        "session_id": session_id,
                        "date": time.strftime("%Y-%m-%d"),
                        "score": score,
                        "breakdown": {
                            "keystrokes": activity.get("keystrokes", 0),
                            "mouse_clicks": activity.get("mouse_clicks", 0),
                            "scroll_events": activity.get("scroll_events", 0),
                            "idle_seconds": activity.get("idle_seconds", 0),
                            "active_seconds": activity.get("active_seconds", 300)
                        }
                    }

                    prod_result = send_productivity(token, prod_payload)
                    print("Productivity synced:", prod_result)
                except Exception as prod_err:
                    print("Productivity sync failed:", str(prod_err))

            else:
                print("No token found. Login required.")

        except Exception as e:
            print("Activity auto sync error:", str(e))

        time.sleep(ACTIVITY_SYNC_SECONDS)


def screenshot_sync_loop():
    global _screenshot_running
    _screenshot_running = True

    while _screenshot_running:
        try:
            state = load_state()

            token = state.get("token")
            device_id = _REAL_DEVICE_ID  # Always use real hardware device ID
            session_id = state.get("session_id")
            policy = state.get("policy", {})

            if token:
                shot = capture_screenshot()
                file_path = shot.get("file_path")

                with open(file_path, "rb") as img_f:
                    encoded_string = base64.b64encode(img_f.read()).decode("utf-8")
                base64_url = f"data:image/jpeg;base64,{encoded_string}"

                app_info = get_active_app_info()

                payload = {
                    "device_id": device_id,
                    "session_id": session_id,
                    "image_url": base64_url,
                    "thumbnail_url": None,
                    "active_app": app_info.get("active_app"),
                    "active_window": app_info.get("active_window")
                }

                try:
                    result = send_screenshot(token, payload)
                    print("Screenshot synced:", result)
                except Exception as e:
                    payload["token"] = token
                    add_to_queue("screenshot", payload)
                    print("Screenshot queued:", str(e))

            else:
                print("No token found. Login required.")

        except Exception as e:
            print("Screenshot auto sync error:", str(e))

        # Dynamic screen capture sleep from policy
        interval_mins = policy.get("screenshot_interval_minutes", 10)
        interval_secs = max(60, interval_mins * 60) # min 1 min for safety
        
        for _ in range(int(interval_secs / 5)):
            if not _screenshot_running:
                break
            time.sleep(5)


def queue_sync_loop():
    while True:
        try:
            process_queue_once()
        except Exception as e:
            print("Queue sync error:", str(e))

        time.sleep(30)


def start_auto_sync():
    global _activity_running, _screenshot_running, _queue_running, _active_sampling_running, _app_usage_running, _face_check_running
    _activity_running = True
    _screenshot_running = True
    _queue_running = True
    _active_sampling_running = True
    _app_usage_running = True
    _face_check_running = True

    activity_thread = threading.Thread(target=activity_sync_loop, daemon=True)
    screenshot_thread = threading.Thread(target=screenshot_sync_loop, daemon=True)
    queue_thread = threading.Thread(target=queue_sync_loop, daemon=True)
    sampling_thread = threading.Thread(target=active_app_sampling_loop, daemon=True)
    app_usage_thread = threading.Thread(target=app_usage_sync_loop, daemon=True)
    face_check_thread = threading.Thread(target=face_check_loop, daemon=True)

    activity_thread.start()
    screenshot_thread.start()
    queue_thread.start()
    sampling_thread.start()
    app_usage_thread.start()
    face_check_thread.start()

    # Local screenshots cleanup on startup (older than 7 days)
    try:
        import glob
        import os
        now = time.time()
        for f in glob.glob("screenshots/*"):
            if os.stat(f).st_mtime < now - (7 * 86400):
                os.remove(f)
                print(f"Cleaned up stale local screenshot: {f}")
    except Exception as e:
        print("Local screenshot cleanup error:", str(e))

    return {
        "status": "started",
        "activity": True,
        "screenshots": True,
        "queue": True,
        "sampling": True,
        "app_usage": True,
        "face_check": True
    }


def stop_auto_sync():
    global _activity_running
    global _screenshot_running
    global _queue_running
    global _active_sampling_running
    global _app_usage_running
    global _face_check_running
    
    _activity_running = False
    _screenshot_running = False
    _queue_running = False
    _active_sampling_running = False
    _app_usage_running = False
    _face_check_running = False

    return {
        "status": "stopped"
    }
    
def process_queue_once():
    items = get_pending_items(limit=10)

    for item in items:
        try:
            payload = item["payload"]
            token = payload.pop("token", None)

            if not token:
                mark_failed(item["id"], "Missing token")
                continue

            if item["type"] == "activity":
                send_activity(token, payload)

            elif item["type"] == "screenshot":
                send_screenshot(token, payload)

            else:
                mark_failed(item["id"], "Unknown item type")
                continue

            mark_done(item["id"])

        except Exception as e:
            mark_failed(item["id"], str(e))