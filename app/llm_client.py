import json
import os
from typing import Any, Dict, List

from pydantic import BaseModel, Field
from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage


def _creator_model_name() -> str:
    return os.getenv("VERTEXAI_CREATOR_MODEL") or os.getenv("VERTEXAI_MODEL", "gemini-2.5-pro")


def _chat_model_name() -> str:
    return os.getenv("VERTEXAI_CHAT_MODEL") or os.getenv("VERTEXAI_MODEL", "gemini-2.5-flash")


class CreatorBrief(BaseModel):
    opportunity_statement: str = Field(
        description=(
            "1–2 sentences: why this topic is worth a video now, combining upload trend and engagement. "
            "Name the type of opportunity (e.g. growing but not saturated vs unmet demand)."
        )
    )
    video_concept: str = Field(
        description=(
            "One concrete, filmable idea: working title + premise + structure. Not a generic category."
        )
    )
    production_brief: str = Field(
        description=(
            "Tactical production guidance as short paragraphs and/or lines starting with '- ' for bullets. "
            "Cover ideal length range, title/thumbnail/hook, comment cues, and how to integrate sponsorship or "
            "brand placement (timing in the video, pacing, disclosure, brand-category fit). "
            "Never tell the creator to avoid sponsorship or to avoid sponsor language."
        )
    )
    differentiation_angle: str = Field(
        description=(
            "What is saturated in top titles and one specific twist or white-space angle to stand out."
        )
    )


class CommentThemeOutput(BaseModel):
    themes: List[str]


class CreatorBriefIdeas(BaseModel):
    ideas: List[CreatorBrief] = Field(
        description="Exactly two distinct brief ideas tailored to this creator and topic."
    )


def _build_fallback_idea(
    analysis: Dict[str, Any],
    creator_profile: str,
    mode: str,
) -> Dict[str, Any]:
    topic = analysis.get("topic") or "this topic"
    summary = analysis.get("summary", {})
    sponsorship = analysis.get("sponsorship", {})
    duration = analysis.get("duration_patterns", [])
    keywords = analysis.get("keyword_patterns", [])
    upload_trend = analysis.get("upload_trend", {})
    confidence = analysis.get("brief_confidence", {})
    top_videos = analysis.get("top_videos", [])[:5]

    n = int(summary.get("num_videos", 0) or 0)
    avg_eng = float(summary.get("avg_engagement_rate", 0) or 0)
    best_duration = max(duration, key=lambda x: x.get("avg_engagement_rate", 0.0), default={})
    best_keyword = max(keywords, key=lambda x: x.get("avg_engagement_rate", 0.0), default={})

    pct = upload_trend.get("pct_change_vs_prior_half")
    trend_note = (
        f"Upload pace in the recent half of the window is about {pct}% vs the prior half."
        if pct is not None
        else "Upload trend is flat or not computable from the weekly buckets."
    )

    creator_note = (
        f" Tailor this to creator context: {creator_profile}."
        if creator_profile
        else ""
    )

    opp = (
        f"Across {n} long-form videos on “{topic}”, average engagement is about {avg_eng:.4f}. "
        f"{trend_note} "
        f"The strongest duration bucket in this sample is {best_duration.get('duration_bucket', '1-3m')} "
        f"by engagement rate — use that as a starting length range.{creator_note}"
    )

    titles_preview = ", ".join(
        (v.get("title") or "")[:48] for v in top_videos[:3] if v.get("title")
    ) or "top titles in the sample"

    if mode == "format_flip":
        concept = (
            f"Pilot: “I tested 3 ways to do {topic} and only one actually worked.” "
            f"Use a challenge arc (promise → tests → winner). Inspired by: {titles_preview}."
        )
    else:
        concept = (
            f"Pilot: “I ranked {topic} spots by [one specific criterion] — here is the honest order.” "
            f"Build a clear arc (intro hook → locations → verdict). Inspired by: {titles_preview}."
        )

    bucket = best_duration.get("duration_bucket", "1-3m")
    prod_lines = [
        f"- Start from the {bucket} duration bucket (strongest avg engagement in this sample of {n} videos); adjust for your format.",
        f"- Test titles using the keyword “{best_keyword.get('keyword', 'best')}” if it fits your angle.",
    ]
    if sponsorship.get("sponsored_avg_views", 0) > sponsorship.get("organic_avg_views", 0):
        prod_lines.append(
            "- Sponsored reads in the sample skew higher on views; place your sponsor block after the first payoff, "
            "then echo the brand at a natural mid-roll beat."
        )
    else:
        prod_lines.append(
            "- Plan sponsorship like a segment: hook with value first, then a clear mid-roll brand beat with disclosure, "
            "and a light callback near the outro if the deal allows."
        )
    if confidence.get("message"):
        prod_lines.append(f"- Note: {confidence['message']}")
    if creator_profile:
        prod_lines.append(
            f"- Creator fit: adapt tone/examples to this channel profile: {creator_profile}."
        )

    if mode == "format_flip":
        diff = (
            "Most top titles compete on list/ranking framing. Differentiate with a test-lab format: "
            "same topic, multiple approaches, one winner with explicit scoring."
        )
    else:
        diff = (
            "If many top titles repeat generic ranking language, differentiate with a POV flip "
            "(parent-with-kids lens, budget lens, or time-crunched lens)."
        )

    return {
        "opportunity_statement": opp,
        "video_concept": concept,
        "production_brief": "\n".join(prod_lines),
        "differentiation_angle": diff,
    }


def _fallback_creator_brief(analysis: Dict[str, Any], creator_profile: str = "") -> Dict[str, Any]:
    return {
        "ideas": [
            _build_fallback_idea(analysis, creator_profile, mode="ranked"),
            _build_fallback_idea(analysis, creator_profile, mode="format_flip"),
        ]
    }


def generate_creator_brief(analysis: Dict[str, Any], creator_profile: str = "") -> Dict[str, Any]:
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        return _fallback_creator_brief(analysis, creator_profile=creator_profile)

    try:
        llm = ChatVertexAI(
            model_name=_creator_model_name(),
            temperature=0.4,
            project=project,
        )
        structured_llm = llm.with_structured_output(CreatorBriefIdeas)

        system_instructions = """You are a YouTube content strategist who has studied thousands of food and creator videos. You think like a creative director, not an analyst. Your job is to give ONE creator TWO clear directions they could film tomorrow — not a vague report.

Ground everything in the ANALYSIS_JSON. Never give generic YouTube advice. Every sentence in your output must tie to a specific number, label, title pattern, keyword, sentiment theme, or trend from the data. If something is not in the data, say what is missing instead of guessing.

You will also get CREATOR_PROFILE. Adapt format, tone, pacing, and examples to that creator profile (niche, audience size, family-safe constraints, etc.).

Return JSON with an ideas array of EXACTLY 2 objects. Each object must include these four fields:
1) opportunity_statement — Why this topic is worth a video now, using upload_trend + engagement + sample size signals. Wrap key metrics in **double asterisks** (e.g. **5.8%**, **3300%**) so they scan easily.
2) video_concept — Specific working title + premise + beats (not “make a ranking video”). Start lines with labels like "Working Title:", "Premise:", "Structure:" when possible; use numbered steps under Structure. Bold important numbers.
3) production_brief — Tactical: length range from duration buckets/engagement curve signals, title patterns from top videos, hook patience vs avg length, comment themes as unanswered demand, and sponsor vs organic stats if present. Always include practical guidance for sponsorship or brand placement when relevant: where in runtime to place reads, how to bridge from content to brand, disclosure placement, and suitable brand categories. Never advise avoiding sponsorship or avoiding sponsor language.
4) differentiation_angle — What is repeated in top titles and one concrete twist.

The 2 ideas must be materially different in angle and structure (not minor wording variants).

The brief_confidence object is shown separately in the UI — do not repeat its disclaimer verbatim; focus on actionable insight."""

        human_payload = (
            f"CREATOR_PROFILE:\n{creator_profile or 'Not provided'}\n\n"
            f"ANALYSIS_JSON:\n{json.dumps(analysis, default=str)}"
        )

        parsed = structured_llm.invoke(
            [SystemMessage(content=system_instructions), HumanMessage(content=human_payload)]
        )
        ideas = [idea.model_dump() for idea in parsed.ideas if idea]
        if len(ideas) >= 2:
            return {"ideas": ideas[:2]}
        fallback = _fallback_creator_brief(analysis, creator_profile=creator_profile)
        existing = ideas + fallback.get("ideas", [])
        return {"ideas": existing[:2]}
    except Exception as e:
        print(f"Vertex AI Error: {e}")
        return _fallback_creator_brief(analysis, creator_profile=creator_profile)


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
