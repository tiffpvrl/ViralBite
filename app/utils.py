import json

from app.tools import collect_youtube_tool, analyze_youtube_tool
from app.report_formatter import format_report


def run_topic_analysis(query: str) -> dict:
    collected_videos_json = collect_youtube_tool.invoke({"query": query})
    analysis_json = analyze_youtube_tool.invoke({"videos_json": collected_videos_json})
    analysis = json.loads(analysis_json)
    report = format_report(query, analysis)

    return {
        "query": query,
        "analysis": analysis,
        "report": report,
    }

def build_homepage_cards(topics: list[str]) -> list[dict]:
    cards = []

    for topic in topics:
        result = run_topic_analysis(topic)
        analysis = result["analysis"]

        summary = analysis.get("summary", {})
        duration_patterns = analysis.get("duration_patterns", [])
        keyword_patterns = analysis.get("keyword_patterns", [])

        # best duration
        best_duration = None
        if duration_patterns:
            valid = [d for d in duration_patterns if d.get("video_count", 0) > 0]
            if valid:
                best_duration = max(valid, key=lambda x: x.get("avg_engagement_rate", 0))

        # best keyword
        best_keyword = None
        if keyword_patterns:
            best_keyword = max(keyword_patterns, key=lambda x: x.get("avg_engagement_rate", 0))

        cards.append({
            "topic": topic,
            "num_videos": summary.get("num_videos"),
            "avg_engagement_rate": summary.get("avg_engagement_rate"),
            "top_duration_bucket": best_duration.get("duration_bucket") if best_duration else None,
            "top_keyword": best_keyword.get("keyword") if best_keyword else None,
        })

    return cards