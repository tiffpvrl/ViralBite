import copy
import os
import threading
import time

from app.graph import build_graph
from app.report_formatter import format_report

_CACHE_LOCK = threading.Lock()
_ANALYSIS_CACHE: dict[tuple, tuple[float, dict]] = {}
_CACHE_TTL_SECONDS = int(os.getenv("VIRALBITE_CACHE_TTL_SECONDS", "600"))


def run_topic_analysis(
    query: str,
    window_days: int = 30,
    max_results: int = 35,
    order: str = "viewCount",
    max_pages: int = 2,
    max_comments_per_video: int = 10,
) -> dict:
    cache_key = (
        query.strip().lower(),
        int(window_days),
        int(max_results),
        order,
        int(max_pages),
        int(max_comments_per_video),
    )
    now = time.time()
    with _CACHE_LOCK:
        cached = _ANALYSIS_CACHE.get(cache_key)
        if cached:
            cached_at, payload = cached
            if now - cached_at < _CACHE_TTL_SECONDS:
                return copy.deepcopy(payload)

    graph = build_graph()
    state = graph.invoke(
        {
            "query": query,
            "window_days": window_days,
            "max_results": max_results,
            "order": order,
            "max_pages": max_pages,
            "max_comments_per_video": max_comments_per_video,
        }
    )
    analysis = state.get("analysis", {})
    final_response = state.get("final_response", {})
    report = format_report(query, analysis, final_response)

    result = {
        "query": query,
        "analysis": analysis,
        "final_response": final_response,
        "report": report,
    }
    with _CACHE_LOCK:
        _ANALYSIS_CACHE[cache_key] = (now, copy.deepcopy(result))
    return result

def build_homepage_cards(topics: list[str]) -> list[dict]:
    return [
        {"topic": topic, "window": "weekly", "source": "hardcoded_demo"}
        for topic in topics
    ]