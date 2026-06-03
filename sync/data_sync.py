import requests
from config import MAIN_BACKEND_URL


def send_device_info(token, payload):
    return requests.post(
        f"{MAIN_BACKEND_URL}/api/wfh/device-info",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=20
    ).json()


def send_activity(token, payload):
    return requests.post(
        f"{MAIN_BACKEND_URL}/api/wfh/activity",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=20
    ).json()


def send_screenshot(token, payload):
    return requests.post(
        f"{MAIN_BACKEND_URL}/api/wfh/screenshot",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=20
    ).json()


def send_productivity(token, payload):
    return requests.post(
        f"{MAIN_BACKEND_URL}/api/wfh/productivity",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=20
    ).json()


def send_app_usage(token, payload):
    return requests.post(
        f"{MAIN_BACKEND_URL}/api/wfh/app-usage",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=20
    ).json()