from datetime import datetime, time
from zoneinfo import ZoneInfo
from config import TIMEZONE

STATE = {
    "last_refresh": None,
    "last_mode": "startup",
}

def get_refresh_mode(now=None):
    tz = ZoneInfo(TIMEZONE)
    now = now or datetime.now(tz)
    weekday = now.weekday()  # Mon=0, Sun=6
    hour = now.hour

    if weekday >= 5:
        return "weekend", 60

    # Major North American release window: 6:15–7:15 AM Mountain for many 8:30 ET releases.
    if (hour == 6 and now.minute >= 15) or (hour == 7 and now.minute <= 15):
        return "major_release_window", 1

    # Active market hours roughly 7:30 AM–2 PM Mountain.
    if (hour > 7 or (hour == 7 and now.minute >= 30)) and hour < 14:
        return "market_hours", 10

    return "off_hours", 30

def should_refresh(now=None):
    tz = ZoneInfo(TIMEZONE)
    now = now or datetime.now(tz)
    mode, interval_minutes = get_refresh_mode(now)
    last = STATE["last_refresh"]
    if last is None:
        STATE["last_refresh"] = now
        STATE["last_mode"] = mode
        return True, mode, interval_minutes

    elapsed = (now - last).total_seconds() / 60
    if elapsed >= interval_minutes:
        STATE["last_refresh"] = now
        STATE["last_mode"] = mode
        return True, mode, interval_minutes
    return False, mode, interval_minutes

def adaptive_status():
    mode, interval = get_refresh_mode()
    last = STATE.get("last_refresh")
    last_text = last.strftime("%Y-%m-%d %H:%M:%S") if last else "not yet"
    return f"""⚙️ Adaptive Intelligence Engine

Current mode:
{mode}

Target refresh interval:
Every {interval} minute(s)

Last refresh:
{last_text}

Plain English:
The bot checks more often during important market periods and less often during quiet periods."""
