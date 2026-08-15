"""Simple in-process event bus for domain events."""
from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("app.events")

Handler = Callable[["DomainEvent"], Awaitable[None]]


@dataclass
class DomainEvent:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Handler) -> None:
        self._subscribers[event_type].append(handler)

    def subscribe_many(self, handlers: dict[str, list[Handler]]) -> None:
        for event_type, handlers_list in handlers.items():
            for h in handlers_list:
                self.subscribe(event_type, h)

    async def publish(self, event: DomainEvent) -> None:
        for handler in self._subscribers.get(event.type, []):
            try:
                await handler(event)
            except Exception:  # noqa: BLE001 - handlers must not break the bus
                logger.exception(
                    "event handler failed", extra={"event_type": event.type}
                )

    async def publish_all(self, events: list[DomainEvent]) -> None:
        for event in events:
            await self.publish(event)


bus = EventBus()
