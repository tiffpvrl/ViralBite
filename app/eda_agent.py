"""
Option B (course rubric): exploratory data analysis runs only through LangChain `@tool`
callables. The analyst model must invoke these tools (or we deterministically invoke
the same tools when Vertex is unavailable).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, tool
from langchain_google_vertexai import ChatVertexAI

from app.analysis_tools import (
    analyze_comment_sentiment,
    analyze_duration_patterns,
    analyze_keyword_patterns,
    analyze_sponsorship,
    analyze_top_videos,
    analyze_upload_frequency,
    compute_brief_confidence,
    summarize_dataset,
    summarize_upload_trend,
    videos_to_dataframe,
)

EDA_KEYWORDS: List[str] = [
    "cheap",
    "best",
    "authentic",
    "hidden",
    "local",
    "ranking",
    "review",
    "vs",
    "worth it",
    "street food",
    "food tour",
    "honest",
]

EDA_SYSTEM_PROMPT = """You are the EDA (exploratory data analysis) specialist for ViralBite.

You MUST call every tool available to you exactly once. Each tool analyzes the same
already-collected YouTube video sample (you do not pass raw data — the tools read the
session sample internally).

Do not skip tools. Do not fabricate numbers — tools compute metrics from data.
After you have invoked all tools once, stop."""


def _eda_model_name() -> str:
    return os.getenv("VERTEXAI_EDA_MODEL") or os.getenv("VERTEXAI_CHAT_MODEL") or os.getenv(
        "VERTEXAI_MODEL", "gemini-2.0-flash"
    )


def _tool_json(payload: Any) -> str:
    return json.dumps(payload, default=str)


def build_eda_tools(videos: List[Dict[str, Any]]) -> Tuple[List[BaseTool], Dict[str, BaseTool]]:
    """Create LangChain tools that close over `videos`; EDA reads only from this sample."""

    @tool
    def eda_summary_metrics() -> str:
        """Aggregate stats (views, engagement, duration) for the long-form video sample."""
        df, duration_filter = videos_to_dataframe(videos)
        summary = summarize_dataset(df)
        return _tool_json({"summary": summary, "duration_filter": duration_filter})

    @tool
    def eda_duration_patterns() -> str:
        """Engagement and counts grouped by duration bucket (1–3m, 3–10m, 10m+)."""
        df, _ = videos_to_dataframe(videos)
        return _tool_json(analyze_duration_patterns(df))

    @tool
    def eda_upload_and_trend() -> str:
        """Weekly upload counts and half-window trend (accelerating vs cooling)."""
        df, _ = videos_to_dataframe(videos)
        upload_frequency = analyze_upload_frequency(df)
        upload_trend = summarize_upload_trend(upload_frequency)
        return _tool_json({"upload_frequency": upload_frequency, "upload_trend": upload_trend})

    @tool
    def eda_keyword_patterns() -> str:
        """Keyword lift in titles, descriptions, tags, and transcripts (top by engagement)."""
        df, _ = videos_to_dataframe(videos)
        return _tool_json(
            analyze_keyword_patterns(df, EDA_KEYWORDS, top_n=8)
        )

    @tool
    def eda_comment_sentiment() -> str:
        """VADER sentiment mix on fetched comments plus simple token themes."""
        df, _ = videos_to_dataframe(videos)
        return _tool_json(analyze_comment_sentiment(df))

    @tool
    def eda_sponsorship() -> str:
        """Sponsored vs organic titles/descriptions and average views/engagement."""
        df, _ = videos_to_dataframe(videos)
        return _tool_json(analyze_sponsorship(df))

    @tool
    def eda_top_videos() -> str:
        """Top 5 videos in the sample by view count with engagement and duration."""
        df, _ = videos_to_dataframe(videos)
        return _tool_json(analyze_top_videos(df, top_n=5))

    @tool
    def eda_brief_confidence() -> str:
        """Sample size / channel concentration signal for how much to trust downstream briefs."""
        df, _ = videos_to_dataframe(videos)
        return _tool_json(compute_brief_confidence(df))

    tools = [
        eda_summary_metrics,
        eda_duration_patterns,
        eda_upload_and_trend,
        eda_keyword_patterns,
        eda_comment_sentiment,
        eda_sponsorship,
        eda_top_videos,
        eda_brief_confidence,
    ]
    by_name = {t.name: t for t in tools}
    return tools, by_name


def merge_eda_tool_results(
    results_by_tool_name: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Turn tool-name → JSON payloads into the `analysis` fragment expected by the UI
    (minus topic + sample_definition).

    Returns (analysis_core, duration_filter_meta).
    """
    sm = results_by_tool_name.get("eda_summary_metrics") or {}
    if isinstance(sm, str):
        sm = json.loads(sm)
    summary = sm.get("summary") or {"error": "No videos found."}
    duration_filter = sm.get("duration_filter") or {}

    dur = results_by_tool_name.get("eda_duration_patterns")
    if isinstance(dur, str):
        dur = json.loads(dur)

    ut = results_by_tool_name.get("eda_upload_and_trend") or {}
    if isinstance(ut, str):
        ut = json.loads(ut)

    kw = results_by_tool_name.get("eda_keyword_patterns")
    if isinstance(kw, str):
        kw = json.loads(kw)

    sent = results_by_tool_name.get("eda_comment_sentiment") or {}
    if isinstance(sent, str):
        sent = json.loads(sent)

    sp = results_by_tool_name.get("eda_sponsorship")
    if isinstance(sp, str):
        sp = json.loads(sp)

    tv = results_by_tool_name.get("eda_top_videos")
    if isinstance(tv, str):
        tv = json.loads(tv)

    bc = results_by_tool_name.get("eda_brief_confidence")
    if isinstance(bc, str):
        bc = json.loads(bc)

    analysis_core = {
        "summary": summary,
        "duration_patterns": dur if dur is not None else [],
        "upload_frequency": ut.get("upload_frequency", []) if isinstance(ut, dict) else [],
        "upload_trend": ut.get("upload_trend", {}) if isinstance(ut, dict) else {},
        "brief_confidence": bc if isinstance(bc, dict) else {},
        "keyword_patterns": kw if kw is not None else [],
        "comment_sentiment": sent if isinstance(sent, dict) else {},
        "sponsorship": sp if isinstance(sp, dict) else {},
        "top_videos": tv if tv is not None else [],
    }
    return analysis_core, duration_filter


def _execute_all_tools_directly(tools: List[BaseTool]) -> Dict[str, Any]:
    """Invoke every EDA tool once via LangChain tool objects (no LLM)."""
    out: Dict[str, Any] = {}
    for t in tools:
        raw = t.invoke({})
        out[t.name] = json.loads(raw) if isinstance(raw, str) else raw
    return out


def run_eda_with_tool_calling_agent(videos: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Run Option-B EDA: metrics are produced only inside LangChain tools.

    When GOOGLE_CLOUD_PROJECT is set, a Vertex model issues tool calls (bind_tools).
    Otherwise we invoke the same tools deterministically so local dev still works.
    """
    tools, by_name = build_eda_tools(videos)
    project = os.getenv("GOOGLE_CLOUD_PROJECT")

    if not project:
        raw = _execute_all_tools_directly(tools)
        return merge_eda_tool_results(raw)

    llm = ChatVertexAI(
        model_name=_eda_model_name(),
        temperature=0,
        project=project,
    )
    llm_t = llm.bind_tools(tools)

    messages = [
        SystemMessage(content=EDA_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                "The collector has finished fetching YouTube videos for this topic. "
                "Perform EDA by calling each available tool exactly once."
            )
        ),
    ]

    response = llm_t.invoke(messages)

    raw: Dict[str, Any] = {}
    if getattr(response, "tool_calls", None):
        for tc in response.tool_calls:
            name = tc["name"]
            if name not in by_name:
                continue
            args = tc.get("args") or {}
            tool_fn = by_name[name]
            out = tool_fn.invoke(args)
            raw[name] = json.loads(out) if isinstance(out, str) else out

    expected = set(by_name.keys())
    got = set(raw.keys())
    if got != expected:
        missing = expected - got
        for name in missing:
            out = by_name[name].invoke({})
            raw[name] = json.loads(out) if isinstance(out, str) else out

    return merge_eda_tool_results(raw)
