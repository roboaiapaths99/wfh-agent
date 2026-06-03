import psutil
import time
import logging
from services.app_monitor_service import get_active_app_info

logger = logging.getLogger(__name__)

# Active meeting session tracker
active_meeting = {
    "platform": None,
    "start_time": 0,
    "is_in_meeting": False
}

def detect_meeting_platform() -> str:
    """
    Checks active processes and window titles to determine if user is in a meeting.
    Returns: 'zoom', 'teams', 'google_meet', 'slack', or None.
    """
    try:
        # Check standard window title info
        app_info = get_active_app_info()
        window_title = app_info.get("active_window", "").lower()
        active_app = app_info.get("active_app", "").lower()

        # Check for Google Meet inside window titles
        if "meet.google.com" in window_title or "google meet" in window_title:
            return "google_meet"
        
        # Check running processes
        meeting_process_mapping = {
            "zoom.exe": "zoom",
            "zoom": "zoom",
            "teams.exe": "teams",
            "teams": "teams",
            "ms-teams.exe": "teams",
            "slack.exe": "slack",
            "slack": "slack"
        }

        # Scan active processes
        for proc in psutil.process_iter(["name"]):
            try:
                proc_name = proc.info["name"]
                if proc_name and proc_name.lower() in meeting_process_mapping:
                    # Double-check window title for active call signature if it's Slack/Teams
                    mapped_platform = meeting_process_mapping[proc_name.lower()]
                    
                    if mapped_platform == "slack" and "huddle" not in window_title:
                        # Only flag Slack if they are actively in a huddle
                        continue
                    
                    return mapped_platform
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    except Exception as e:
        logger.error(f"Error checking for active meeting: {e}")

    return None

def check_meeting_status() -> dict:
    """
    Called periodically to monitor meeting status.
    If a meeting starts, logs start time. If a meeting ends, computes final duration.
    Returns the meeting state payload.
    """
    platform = detect_meeting_platform()
    now = time.time()

    if platform and not active_meeting["is_in_meeting"]:
        # Meeting just started!
        active_meeting["platform"] = platform
        active_meeting["start_time"] = now
        active_meeting["is_in_meeting"] = True
        logger.info(f"Meeting started on platform: {platform}")
        
        return {
            "status": "started",
            "platform": platform,
            "start_time": now,
            "duration_seconds": 0
        }

    elif not platform and active_meeting["is_in_meeting"]:
        # Meeting just ended!
        duration = now - active_meeting["start_time"]
        final_platform = active_meeting["platform"]
        
        active_meeting["is_in_meeting"] = False
        active_meeting["platform"] = None
        active_meeting["start_time"] = 0
        
        logger.info(f"Meeting ended on platform: {final_platform}. Duration: {duration:.1f}s")
        
        return {
            "status": "ended",
            "platform": final_platform,
            "duration_seconds": round(duration, 1)
        }

    elif platform and active_meeting["is_in_meeting"]:
        # Still in meeting
        duration = now - active_meeting["start_time"]
        return {
            "status": "active",
            "platform": active_meeting["platform"],
            "duration_seconds": round(duration, 1)
        }

    return {
        "status": "inactive",
        "platform": None,
        "duration_seconds": 0
    }
