from __future__ import annotations

from typing import Any, Optional


def to_float(value: Any) -> Optional[float]:
    """Best-effort conversion of arbitrary price values to float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    if type(value).__name__ == "Decimal128" and hasattr(value, "to_decimal"):
        try:
            return float(value.to_decimal())
        except Exception:
            pass

    text = str(value).strip()
    if not text:
        return None

    cleaned = "".join(ch for ch in text if ch.isdigit() or ch in ".,")
    if not cleaned:
        return None
    cleaned = cleaned.replace(",", ".")

    try:
        return float(cleaned)
    except Exception:
        return None
