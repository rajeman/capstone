from datetime import datetime, timezone

from beanie import Document, Insert, Save, before_event


class TimestampedDocument(Document):
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Names must not start with "_" — Beanie's init_actions skips private attrs,
    # so before_event handlers on base classes would never run (see beanie.odm.utils.init).
    @before_event(Insert)
    def stamp_on_insert(self) -> None:
        now = datetime.now(timezone.utc)
        self.created_at = now
        self.updated_at = now

    @before_event(Save)
    def touch_on_save(self) -> None:
        now = datetime.now(timezone.utc)
        if self.created_at is None:
            self.created_at = now
        self.updated_at = now
