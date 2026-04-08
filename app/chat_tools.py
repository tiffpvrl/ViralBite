"""
Chat tab: LangChain tools read only from the current dashboard payload (analysis + optional
brief). No YouTube re-fetch; answers are grounded via tool calls over structured JSON.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.tools import BaseTool, tool


def _j(payload: Any) -> str:
    return json.dumps(payload, default=str)


def _safe_sentiment(s: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(s) if s else {}
    out.pop("comment_samples", None)
    return out


def build_chat_analysis_tools(
    analysis: Dict[str, Any],
    final_response: Optional[Dict[str, Any]] = None,
) -> Tuple[List[BaseTool], Dict[str, BaseTool]]:
    """Tools close over `analysis` (and brief); no network I/O."""

    @tool
    def get_run_summary() -> str:
        """Overall sample stats: video count, views, engagement, dominant duration bucket, and brief_confidence."""
        payload = {
            "topic": analysis.get("topic"),
            "summary": analysis.get("summary") or {},
            "brief_confidence": analysis.get("brief_confidence") or {},
        }
        return _j(payload)

    @tool
    def get_duration_and_format_signals() -> str:
        """Engagement and video counts by duration bucket (1–3m, 3–10m, 10m+)."""
        return _j(analysis.get("duration_patterns") or [])

    @tool
    def get_upload_pace_and_trend() -> str:
        """Weekly upload counts and whether upload pace is accelerating, steady, or cooling."""
        return _j(
            {
                "upload_frequency": analysis.get("upload_frequency") or [],
                "upload_trend": analysis.get("upload_trend") or {},
            }
        )

    @tool
    def get_keyword_engagement_signals() -> str:
        """Keyword patterns with average engagement (titles, descriptions, tags, transcripts)."""
        return _j(analysis.get("keyword_patterns") or [])

    @tool
    def get_comment_sentiment_breakdown() -> str:
        """VADER sentiment mix and theme lists from comments in the sample."""
        return _j(_safe_sentiment(analysis.get("comment_sentiment") or {}))

    @tool
    def get_sponsorship_comparison() -> str:
        """Sponsored vs organic counts and average views/engagement in the sample."""
        return _j(analysis.get("sponsorship") or {})

    @tool
    def get_top_videos_by_views() -> str:
        """Top videos in the sample by view count with engagement and duration."""
        return _j(analysis.get("top_videos") or [])

    @tool
    def get_sample_and_search_context() -> str:
        """How this dataset was built: lookback window, YouTube search query used, duration filter, comment/transcript policy."""
        return _j(analysis.get("sample_definition") or {})

    @tool
    def get_creator_brief_ideas() -> str:
        """Structured creator brief ideas from the Brief ideas tab (if available for this run)."""
        if not final_response:
            return _j({"available": False, "message": "No brief payload in this session."})
        brief = final_response.get("creator_brief") or {}
        return _j({"available": True, "creator_brief": brief})

    tools = [
        get_run_summary,
        get_duration_and_format_signals,
        get_upload_pace_and_trend,
        get_keyword_engagement_signals,
        get_comment_sentiment_breakdown,
        get_sponsorship_comparison,
        get_top_videos_by_views,
        get_sample_and_search_context,
        get_creator_brief_ideas,
    ]
    return tools, {t.name: t for t in tools}
