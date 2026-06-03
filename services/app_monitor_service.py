import psutil
import pygetwindow as gw
import re

def extract_domain_from_title(title: str) -> str:
    """Extracts a domain signature or website identifier from active window title."""
    if not title or title == "unknown":
        return None
    title_lower = title.lower()
    
    # Common office/unproductive domain maps
    domains = [
        "github.com", "github", "gitlab.com", "gitlab", "jira", "atlassian",
        "youtube.com", "youtube", "netflix.com", "netflix", "facebook.com", "facebook",
        "instagram.com", "instagram", "twitter.com", "twitter", "x.com",
        "stackoverflow.com", "stackoverflow", "chatgpt.com", "chatgpt", "openai",
        "slack.com", "slack", "zoom.us", "zoom", "meet.google.com", "google meet",
        "figma.com", "figma", "notion.so", "notion", "linkedin.com", "linkedin"
    ]
    
    for domain in domains:
        if domain in title_lower:
            if domain in ["github", "github.com"]: return "github.com"
            if domain in ["youtube", "youtube.com"]: return "youtube.com"
            if domain in ["netflix", "netflix.com"]: return "netflix.com"
            if domain in ["slack", "slack.com"]: return "slack.com"
            if domain in ["figma", "figma.com"]: return "figma.com"
            if domain in ["notion", "notion.so"]: return "notion.so"
            if domain in ["zoom", "zoom.us"]: return "zoom.us"
            if domain in ["google meet", "meet.google.com"]: return "meet.google.com"
            if domain in ["atlassian", "jira"]: return "jira.atlassian.com"
            if domain in ["stackoverflow", "stackoverflow.com"]: return "stackoverflow.com"
            if domain in ["chatgpt", "chatgpt.com", "openai"]: return "chatgpt.com"
            return f"{domain}.com" if "." not in domain else domain

    # Generic regex match for domain format
    domain_match = re.search(r'([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', title)
    if domain_match:
        return domain_match.group(1).lower()
        
    return None

def get_active_app_info():
    try:
        active_window = gw.getActiveWindow()

        if not active_window:
            return {
                "active_app": "unknown",
                "active_window": "unknown",
                "active_domain": None
            }

        window_title = active_window.title or "unknown"
        active_app = "unknown"

        # 1. Native Windows PID extraction using ctypes (highly accurate, fast)
        try:
            import ctypes
            pid = ctypes.c_ulong()
            # Win32 call to get process ID of current window handle
            ctypes.windll.user32.GetWindowThreadProcessId(active_window._hWnd, ctypes.byref(pid))
            if pid.value:
                proc = psutil.Process(pid.value)
                active_app = proc.name()
        except Exception:
            pass

        # 2. Scanning fallback if native PID lookup fails
        if active_app == "unknown":
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    if proc.info["name"]:
                        name = proc.info["name"]
                        if name.lower().replace(".exe", "") in window_title.lower():
                            active_app = name
                            break
                except Exception:
                    continue

        # Map raw process names to highly readable friendly titles
        friendly_names = {
            "code.exe": "VS Code",
            "chrome.exe": "Google Chrome",
            "msedge.exe": "Microsoft Edge",
            "brave.exe": "Brave Browser",
            "slack.exe": "Slack",
            "zoom.exe": "Zoom Meeting",
            "teams.exe": "Microsoft Teams",
            "explorer.exe": "Windows Explorer",
            "cmd.exe": "Command Prompt",
            "powershell.exe": "PowerShell",
            "python.exe": "Python Runtime",
            "notepad.exe": "Notepad",
            "taskmgr.exe": "Task Manager"
        }
        active_app_friendly = friendly_names.get(active_app.lower(), active_app)

        # If it is a browser process, attempt to audit the tab domain
        active_domain = None
        if any(b_name in active_app.lower() for b_name in ["chrome", "firefox", "msedge", "browser"]):
            active_domain = extract_domain_from_title(window_title)

        return {
            "active_app": active_app_friendly,
            "active_window": window_title,
            "active_domain": active_domain
        }

    except Exception as e:
        return {
            "active_app": "unknown",
            "active_window": f"error: {str(e)}",
            "active_domain": None
        }