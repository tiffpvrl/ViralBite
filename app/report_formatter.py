def format_report(query: str, analysis: dict, final_response: dict | None = None) -> str:
    summary = analysis.get("summary", {})
    duration_patterns = analysis.get("duration_patterns", [])
    keyword_patterns = analysis.get("keyword_patterns", [])
    creator_brief = (final_response or {}).get("creator_brief", {})
    brief_ideas = creator_brief.get("ideas") if isinstance(creator_brief, dict) else None
    brief_confidence = (final_response or {}).get("brief_confidence") or analysis.get("brief_confidence") or {}

    top_duration = None
    if duration_patterns:
        valid_rows = [row for row in duration_patterns if row.get("video_count", 0) > 0]
        if valid_rows:
            top_duration = max(valid_rows, key=lambda x: x.get("avg_engagement_rate", 0))

    top_keyword = None
    if keyword_patterns:
        top_keyword = max(keyword_patterns, key=lambda x: x.get("avg_engagement_rate", 0))

    lines = []
    lines.append(f"VIRALBITE REPORT: {query.upper()}")
    lines.append("=" * 50)

    lines.append("\nOVERVIEW")
    lines.append(f"- Videos analyzed: {summary.get('num_videos', 'N/A')}")
    lines.append(f"- Average views: {round(summary.get('avg_views', 0), 1)}")
    lines.append(f"- Median views: {round(summary.get('median_views', 0), 1)}")
    lines.append(f"- Average engagement rate: {round(summary.get('avg_engagement_rate', 0), 4)}")

    if top_duration:
        lines.append("\nTOP FORMAT SIGNAL")
        lines.append(f"- Best duration bucket: {top_duration.get('duration_bucket')}")
        lines.append(f"- Avg engagement rate in that bucket: {round(top_duration.get('avg_engagement_rate', 0), 4)}")

    if top_keyword:
        lines.append("\nTOP KEYWORD SIGNAL")
        lines.append(f"- Strongest keyword: {top_keyword.get('keyword')}")
        lines.append(f"- Avg engagement rate: {round(top_keyword.get('avg_engagement_rate', 0), 4)}")
        lines.append(f"- Matching videos: {top_keyword.get('video_count', 0)}")

    lines.append("\nCREATOR BRIEF")
    if brief_confidence.get("message"):
        lines.append(f"- Confidence: {brief_confidence.get('message')}")
    if isinstance(brief_ideas, list) and brief_ideas:
        for i, idea in enumerate(brief_ideas[:2], start=1):
            lines.append(f"- Idea {i} Opportunity: {idea.get('opportunity_statement')}")
            lines.append(f"- Idea {i} Video concept: {idea.get('video_concept')}")
            lines.append(f"- Idea {i} Production brief: {idea.get('production_brief')}")
            lines.append(f"- Idea {i} Differentiation: {idea.get('differentiation_angle')}")
    elif creator_brief.get("opportunity_statement"):
        lines.append(f"- Opportunity: {creator_brief.get('opportunity_statement')}")
        lines.append(f"- Video concept: {creator_brief.get('video_concept')}")
        lines.append(f"- Production brief: {creator_brief.get('production_brief')}")
        lines.append(f"- Differentiation: {creator_brief.get('differentiation_angle')}")
    else:
        lines.append(f"- {creator_brief.get('summary', 'No creator brief generated.')}")
        for item in creator_brief.get("recommendations") or []:
            lines.append(f"- {item}")

    if top_duration or top_keyword:
        lines.append("\nCREATOR TAKEAWAY")
        takeaway = "For this topic, creators should lean into"
        pieces = []

        if top_duration:
            pieces.append(f"{top_duration.get('duration_bucket')} videos")
        if top_keyword:
            pieces.append(f"keyword framing around '{top_keyword.get('keyword')}'")

        lines.append(f"- {takeaway} " + " and ".join(pieces) + ".")

    return "\n".join(lines)