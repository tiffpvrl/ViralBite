from app.youtube_collector import collect_youtube_data
from app.analysis_tools import (
    videos_to_dataframe,
    summarize_dataset,
    analyze_duration_patterns,
    analyze_keyword_patterns,
    generate_basic_hypothesis,
)


def collector_node(state):
    query = state["query"]

    videos = collect_youtube_data(
        query=query,
        max_results=20,
        max_comments_per_video=10,
        fetch_comments=True
    )

    return {"videos": videos}


def analyst_node(state):
    videos = state["videos"]
    df = videos_to_dataframe(videos)

    analysis = {
        "summary": summarize_dataset(df),
        "duration_patterns": analyze_duration_patterns(df),
        "keyword_patterns": analyze_keyword_patterns(
            df,
            ["cheap", "best", "authentic", "hidden", "local"]
        ),
        "hypothesis": generate_basic_hypothesis(df),
    }

    return {"analysis": analysis}


def insight_node(state):
    analysis = state["analysis"]

    final_response = {
        "summary": analysis["summary"],
        "key_finding": analysis["hypothesis"]["hypothesis"],
        "evidence": analysis["hypothesis"]["supporting_evidence"],
        "caveats": analysis["hypothesis"]["caveats"],
    }

    return {"final_response": final_response}