"""JSON column type that safely serialises datetimes and other non-JSON values."""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON


def json_clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: json_clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_clean(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class SafeJSON(JSON):
    def bind_processor(self, dialect):
        def process(value: Any) -> Any:
            if value is None:
                return None
            return json.dumps(json_clean(value))

        return process
