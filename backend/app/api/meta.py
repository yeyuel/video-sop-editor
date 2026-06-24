from __future__ import annotations


def merge_response_meta(llm_meta: dict[str, str] | None = None) -> dict[str, str]:
    meta: dict[str, str] = {"requestId": "local-dev"}
    if llm_meta:
        meta.update(llm_meta)
    return meta
