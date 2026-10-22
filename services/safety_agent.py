
from datetime import datetime, timezone, timedelta


def check_food_safety(category, prepared_at, now=None):
    now = now or datetime.now(timezone.utc)

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    try:
        prepared = datetime.fromisoformat(prepared_at)
        if prepared.tzinfo is None:
            prepared = prepared.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return {
            "safe": False,
            "status": "REJECTED_INVALID_TIME",
            "reason": "Preparation time is missing or invalid."
        }

    if prepared > now:
        return {
            "safe": False,
            "status": "REJECTED_INVALID_TIME",
            "reason": "Preparation time cannot be in the future."
        }

    if category.strip().lower() == "cooked meals":
        age = now - prepared
        if age > timedelta(hours=4):
            return {
                "safe": False,
                "status": "REJECTED_SAFETY_EXPIRED",
                "reason": "Cooked food is older than the 4-hour safety window."
            }

    return {
        "safe": True,
        "status": "SAFETY_CHECK_PASSED",
        "reason": "The configured time-window check passed. This is not a full food-safety certification."
    }
