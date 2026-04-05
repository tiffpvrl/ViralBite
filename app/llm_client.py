import json
import os
from typing import Any, Dict, List

from pydantic import BaseModel, ValidationError
from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage


class CreatorBrief(BaseModel):
    summary: str
    recommendations: List[str]


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
            f"Sampled {summary.get('num_videos', 0)} videos. The strongest performance pattern "
            f"is concentrated in {best_duration.get('duration_bucket', 'mid-length')} videos with "
            f"keyword framing around '{best_keyword.get('keyword', 'best')}'."
        ),
        "recommendations": recommendations[:4],
    }


def generate_creator_brief(analysis: Dict[str, Any]) -> Dict[str, Any]:
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        return _fallback_creator_brief(analysis)

    try:
        llm = ChatVertexAI(
            model_name=os.getenv("VERTEXAI_MODEL", "gemini-2.5-flash"),
            temperature=0.4,
            project=project,
        )
        structured_llm = llm.with_structured_output(CreatorBrief)

        prompt = (
            "You are a YouTube food content analyst. You will receive structured data "
            "about a food topic. Write a creator brief with: (1) a 2-3 sentence summary "
            "of what patterns you found, (2) 3-4 specific actionable recommendations for "
            "a creator making a video on this topic. Be concrete and mention formats, "
            "title ideas, ideal length, and where to place a sponsor if relevant. "
            "Ground everything in the numbers provided.\n\n"
            f"ANALYSIS: {json.dumps(analysis)}"
        )

        parsed = structured_llm.invoke(prompt)
        return parsed.model_dump()
    except Exception as e:
        print(f"Vertex AI Error: {e}")
        return _fallback_creator_brief(analysis)


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
            model_name=os.getenv("VERTEXAI_MODEL", "gemini-1.5-flash"),
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
