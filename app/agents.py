from app.collection_agent import run_collection_with_tool_calling_agent
from app.eda_agent import run_eda_with_tool_calling_agent
from app.llm_client import generate_creator_brief, extract_comment_themes_llm


def collector_node(state):
    """
    Step 1 (Collect): LangChain tool `fetch_youtube_sample` runs the YouTube API.
    With Vertex, the model chooses `youtube_search_query` from topic + creator_profile.
    """
    query = state["query"]
    creator_profile = (state.get("creator_profile") or "").strip()
    max_results = int(state.get("max_results", 25))
    max_comments_per_video = int(state.get("max_comments_per_video", 10))
    order = state.get("order", "viewCount")
    window_days = state.get("window_days", 30)

    videos, collect_extra = run_collection_with_tool_calling_agent(
        topic=query,
        creator_profile=creator_profile,
        max_results=max_results,
        max_comments_per_video=max_comments_per_video,
        order=order,
        window_days=window_days,
    )

    videos_with_comments = sum(1 for video in videos if video.get("top_comments"))
    videos_with_transcript = sum(1 for video in videos if (video.get("transcript_text") or "").strip())
    collection_meta = {
        "max_results": max_results,
        "max_comments_per_video": max_comments_per_video,
        "order": order,
        "window_days": int(window_days) if window_days is not None else None,
        "fetched_videos": len(videos),
        "videos_with_comments": videos_with_comments,
        "videos_with_transcript": videos_with_transcript,
        "effective_youtube_query": collect_extra.get("effective_youtube_query"),
        "user_topic": collect_extra.get("user_topic", query),
        "creator_profile_used": collect_extra.get("creator_profile_used", creator_profile),
        "collection_tool_mode": collect_extra.get("collection_tool_mode"),
    }

    return {"videos": videos, "collection_meta": collection_meta}


def analyst_node(state):
    """
    Step 2 (EDA): all tabular exploratory metrics are computed only inside LangChain tools
    (`app/eda_agent.py`). The analyst LLM issues tool calls when Vertex is configured;
    otherwise the same tools are invoked deterministically.
    """
    videos = state["videos"]
    collection_meta = state.get("collection_meta", {})

    analysis_core, duration_filter = run_eda_with_tool_calling_agent(videos)

    sentiment = analysis_core.get("comment_sentiment") or {}
    llm_themes = extract_comment_themes_llm(sentiment.get("comment_samples", []))
    if llm_themes:
        sentiment["top_positive_themes"] = llm_themes
        sentiment["top_negative_themes"] = []
    sentiment.pop("comment_samples", None)

    analysis = {
        "topic": state["query"],
        **analysis_core,
        "comment_sentiment": sentiment,
        "sample_definition": {
            "window_days": collection_meta.get("window_days"),
            "order": collection_meta.get("order", "viewCount"),
            "fetched_videos": collection_meta.get("fetched_videos", len(videos)),
            "videos_analyzed": duration_filter.get("videos_analyzed", 0),
            "min_duration_seconds_threshold": duration_filter.get("min_duration_seconds_threshold"),
            "excluded_not_longer_than_threshold": duration_filter.get(
                "excluded_not_longer_than_threshold", 0
            ),
            "effective_youtube_query": collection_meta.get("effective_youtube_query"),
            "user_topic": collection_meta.get("user_topic"),
            "creator_profile_used": collection_meta.get("creator_profile_used"),
            "videos_with_comments": collection_meta.get("videos_with_comments", 0),
            "videos_with_transcript": collection_meta.get("videos_with_transcript", 0),
            "comment_policy": (
                f"Up to {collection_meta.get('max_comments_per_video', 0)} top comments "
                f"per video on {collection_meta.get('videos_with_comments', 0)} videos."
            ),
            "transcript_policy": (
                f"Transcript enrichment available on {collection_meta.get('videos_with_transcript', 0)} videos "
                "when public captions are accessible."
            ),
        },
    }

    return {"analysis": analysis}


def insight_node(state):
    analysis = state["analysis"]
    creator_profile = (state.get("creator_profile") or "").strip()
    creator_brief = generate_creator_brief(analysis, creator_profile=creator_profile)

    final_response = {
        "summary": analysis["summary"],
        "creator_brief": creator_brief,
        "brief_confidence": analysis.get("brief_confidence"),
    }

    return {"final_response": final_response}