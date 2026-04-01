import re
from typing import List, Dict, Any

import pandas as pd
import matplotlib.pyplot as plt


def iso8601_duration_to_seconds(duration: str) -> int:
    """
    Convert YouTube ISO 8601 duration (e.g. PT5M12S) to total seconds.
    """
    if not duration:
        return 0

    pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
    match = re.match(pattern, duration)

    if not match:
        return 0

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    return hours * 3600 + minutes * 60 + seconds


def videos_to_dataframe(videos: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Flatten raw YouTube video records into a pandas DataFrame.
    """
    rows = []

    for v in videos:
        view_count = v.get("view_count", 0) or 0
        like_count = v.get("like_count", 0) or 0
        comment_count = v.get("comment_count", 0) or 0
        duration_seconds = iso8601_duration_to_seconds(v.get("duration", ""))

        tags = v.get("tags", [])
        if not isinstance(tags, list):
            tags = []

        comments = v.get("top_comments", [])
        comment_texts = [c.get("text", "") for c in comments if isinstance(c, dict)]

        rows.append({
            "video_id": v.get("video_id"),
            "title": v.get("title"),
            "description": v.get("description"),
            "channel_title": v.get("channel_title"),
            "published_at": v.get("published_at"),
            "view_count": view_count,
            "like_count": like_count,
            "comment_count": comment_count,
            "duration_seconds": duration_seconds,
            "tags_text": " ".join(tags),
            "comments_text": " || ".join(comment_texts),
            "num_fetched_comments": len(comment_texts),
        })

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df["like_rate"] = df.apply(
        lambda row: row["like_count"] / row["view_count"] if row["view_count"] > 0 else 0,
        axis=1
    )

    df["comment_rate"] = df.apply(
        lambda row: row["comment_count"] / row["view_count"] if row["view_count"] > 0 else 0,
        axis=1
    )

    df["engagement_rate"] = df["like_rate"] + df["comment_rate"]

    df["duration_bucket"] = pd.cut(
        df["duration_seconds"],
        bins=[0, 60, 180, 600, 999999],
        labels=["0-60s", "1-3m", "3-10m", "10m+"],
        include_lowest=True
    )

    return df


def summarize_dataset(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {"error": "No videos found."}

    return {
        "num_videos": int(len(df)),
        "avg_views": float(df["view_count"].mean()),
        "median_views": float(df["view_count"].median()),
        "avg_engagement_rate": float(df["engagement_rate"].mean()),
        "avg_duration_seconds": float(df["duration_seconds"].mean()),
    }


def analyze_duration_patterns(df: pd.DataFrame) -> List[Dict[str, Any]]:
    if df.empty:
        return []

    grouped = (
        df.groupby("duration_bucket", observed=False)
        .agg(
            video_count=("video_id", "count"),
            avg_views=("view_count", "mean"),
            avg_engagement_rate=("engagement_rate", "mean"),
        )
        .reset_index()
    )

    return grouped.to_dict(orient="records")


def analyze_keyword_patterns(df: pd.DataFrame, keywords: List[str]) -> List[Dict[str, Any]]:
    if df.empty:
        return []

    results = []

    searchable_text = (
        df["title"].fillna("") + " " +
        df["description"].fillna("") + " " +
        df["tags_text"].fillna("")
    ).str.lower()

    for keyword in keywords:
        mask = searchable_text.str.contains(keyword.lower(), na=False)
        subset = df[mask]

        if len(subset) == 0:
            continue

        results.append({
            "keyword": keyword,
            "video_count": int(len(subset)),
            "avg_views": float(subset["view_count"].mean()),
            "avg_engagement_rate": float(subset["engagement_rate"].mean()),
        })

    return results


def save_dataframe(df: pd.DataFrame, path: str) -> None:
    df.to_csv(path, index=False)


def plot_duration_engagement(df: pd.DataFrame, output_path: str) -> str:
    if df.empty:
        return ""

    grouped = (
        df.groupby("duration_bucket", observed=False)["engagement_rate"]
        .mean()
        .reset_index()
    )

    plt.figure(figsize=(8, 5))
    plt.bar(grouped["duration_bucket"].astype(str), grouped["engagement_rate"])
    plt.xlabel("Duration Bucket")
    plt.ylabel("Average Engagement Rate")
    plt.title("Average Engagement Rate by Video Duration")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

    return output_path


def generate_basic_hypothesis(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {"error": "No data available for hypothesis generation."}

    duration_stats = analyze_duration_patterns(df)
    if not duration_stats:
        return {"error": "No duration stats available."}

    valid_rows = [
        row for row in duration_stats
        if row["avg_engagement_rate"] is not None and row["video_count"] > 0
    ]

    if not valid_rows:
        return {"error": "No valid duration pattern rows found."}

    best_bucket = max(valid_rows, key=lambda x: x["avg_engagement_rate"])
    summary = summarize_dataset(df)

    return {
        "hypothesis": (
            f"Videos in the {best_bucket['duration_bucket']} range appear to perform best "
            f"for this query based on average engagement rate."
        ),
        "supporting_evidence": [
            f"Analyzed {summary['num_videos']} videos.",
            f"Best duration bucket: {best_bucket['duration_bucket']}.",
            f"Average engagement rate in that bucket: {best_bucket['avg_engagement_rate']:.4f}.",
        ],
        "caveats": [
            "This result is based on the current YouTube search sample, not all YouTube videos.",
            "Engagement rate is approximated using likes and comments divided by views.",
        ]
    }