from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class EventRecord:
    user_id: str
    event_name: str
    timestamp: datetime
    session_id: Optional[str] = None
    url: Optional[str] = None
    language: Optional[str] = None
    user_agent: Optional[str] = None
    screen_width: Optional[int] = None
    screen_height: Optional[int] = None


@dataclass
class UserRecord:
    user_id: str
    event_count: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    session_count: int = 0
    total_duration: float = 0.0
    is_churned: bool = False


@dataclass
class SessionRecord:
    session_id: str
    user_id: str
    event_count: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    bounced: bool = False
    pages_viewed: int = 0


@dataclass
class FunnelRecord:
    funnel_name: str
    date: datetime
    step_order: int
    step_name: str
    count: int = 0
    conversion_rate: float = 0.0
