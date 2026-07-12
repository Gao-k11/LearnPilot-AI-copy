from __future__ import annotations

import re

_CJK_RANGE = range(0x4E00, 0x9FFF + 1)

# High-frequency UTF-8-as-Latin-1 mojibake byte markers (as Unicode chars).
_MOJIBAKE_MARKERS = frozenset("ÃÂèåæçéä»¶·¥¨¤º½¯¼¾¿")

# Multi-byte mojibake sequences commonly seen when Chinese UTF-8 is misread.
_MOJIBAKE_SEQUENCES = re.compile(
    r"(?:Ã.|Â.|ä»|å¤|è½|ç¨|å·|é|æ¯|ä¸|å­|ç§|å·¥|ç¨|å¤§|äº)"
)


def has_cjk(value: str) -> bool:
    if not value or not isinstance(value, str):
        return False
    return any(ord(char) in _CJK_RANGE for char in value)


def looks_like_mojibake(value: str) -> bool:
    """Detect likely UTF-8-read-as-Latin-1 corruption without mutating the string."""
    if not value or not isinstance(value, str):
        return False
    if has_cjk(value):
        return False

    marker_count = sum(1 for char in value if char in _MOJIBAKE_MARKERS)
    if marker_count >= 2:
        return True
    if _MOJIBAKE_SEQUENCES.search(value):
        return True

    # Strong signal: Latin-1 round-trip would yield CJK (detection only, never applied).
    try:
        repaired = value.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return False
    return has_cjk(repaired)


def _as_text(value) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)


def choose_safe_text(
    existing,
    incoming,
    *,
    allow_clear: bool = False,
) -> str | None:
    """Pick the text value to persist; never auto-repair encoding."""
    existing_text = _as_text(existing).strip()
    incoming_text = _as_text(incoming).strip()

    if not incoming_text:
        if allow_clear:
            return ""
        return existing_text

    if not existing_text:
        return incoming_text

    incoming_bad = looks_like_mojibake(incoming_text)
    existing_bad = looks_like_mojibake(existing_text)
    existing_good = has_cjk(existing_text) and not existing_bad
    incoming_good = has_cjk(incoming_text) and not incoming_bad

    if incoming_bad and existing_good:
        return existing_text
    if existing_bad and incoming_good:
        return incoming_text
    if incoming_bad and not existing_bad:
        return existing_text

    return incoming_text


def _weak_point_items(value) -> list[str]:
    if not value:
        return []
    if not isinstance(value, list):
        return []
    return [_as_text(item).strip() for item in value if _as_text(item).strip()]


def _list_has_cjk(items: list[str]) -> bool:
    return any(has_cjk(item) and not looks_like_mojibake(item) for item in items)


def _list_looks_mojibake(items: list[str]) -> bool:
    if not items:
        return False
    bad_count = sum(1 for item in items if looks_like_mojibake(item))
    return bad_count >= max(1, len(items) // 2)


def choose_safe_weak_points(existing, incoming) -> list[str]:
    existing_items = _weak_point_items(existing)
    incoming_items = _weak_point_items(incoming)

    if not incoming_items:
        return existing_items

    if not existing_items:
        return incoming_items

    if _list_looks_mojibake(incoming_items) and _list_has_cjk(existing_items):
        return existing_items
    if _list_looks_mojibake(existing_items) and _list_has_cjk(incoming_items):
        return incoming_items

    return incoming_items


def choose_safe_mastery(existing, incoming) -> dict:
    if not isinstance(incoming, dict) or not incoming:
        return dict(existing) if isinstance(existing, dict) else {}

    base = dict(existing) if isinstance(existing, dict) else {}
    for key, value in incoming.items():
        key_text = _as_text(key)
        if isinstance(value, str):
            safe = choose_safe_text(base.get(key_text, ""), value)
            if safe is not None:
                base[key_text] = safe
        elif isinstance(value, dict):
            base[key_text] = choose_safe_mastery(base.get(key_text, {}), value)
        else:
            base[key_text] = value
    return base
