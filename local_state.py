import json
import os

USER_HOME = os.path.expanduser("~")
LOGDAY_DIR = os.path.join(USER_HOME, ".logday-wfh")
os.makedirs(LOGDAY_DIR, exist_ok=True)
STATE_FILE = os.path.join(LOGDAY_DIR, "agent_state.json")


def save_state(data: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def clear_state():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)