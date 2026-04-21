from datetime import datetime, timezone

from beanie import Document, Insert, Save, before_event


class TimestampedDocument(Document):
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @before_event(Insert)
    def _stamp_on_insert(self) -> None:
        now = datetime.now(timezone.utc)
        self.created_at = now
        self.updated_at = now

    @before_event(Save)
    def _touch_on_save(self) -> None:
        now = datetime.now(timezone.utc)
        if self.created_at is None:
            self.created_at = now
        self.updated_at = now
