"""
Legacy LangChain tool stubs — not used by `/analyze`.

EDA tools for the assignment rubric live in `app/eda_agent.py` (`build_eda_tools`).
"""
import json
from langchain.tools import tool

from app.youtube_collector import collect_youtube_data
from app.analysis_tools import (
    videos_to_dataframe,
    summarize_dataset,
    analyze_duration_patterns,
    analyze_keyword_patterns,
    generate_basic_hypothesis,
)


@tool
def collect_youtube_tool(query: str) -> str:
    """Collect YouTube food video data for a topic and return it as JSON."""
    videos = collect_youtube_data(
        query=query,
        max_results=20,
        max_comments_per_video=10,
        fetch_comments=True,
    )
    return json.dumps(videos)


@tool
def analyze_youtube_tool(videos_json: str) -> str:
    """Analyze collected YouTube video data from a JSON string and return analysis as JSON."""
    videos = json.loads(videos_json)

    df, _duration_filter = videos_to_dataframe(videos)

    analysis = {
        "summary": summarize_dataset(df),
        "duration_patterns": analyze_duration_patterns(df),
        "keyword_patterns": analyze_keyword_patterns(
            df,
            ["cheap", "best", "authentic", "hidden", "local"]
        ),
        "hypothesis": generate_basic_hypothesis(df),
    }
    return json.dumps(analysis)