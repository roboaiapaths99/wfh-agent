from pynput import keyboard, mouse
import time

keyboard_count = 0
mouse_clicks = 0
scroll_events = 0
last_activity_time = time.time()

# Keystroke cadence tracking variables
last_key_press_time = None
key_intervals = []


def on_key_press(key):
    global keyboard_count, last_activity_time, last_key_press_time, key_intervals
    keyboard_count += 1
    now = time.time()
    last_activity_time = now
    
    if last_key_press_time is not None:
        interval = now - last_key_press_time
        # Differentiate active typing intervals (under 1.5s) from generic pauses
        if interval < 1.5:
            key_intervals.append(interval)
            if len(key_intervals) > 50:
                key_intervals.pop(0)
    last_key_press_time = now


def on_click(x, y, button, pressed):
    global mouse_clicks, last_activity_time
    if pressed:
        mouse_clicks += 1
        last_activity_time = time.time()


def on_scroll(x, y, dx, dy):
    global scroll_events, last_activity_time
    scroll_events += 1
    last_activity_time = time.time()


def get_typing_cadence_stats() -> dict:
    """Calculates typing rhythm stats (mean and variance) to detect user swap anomalies."""
    global key_intervals, keyboard_count, mouse_clicks
    
    if len(key_intervals) > 0:
        import numpy as np
        intervals = np.array(key_intervals)
        mean_val = float(np.mean(intervals))
        std_val = float(np.std(intervals))
        
        # WPM estimation: 1 word = 5 characters.
        # mean_val is seconds per character.
        # characters per minute = 60 / mean_val
        # words per minute = 12 / mean_val
        if mean_val > 0:
            wpm = int(12.0 / mean_val)
        else:
            wpm = 0
            
        wpm = max(10, min(120, wpm))
        variance_val = std_val ** 2
        anomaly = mean_val > 0.6 or std_val > 0.3
    else:
        wpm = 45 if keyboard_count > 0 else 0
        mean_val = 0.0
        variance_val = 0.0
        anomaly = False
        
    cpm = mouse_clicks * 12
    if cpm == 0 and mouse_clicks > 0:
        cpm = 15
    cpm = max(0, min(80, cpm))
    
    if wpm > 60 or cpm > 40:
        intensity = "High Work Intensity"
    elif wpm > 25 or cpm > 15:
        intensity = "Balanced Work Intensity"
    else:
        intensity = "Low Work Intensity"
        
    return {
        "status": "active" if len(key_intervals) >= 10 else "accumulating",
        "mean": round(mean_val, 4),
        "variance": round(variance_val, 4),
        "anomaly": anomaly,
        "typing_speed_wpm": wpm,
        "clicks_per_minute": cpm,
        "work_intensity_category": intensity
    }


keyboard_listener = keyboard.Listener(on_press=on_key_press)
mouse_listener = mouse.Listener(on_click=on_click, on_scroll=on_scroll)


def start_activity_tracking():
    if not keyboard_listener.running:
        keyboard_listener.start()
    if not mouse_listener.running:
        mouse_listener.start()


def get_activity_snapshot(reset=True):
    global keyboard_count, mouse_clicks, scroll_events

    now = time.time()
    idle_seconds = int(now - last_activity_time)

    data = {
        "period_minutes": 5,
        "keystrokes": keyboard_count,
        "mouse_clicks": mouse_clicks,
        "mouse_distance_px": 0,
        "scroll_events": scroll_events,
        "idle_seconds": idle_seconds,
        "active_seconds": max(0, 300 - idle_seconds)
    }

    if reset:
        keyboard_count = 0
        mouse_clicks = 0
        scroll_events = 0

    return data