import platform
import socket
import uuid
import psutil
import subprocess

def check_wifi_security() -> bool:
    """
    Checks if the active Wi-Fi connection is secured (WPA2/WPA3, etc.) or open.
    Returns True if secured or not using Wi-Fi (e.g. ethernet), False if connected to unsecured Wi-Fi.
    """
    try:
        # Run Windows wlan query tool
        output = subprocess.check_output(
            ["netsh", "wlan", "show", "interfaces"], 
            stderr=subprocess.STDOUT, 
            text=True, 
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        
        state = None
        auth = None
        for line in output.splitlines():
            line_strip = line.strip().lower()
            if "state" in line_strip:
                state = line_strip.split(":")[-1].strip()
            if "authentication" in line_strip:
                auth = line_strip.split(":")[-1].strip()
                
        if state != "connected":
            return True
            
        # Flag open or unsecured authentication modes
        if auth and any(open_word in auth for open_word in ["open", "none"]):
            return False
            
    except Exception:
        return True
        
    return True


def get_hardware_info():
    ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)

    return {
        "device_id": str(uuid.getnode()),
        "mac_address": ":".join(
            ["{:02x}".format((uuid.getnode() >> i) & 0xff) for i in range(0, 8 * 6, 8)][::-1]
        ),
        "cpu_id": platform.processor(),
        "os_info": f"{platform.system()} {platform.release()}",
        "hostname": socket.gethostname(),
        "ip_local": socket.gethostbyname(socket.gethostname()),
        "ram_gb": ram_gb,
        "screen_resolution": None,
        "monitor_count": None,
        "wifi_secured": check_wifi_security()
    }