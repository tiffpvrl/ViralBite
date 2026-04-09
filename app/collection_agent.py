"""
Step 1 (Collect): LangChain `@tool` wraps `collect_youtube_data`. A Vertex model issues a
real tool call with `youtube_search_query` chosen from the user topic + optional creator
profile. Without Vertex, the same tool is invoked with a deterministic fallback query.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, tool
from langchain_google_vertexai import ChatVertexAI

from app.youtube_collector import collect_youtube_data

COLLECTION_SYSTEM_PROMPT = """You are a YouTube search strategist for ViralBite (food and creator research).

You have exactly one tool: `fetch_youtube_sample`. You MUST call it exactly once.

Choose `youtube_search_query` — a concise string for the YouTube Search API `q` parameter by considering:
- Reflect the user's TOPIC clearly.
- When CREATOR_PROFILE is non-empty, bias the query toward that niche (audience, format, tone).
  Example: topic "breakfast ideas" + profile "kids vlogs" → prefer "breakfast ideas for kids" as the query
  as opposed to "breakfast ideas for adults".
  - Make sure you are reasoning through what the TOPIC vs the PROFILE is. If the TOPIC is already related to the PROFILE,
  then it is probably better to use the TOPIC as the query.
  Example: topic "matcha latte" + profile "asian recipes" → prefer "matcha latte" as the query.
- When CREATOR_PROFILE is empty, use a strong topic-focused query without inventing a profile.
- Stay concise (roughly under 100 characters). No surrounding quotes in the argument value.

Do not call any tool twice. Do not fabricate video statistics — the tool fetches real data."""


def _collection_model_name() -> str:
    return os.getenv("VERTEXAI_COLLECTION_MODEL") or os.getenv("VERTEXAI_CHAT_MODEL") or os.getenv(
        "VERTEXAI_MODEL", "gemini-2.5-flash"
    )


def _fallback_youtube_query(topic: str, creator_profile: str) -> str:
    t = (topic or "").strip()
    p = (creator_profile or "").strip()
    if not p:
        return t
    combined = f"{t} {p}"
    return combined[:200]


def build_collection_tool(
    max_results: int,
    max_comments_per_video: int,
    order: str,
    window_days: int,
    capture: Dict[str, Any],
) -> Tuple[List[BaseTool], Dict[str, BaseTool]]:
    """Single tool that runs `collect_youtube_data` and stores full videos in `capture`."""

    @tool
    def fetch_youtube_sample(youtube_search_query: str) -> str:
        """Fetch a sample of YouTube videos using this search string (YouTube API `q`). Returns JSON metadata; full rows are stored for the pipeline."""
        q = (youtube_search_query or "").strip() or capture.get("fallback_query", "")
        capture["effective_youtube_query"] = q
        videos = collect_youtube_data(
            query=q,
            max_results=max_results,
            max_comments_per_video=max_comments_per_video,
            fetch_comments=True,
            order=order,
            window_days=window_days,
        )
        capture["videos"] = videos
        return json.dumps(
            {
                "youtube_search_query": q,
                "videos_returned": len(videos),
                "message": "Sample stored for EDA.",
            },
            default=str,
        )

    tools = [fetch_youtube_sample]
    by_name = {t.name: t for t in tools}
    return tools, by_name


def run_collection_with_tool_calling_agent(
    topic: str,
    creator_profile: str,
    max_results: int,
    max_comments_per_video: int,
    order: str,
    window_days: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Returns (videos, collection_meta_extra).

    `collection_meta_extra` includes `effective_youtube_query` and `user_topic`.
    """
    profile = (creator_profile or "").strip()
    fallback_q = _fallback_youtube_query(topic, profile)

    capture: Dict[str, Any] = {
        "videos": [],
        "effective_youtube_query": None,
        "fallback_query": fallback_q,
    }
    tools, by_name = build_collection_tool(
        max_results=max_results,
        max_comments_per_video=max_comments_per_video,
        order=order,
        window_days=int(window_days) if window_days is not None else 30,
        capture=capture,
    )

    project = os.getenv("GOOGLE_CLOUD_PROJECT")

    if not project:
        tool_fn = by_name["fetch_youtube_sample"]
        tool_fn.invoke({"youtube_search_query": fallback_q})
        videos = capture.get("videos") or []
        return videos, {
            "effective_youtube_query": capture.get("effective_youtube_query") or fallback_q,
            "user_topic": topic,
            "creator_profile_used": profile,
            "collection_tool_mode": "deterministic_fallback",
        }

    llm = ChatVertexAI(
        model_name=_collection_model_name(),
        temperature=0.2,
        project=project,
    )
    llm_t = llm.bind_tools(tools)

    human_lines = [
        f"TOPIC: {topic}",
        f"CREATOR_PROFILE: {profile if profile else 'Not provided — use topic only.'}",
    ]
    messages = [
        SystemMessage(content=COLLECTION_SYSTEM_PROMPT),
        HumanMessage(content="\n".join(human_lines)),
    ]

    response = llm_t.invoke(messages)

    if getattr(response, "tool_calls", None):
        for tc in response.tool_calls:
            name = tc["name"]
            if name not in by_name:
                continue
            args = tc.get("args") or {}
            by_name[name].invoke(args)

    if not capture.get("videos"):
        by_name["fetch_youtube_sample"].invoke({"youtube_search_query": fallback_q})

    videos = capture.get("videos") or []
    effective = capture.get("effective_youtube_query") or fallback_q

    return videos, {
        "effective_youtube_query": effective,
        "user_topic": topic,
        "creator_profile_used": profile,
        "collection_tool_mode": "vertex_tool_call",
    }
