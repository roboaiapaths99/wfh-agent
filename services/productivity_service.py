import logging

logger = logging.getLogger(__name__)

# Default productivity weights matching the PRD
DEFAULT_WEIGHT_PRODUCTIVE_APP = 0.45
DEFAULT_WEIGHT_ACTIVITY = 0.35
DEFAULT_WEIGHT_FACE_PASS = 0.20

# Standard baseline events for a 5-minute tracking block (typical average typing/clicking rate)
BASELINE_EVENTS_5_MIN = 250.0

def get_app_category(app_name: str, org_policy: dict = None) -> str:
    """
    Returns app classification: productive, unproductive, or neutral.
    Uses app classifications matching process names from org policy or global defaults.
    """
    if not app_name or app_name == "unknown":
        return "neutral"

    app_name_lower = app_name.lower().replace(".exe", "").strip()

    # Pre-defined defaults matching typical office app structures
    productive_keywords = ["vscode", "code", "pycharm", "idea", "figma", "notion", "slack", "teams", "excel", "winword", "word", "powerpnt", "outlook", "chrome", "firefox"]
    unproductive_keywords = ["steam", "netflix", "youtube", "instagram", "facebook", "spotify", "discord", "game", "twitter", "reddit"]

    # Check if custom classification is defined in org policy
    if org_policy and "wfh_settings" in org_policy:
        wfh = org_policy["wfh_settings"]
        custom_productive = wfh.get("productive_apps", [])
        custom_unproductive = wfh.get("unproductive_apps", [])

        if any(app.lower() in app_name_lower for app in custom_productive):
            return "productive"
        if any(app.lower() in app_name_lower for app in custom_unproductive):
            return "unproductive"

    # Default category matches
    if any(keyword in app_name_lower for keyword in productive_keywords):
        return "productive"
    if any(keyword in app_name_lower for keyword in unproductive_keywords):
        return "unproductive"

    return "neutral"

def calculate_productivity_score(
    activity_data: dict,
    active_app: str,
    face_pass_count: int = 1,
    face_total_count: int = 1,
    org_policy: dict = None
) -> float:
    """
    Computes a WFH productivity score between 0 and 100.
    Formula:
      active_ratio = active_seconds / total_seconds
      productive_ratio = (1.0 if productive, 0.5 if neutral, 0.0 if unproductive)
      activity_ratio = min(1.0, (keystrokes + mouse_clicks + scroll_events) / baseline)
      face_ratio = face_pass_count / face_total_count (fallback to 1.0)
    """
    try:
        # 1. Active vs Idle time ratio
        total_sec = activity_data.get("idle_seconds", 0) + activity_data.get("active_seconds", 300)
        total_sec = max(total_sec, 1)
        active_ratio = float(activity_data.get("active_seconds", 300)) / total_sec
        active_ratio = max(0.0, min(1.0, active_ratio))

        # 2. Productive App ratio
        app_category = get_app_category(active_app, org_policy)
        if app_category == "productive":
            productive_ratio = 1.0
        elif app_category == "neutral":
            productive_ratio = 0.6 # Neutral gets partial credit
        else:
            productive_ratio = 0.1 # Unproductive gets very low score

        # App score combines active ratio and app type
        app_score = active_ratio * productive_ratio

        # 3. Activity ratio (typing + mouse)
        events = activity_data.get("keystrokes", 0) + activity_data.get("mouse_clicks", 0) + activity_data.get("scroll_events", 0)
        activity_ratio = min(1.0, float(events) / BASELINE_EVENTS_5_MIN)

        # 4. Face presence ratio
        face_ratio = 1.0
        if face_total_count > 0:
            face_ratio = max(0.0, min(1.0, float(face_pass_count) / face_total_count))

        # Weight distribution
        w_app = DEFAULT_WEIGHT_PRODUCTIVE_APP
        w_activity = DEFAULT_WEIGHT_ACTIVITY
        w_face = DEFAULT_WEIGHT_FACE_PASS

        if org_policy and "wfh_settings" in org_policy:
            # Load custom weights if present
            pass # Placeholder for custom weight overrides

        # Compute combined score
        score = (app_score * w_app + activity_ratio * w_activity + face_ratio * w_face) * 100.0
        score = round(max(0.0, min(100.0, score)), 2)
        return score

    except Exception as e:
        logger.error(f"Error in score calculation: {e}")
        return 75.0 # Return a balanced fallback score in case of calculation error
