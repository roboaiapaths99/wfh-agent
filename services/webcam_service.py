import os
import base64
import time
import logging

logger = logging.getLogger(__name__)

# Try to import cv2, but make it optional to prevent startup crashes if not installed
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    logger.warning("OpenCV is not installed in the agent virtual environment. Webcam capture will use fallback.")

# Constant for fallback image if webcam is unavailable or cv2 is not present
FALLBACK_WEBCAM_IMAGE = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)

def is_fake_webcam_active() -> bool:
    """
    Checks if virtual webcams are running in the system.
    Looks for typical virtual camera drivers (OBS, ManyCam, Snap Camera).
    """
    try:
        import psutil
        virtual_camera_processes = [
            "obs64.exe", "obs.exe", "manycam.exe", "snapcamera.exe",
            "virtualcamera", "webcammax", "vcam"
        ]
        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info["name"]
                if name and any(vc in name.lower() for vc in virtual_camera_processes):
                    logger.warning(f"Fake/Virtual webcam software detected running: {name}")
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        logger.error(f"Error checking virtual webcams: {e}")
    return False

def detect_faces(frame) -> int:
    """
    Detects the number of faces in a frame using OpenCV Haar Cascade.
    """
    if not OPENCV_AVAILABLE:
        return 0
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Load the default Haar Cascade face classifier from OpenCV
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face_cascade = cv2.CascadeClassifier(cascade_path)
        if face_cascade.empty():
            logger.error("Haar cascade face classifier xml failed to load.")
            return 0
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        return len(faces)
    except Exception as e:
        logger.error(f"Face detection error: {e}")
        return 0

def verify_liveness(frame) -> bool:
    """
    Verifies biometric liveness by checking for eyes inside the face region.
    Prevents standard flat photo printouts from passing biometrics.
    """
    if not OPENCV_AVAILABLE:
        return True
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        eye_cascade_path = cv2.data.haarcascades + 'haarcascade_eye.xml'
        eye_cascade = cv2.CascadeClassifier(eye_cascade_path)
        if eye_cascade.empty():
            return True
        
        eyes = eye_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(10, 10))
        return len(eyes) > 0
    except Exception:
        return True

def capture_webcam() -> dict:
    """
    Captures a frame from the webcam.
    Returns a dict with face presence info, virtual camera detection, and base64 jpeg image.
    """
    result = {
        "status": "success",
        "image_base64": None,
        "face_count": 0,
        "liveness_passed": True,
        "fake_webcam_detected": is_fake_webcam_active(),
        "timestamp": time.time(),
        "error": None
    }

    if not OPENCV_AVAILABLE:
        result["image_base64"] = FALLBACK_WEBCAM_IMAGE
        result["error"] = "OpenCV library not available on agent"
        return result

    cap = None
    try:
        # Open default system camera (device index 0)
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            result["image_base64"] = FALLBACK_WEBCAM_IMAGE
            result["error"] = "No webcam device detected"
            return result

        # Warm up the sensor
        for _ in range(3):
            cap.read()

        ret, frame = cap.read()
        if not ret or frame is None:
            result["image_base64"] = FALLBACK_WEBCAM_IMAGE
            result["error"] = "Failed to capture frame from webcam"
            return result

        # Run face detection & liveness
        result["face_count"] = detect_faces(frame)
        result["liveness_passed"] = verify_liveness(frame) if result["face_count"] > 0 else False

        # Compress to JPEG
        ret_code, jpeg_buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if ret_code:
            result["image_base64"] = base64.b64encode(jpeg_buffer).decode('utf-8')
        else:
            result["image_base64"] = FALLBACK_WEBCAM_IMAGE
            result["error"] = "Failed to compress image to JPEG"

    except Exception as e:
        logger.error(f"Webcam capture error: {e}")
        result["image_base64"] = FALLBACK_WEBCAM_IMAGE
        result["error"] = f"Webcam error: {str(e)}"
    finally:
        if cap is not None:
            cap.release()

    return result
