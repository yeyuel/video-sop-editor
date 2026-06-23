from __future__ import annotations

import json


def loads_str_list(value: str) -> list[str]:
    if not value:
        return []
    return list(json.loads(value))


def loads_float_list(value: str) -> list[float]:
    if not value:
        return []
    return [float(item) for item in json.loads(value)]


def dumps_list(value: list[str] | list[float]) -> str:
    return json.dumps(value, ensure_ascii=False)
