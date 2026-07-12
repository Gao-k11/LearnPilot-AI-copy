from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator


def dumps_unicode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def loads_unicode(value: str | bytes | bytearray | dict | list | None) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


class UnicodeJSONType(TypeDecorator):
    """Persist JSON as UTF-8 text with ensure_ascii=False."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect) -> str | None:
        if value is None:
            return None
        return dumps_unicode(value)

    def process_result_value(self, value: str | bytes | bytearray | dict | list | None, dialect) -> Any:
        return loads_unicode(value)
