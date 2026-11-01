"""Small shared helpers for the deterministic engines."""
from __future__ import annotations


def is_missing(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def band_lookup(bands, value):
    """bands = [(lo, hi, result)]; returns result or None."""
    for lo, hi, res in bands:
        if lo <= value <= hi:
            return res
    return None
