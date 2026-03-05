from datetime import datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

def to_ny(dt: datetime) -> datetime:
    """Convert a datetime (naive or UTC) to America/New_York."""
    if dt.tzinfo is None:
        # If naive, assume it's UTC (standard for this DB)
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(NY_TZ)

def get_ny_now() -> datetime:
    """Get current time in New York."""
    return datetime.now(NY_TZ)
