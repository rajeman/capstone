import json
from datetime import datetime, timezone

from agents import function_tool


@function_tool(name_override="getCurrentDateTime")
async def get_current_datetime() -> str:
    """Return the server's current date and time in UTC (ISO 8601). Call this when the user asks what time or date it is."""
    now = datetime.now(timezone.utc)
    return json.dumps(
        {
            "iso_utc": now.isoformat(),
            "unix_seconds": int(now.timestamp()),
        }
    )
