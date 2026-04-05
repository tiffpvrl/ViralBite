import json
import os
from typing import Any, Dict, List

from pydantic import BaseModel
from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage


def _creator_model_name() -> str:
    return os.getenv("VERTEXAI_CREATOR_MODEL") or os.getenv("VERTEXAI_MODEL", "gemini-2.5-pro")


def _chat_model_name() -> str:
    return os.getenv("VERTEXAI_CHAT_MODEL") or os.getenv("VERTEXAI_MODEL", "gemini-2.5-flash")


class CreatorBrief(BaseModel):
    summary: str
    recommendations: List[str]


class CommentThemeOutput(BaseModel):
    themes: List[str]


def _fallback_creator_brief(analysis: Dict[str, Any]) -> Dict[str, Any]:
    summary = analysis.get("summary", {})
    sponsorship = analysis.get("sponsorship", {})
    duration = analysis.get("duration_patterns", [])
    keywords = analysis.get("keyword_patterns", [])

    best_duration = max(duration, key=lambda x: x.get("avg_engagement_rate", 0.0), default={})
    best_keyword = max(keywords, key=lambda x: x.get("avg_engagement_rate", 0.0), default={})

    recommendations = [
        (
            f"Use a comparison format with clear ranking verdicts around the "
            f"{best_duration.get('duration_bucket', '3-10m')} range."
        ),
        (
            f"Include high-signal language like '{best_keyword.get('keyword', 'best')}' "
            f"in the title and early hook."
        ),
    ]

    if sponsorship.get("sponsored_avg_views", 0) > sponsorship.get("organic_avg_views", 0):
        recommendations.append(
            "If using a sponsor, place the ad read after early value delivery (roughly mid-video)."
        )
    else:
        recommendations.append(
            "Prioritize an organic-feeling story arc and keep sponsor language minimal in the title."
        )

    return {
        "summary": (
            f"Comparison and ranking formats are the strongest pattern across this sample of "
            f"{summary.get('num_videos', 0)} videos. The best-performing length bucket is "
            f"{best_duration.get('duration_bucket', '3-10m')}, and high-engagement videos often "
            f"use keywords like '{best_keyword.get('keyword', 'best')}'."
        ),
        "recommendations": recommendations[:4],
    }


def generate_creator_brief(analysis: Dict[str, Any]) -> Dict[str, Any]:
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        return _fallback_creator_brief(analysis)

    try:
        llm = ChatVertexAI(
            model_name=_creator_model_name(),
            temperature=0.4,
            project=project,
        )
        structured_llm = llm.with_structured_output(CreatorBrief)

        prompt = f"""
You are a YouTube food content strategist writing creator briefs.

Return JSON with this exact schema:
- summary: string
- recommendations: string[] (exactly 4 items)

Style and structure requirements:
1) Summary should read like a confident analyst paragraph, 3-4 sentences.
2) Mention: dominant format pattern, ideal length range, sponsored vs organic nuance, and strong keywords.
3) Recommendations must be specific and tactical (title framing, structure, duration, sponsor placement, opening hook).
4) Ground claims in the numbers from analysis; do not invent metrics.

Few-shot style example (for tone only):
Summary:
"Comparison and ranking formats ('I tried every X,' '$A vs $B') are the dominant pattern among top-performing NYC bagel videos. The sweet spot is 8-14 minutes, long enough for multiple locations but short enough to hold attention. Organic, personality-driven content outperforms sponsored posts by engagement rate, but sponsored videos reach wider audiences. Keywords like 'best,' 'hidden,' and 'authentic' consistently appear in high-engagement titles."

Recommendations:
- "Title your video like: 'I ranked every famous NYC bagel shop - here is the honest truth.' Use 'best' or 'hidden' in title text."
- "Aim for 10-14 minutes. Cover 6-8 locations, spend about 90 seconds per location, and give clear verdicts."
- "Place sponsor read around the 5-minute mark between locations after early value is delivered."
- "Open with a hook that compares two extremes (cheapest vs most famous) to pull in comparison-content viewers."

ANALYSIS JSON:
{json.dumps(analysis)}
"""

        parsed = structured_llm.invoke(prompt)
        return parsed.model_dump()
    except Exception as e:
        print(f"Vertex AI Error: {e}")
        return _fallback_creator_brief(analysis)


def extract_comment_themes_llm(comments: List[str]) -> List[str]:
    if not comments:
        return []

    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        return []

    sampled = [c.strip()[:350] for c in comments if c and c.strip()][:80]
    if not sampled:
        return []

    try:
        llm = ChatVertexAI(
            model_name=os.getenv("VERTEXAI_THEME_MODEL", "gemini-1.5-flash"),
            temperature=0.2,
            project=project,
        )
        structured_llm = llm.with_structured_output(CommentThemeOutput)
        prompt = (
            "You are analyzing YouTube comment text for topic themes. "
            "Return 3 concise noun-phrase themes (2-5 words each), ranked by salience. "
            "Avoid sentiment words like 'good' or 'bad'. Focus on concrete topics. "
            "Return JSON only.\n\n"
            f"COMMENTS: {json.dumps(sampled)}"
        )
        parsed = structured_llm.invoke(prompt)
        return [theme for theme in parsed.themes[:3] if theme]
    except Exception:
        return []


def chat_with_analysis_context(
    topic: str,
    analysis: Dict[str, Any],
    history: List[Dict[str, str]],
    message: str,
) -> str:
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        return (
            "Chat is running in fallback mode because GOOGLE_CLOUD_PROJECT is not set. "
            "I can still summarize: ask about top videos, duration patterns, sponsorship, "
            "or creator recommendations."
        )

    try:
        llm = ChatVertexAI(
            model_name=_chat_model_name(),
            temperature=0.3,
            project=project,
        )

        messages = [
            SystemMessage(content=(
                "You are ViralBite, a creator strategy assistant. Answer only using the provided "
                "analysis context for the topic. If information is missing, say so clearly and "
                "suggest what metric would help. Keep answers concise and practical.\n\n"
                f"TOPIC: {topic}\n"
                f"ANALYSIS_JSON: {json.dumps(analysis)}"
            ))
        ]

        for item in history:
            role = item.get("role")
            content = item.get("content", "")
            if role == "user" and content:
                messages.append(HumanMessage(content=content))
            elif role == "assistant" and content:
                messages.append(AIMessage(content=content))

        messages.append(HumanMessage(content=message))

        response = llm.invoke(messages)
        return str(response.content) if response.content else ""
    except Exception as e:
        print(f"Vertex AI Chat Error: {e}")
        return "I'm having trouble connecting to Vertex AI right now."
