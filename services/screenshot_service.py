import mss
from PIL import Image
import os
from datetime import datetime


import os
USER_HOME = os.path.expanduser("~")
LOGDAY_DIR = os.path.join(USER_HOME, ".logday-wfh")
SCREENSHOT_DIR = os.path.join(LOGDAY_DIR, "screenshots")

os.makedirs(SCREENSHOT_DIR, exist_ok=True)



def capture_screenshot():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"screenshot_{timestamp}.jpg"
    file_path = os.path.join(SCREENSHOT_DIR, file_name)

    with mss.mss() as sct:
        monitor = sct.monitors[1]
        img = sct.grab(monitor)

        image = Image.frombytes("RGB", img.size, img.rgb)
        image.save(file_path, "JPEG", quality=70)

    return {
        "file_path": file_path,
        "file_name": file_name,
        "timestamp": timestamp
    }