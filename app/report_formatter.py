def format_report(query: str, analysis: dict) -> str:
    summary = analysis.get("summary", {})
    duration_patterns = analysis.get("duration_patterns", [])
    keyword_patterns = analysis.get("keyword_patterns", [])
    hypothesis_block = analysis.get("hypothesis", {})

    hypothesis = hypothesis_block.get("hypothesis", "No hypothesis generated.")
    evidence = hypothesis_block.get("supporting_evidence", [])
    caveats = hypothesis_block.get("caveats", [])

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

    lines.append("\nHYPOTHESIS")
    lines.append(f"- {hypothesis}")

    if evidence:
        lines.append("\nSUPPORTING EVIDENCE")
        for item in evidence:
            lines.append(f"- {item}")

    if caveats:
        lines.append("\nCAVEATS")
        for item in caveats:
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