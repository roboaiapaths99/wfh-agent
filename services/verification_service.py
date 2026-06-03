import random
import time
import logging

logger = logging.getLogger(__name__)

# A pre-defined bank of standard, simple, non-intrusive questions
QUESTION_BANK = [
    "What project task or milestone are you currently working on?",
    "Could you write a brief summary (1 sentence) of your recent activity?",
    "Are you currently in a meeting, brainstorming, or writing code?",
    "Which document or ticket are you reviewing at the moment?",
    "Quick sync check: Are you blocked by any pending reviews or tasks?",
]

# Simple in-memory tracker for the active challenge
active_challenge = {
    "question": None,
    "triggered_at": 0,
    "status": "idle", # idle, pending, responded, timeout
}

def generate_random_question() -> dict:
    """
    Triggers a new random question challenge.
    """
    question = random.choice(QUESTION_BANK)
    now = time.time()
    
    active_challenge["question"] = question
    active_challenge["triggered_at"] = now
    active_challenge["status"] = "pending"
    
    return {
        "status": "pending",
        "question": question,
        "triggered_at": now,
        "timeout_seconds": 120 # Employee has 2 minutes to respond
    }

def submit_challenge_response(answer: str) -> dict:
    """
    Submits response to the pending question challenge.
    """
    now = time.time()
    if active_challenge["status"] != "pending":
        return {
            "status": "error",
            "message": f"No active challenge in pending state. Current status: {active_challenge['status']}"
        }
        
    latency = now - active_challenge["triggered_at"]
    if latency > 120:
        active_challenge["status"] = "timeout"
        return {
            "status": "timeout",
            "message": "Challenge response timed out (exceeded 120s limit)",
            "latency_seconds": latency
        }
        
    active_challenge["status"] = "responded"
    return {
        "status": "success",
        "message": "Challenge response received",
        "latency_seconds": round(latency, 2),
        "answer": answer
    }

def get_current_challenge_status() -> dict:
    """
    Returns the active challenge metadata.
    """
    now = time.time()
    # Check for timeout dynamically
    if active_challenge["status"] == "pending" and (now - active_challenge["triggered_at"]) > 120:
        active_challenge["status"] = "timeout"
        
    return {
        "status": active_challenge["status"],
        "question": active_challenge["question"],
        "triggered_at": active_challenge["triggered_at"],
        "time_elapsed": round(now - active_challenge["triggered_at"], 1) if active_challenge["triggered_at"] > 0 else 0
    }
