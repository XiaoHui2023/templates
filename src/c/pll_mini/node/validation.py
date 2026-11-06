from __future__ import annotations


def normalized_choice(value: object, allowed: tuple[str, ...], field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    normalized = value.strip().lower()
    if normalized not in allowed:
        raise ValueError(f"{field} must be one of {allowed!r}; got {value!r}")
    return normalized
