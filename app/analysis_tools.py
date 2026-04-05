import os
import re
from collections import Counter
from typing import List, Dict, Any, Tuple

import matplotlib.pyplot as plt
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

def _min_duration_threshold() -> int:
    try:
        return max(0, int(os.getenv("VIRALBITE_MIN_DURATION_SECONDS", "60")))
    except ValueError:
        return 60


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


def videos_to_dataframe(videos: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Flatten raw YouTube video records into a pandas DataFrame.

    Drops videos with duration <= VIRALBITE_MIN_DURATION_SECONDS (default 60s), so analysis
    is long-form only (excludes typical Shorts and sub-1-minute clips).
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
            "transcript_text": v.get("transcript_text", "") or "",
            "num_fetched_comments": len(comment_texts),
        })

    df = pd.DataFrame(rows)

    fetched = int(len(df))
    threshold = _min_duration_threshold()
    filter_meta: Dict[str, Any] = {
        "videos_fetched": fetched,
        "min_duration_seconds_threshold": threshold,
        "excluded_not_longer_than_threshold": 0,
        "videos_analyzed": 0,
    }

    if df.empty:
        return df, filter_meta

    before = len(df)
    df = df[df["duration_seconds"] > threshold].reset_index(drop=True)
    filter_meta["excluded_not_longer_than_threshold"] = before - len(df)
    filter_meta["videos_analyzed"] = int(len(df))

    if df.empty:
        return df, filter_meta

    df["like_rate"] = df.apply(
        lambda row: row["like_count"] / row["view_count"] if row["view_count"] > 0 else 0,
        axis=1
    )

    df["comment_rate"] = df.apply(
        lambda row: row["comment_count"] / row["view_count"] if row["view_count"] > 0 else 0,
        axis=1
    )

    df["engagement_rate"] = df["like_rate"] + df["comment_rate"]

    # Long-form sample only; buckets start above typical Shorts (no 0–60s bar).
    df["duration_bucket"] = pd.cut(
        df["duration_seconds"],
        bins=[60, 180, 600, 999999],
        labels=["1-3m", "3-10m", "10m+"],
        include_lowest=True,
    )

    return df, filter_meta


def summarize_dataset(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {"error": "No videos found."}

    dominant_duration_bucket = None
    duration_mode = df["duration_bucket"].mode(dropna=True)
    if not duration_mode.empty:
        dominant_duration_bucket = str(duration_mode.iloc[0])

    return {
        "num_videos": int(len(df)),
        "total_views": int(df["view_count"].sum()),
        "avg_views": float(df["view_count"].mean()),
        "median_views": float(df["view_count"].median()),
        "avg_engagement_rate": float(df["engagement_rate"].mean()),
        "avg_duration_seconds": float(df["duration_seconds"].mean()),
        "dominant_duration_bucket": dominant_duration_bucket,
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
            median_engagement_rate=("engagement_rate", "median"),
        )
        .reset_index()
    )

    return grouped.to_dict(orient="records")


def analyze_keyword_patterns(
    df: pd.DataFrame,
    keywords: List[str],
    top_n: int = 8,
) -> List[Dict[str, Any]]:
    if df.empty:
        return []

    results = []

    searchable_text = (
        df["title"].fillna("") + " " +
        df["description"].fillna("") + " " +
        df["tags_text"].fillna("") + " " +
        df["transcript_text"].fillna("")
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

    results.sort(key=lambda row: row.get("avg_engagement_rate", 0.0), reverse=True)
    return results[:top_n]


def analyze_upload_frequency(df: pd.DataFrame) -> List[Dict[str, Any]]:
    if df.empty or "published_at" not in df.columns:
        return []

    series = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    valid = pd.DataFrame({"published_at": series}).dropna()
    if valid.empty:
        return []

    # Use explicit week-start bins so reindexing does not zero-out due to boundary mismatch.
    week_start_labels = valid["published_at"].dt.to_period("W").astype(str).str.split("/").str[0]
    valid["week_start"] = pd.to_datetime(week_start_labels, utc=True, errors="coerce")
    valid = valid.dropna(subset=["week_start"])
    if valid.empty:
        return []
    weekly_counts = (
        valid.groupby("week_start")
        .size()
        .rename("video_count")
    )
    end_week = valid["week_start"].max()
    all_weeks = [end_week - pd.Timedelta(days=7 * idx) for idx in range(7, -1, -1)]
    weekly_counts = weekly_counts.reindex(pd.DatetimeIndex(all_weeks), fill_value=0)

    return [
        {"week": week.strftime("%Y-%m-%d"), "video_count": int(count)}
        for week, count in weekly_counts.items()
    ]


_STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "you", "your", "are", "was",
    "but", "have", "has", "not", "just", "from", "they", "their", "them", "its",
    "about", "into", "like", "very", "really", "what", "when", "where", "would",
    "should", "could", "there", "here", "more", "than", "then", "also", "too",
    "been", "were", "will", "while", "because", "after", "before", "food", "video",
    "videos", "channel", "watch", "watched", "make", "made", "great", "good"
}


def _extract_top_themes(comments: List[str], top_n: int = 3) -> List[str]:
    if not comments:
        return []

    token_pattern = re.compile(r"\b[a-zA-Z]{3,}\b")
    tokens = []
    for text in comments:
        for token in token_pattern.findall((text or "").lower()):
            if token not in _STOPWORDS:
                tokens.append(token)

    if not tokens:
        return []

    return [word for word, _ in Counter(tokens).most_common(top_n)]


def analyze_comment_sentiment(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty or "comments_text" not in df.columns:
        return {
            "positive_pct": 0.0,
            "neutral_pct": 0.0,
            "negative_pct": 0.0,
            "top_positive_themes": [],
            "top_negative_themes": [],
            "num_comments_analyzed": 0,
            "comment_samples": [],
        }

    analyzer = SentimentIntensityAnalyzer()
    all_comments: List[str] = []
    for raw in df["comments_text"].fillna("").tolist():
        if not raw:
            continue
        all_comments.extend([part.strip() for part in raw.split("||") if part.strip()])

    if not all_comments:
        return {
            "positive_pct": 0.0,
            "neutral_pct": 0.0,
            "negative_pct": 0.0,
            "top_positive_themes": [],
            "top_negative_themes": [],
            "num_comments_analyzed": 0,
            "comment_samples": [],
        }

    positive_comments: List[str] = []
    negative_comments: List[str] = []
    positive = 0
    neutral = 0
    negative = 0

    for comment in all_comments:
        score = analyzer.polarity_scores(comment).get("compound", 0.0)
        if score >= 0.05:
            positive += 1
            positive_comments.append(comment)
        elif score <= -0.05:
            negative += 1
            negative_comments.append(comment)
        else:
            neutral += 1

    total = len(all_comments)
    return {
        "positive_pct": round((positive / total) * 100, 2),
        "neutral_pct": round((neutral / total) * 100, 2),
        "negative_pct": round((negative / total) * 100, 2),
        "top_positive_themes": _extract_top_themes(positive_comments, top_n=3),
        "top_negative_themes": _extract_top_themes(negative_comments, top_n=3),
        "num_comments_analyzed": total,
        "comment_samples": all_comments[:120],
    }


def analyze_sponsorship(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {
            "sponsored_count": 0,
            "organic_count": 0,
            "sponsored_avg_views": 0.0,
            "organic_avg_views": 0.0,
            "sponsored_avg_engagement": 0.0,
            "organic_avg_engagement": 0.0,
        }

    ad_pattern = re.compile(
        (
            r"(#ad\b|#sponsored\b|#partner\b|#paidpartnership\b|#promotion\b|#sp\b|"
            r"paid partnership|includes paid promotion|this video is sponsored|"
            r"sponsored by|in partnership with|thanks to .* for sponsoring|"
            r"use code|use my code)"
        ),
        flags=re.IGNORECASE
    )
    not_sponsored_pattern = re.compile(r"(not sponsored|unsponsored)", flags=re.IGNORECASE)
    sponsor_text = (
        df["title"].fillna("").astype(str) + " " + df["description"].fillna("").astype(str)
    )
    sponsored_mask = (
        sponsor_text.str.contains(ad_pattern, regex=True)
        & ~sponsor_text.str.contains(not_sponsored_pattern, regex=True)
    )

    sponsored = df[sponsored_mask]
    organic = df[~sponsored_mask]

    return {
        "sponsored_count": int(len(sponsored)),
        "organic_count": int(len(organic)),
        "sponsored_avg_views": float(sponsored["view_count"].mean()) if len(sponsored) else 0.0,
        "organic_avg_views": float(organic["view_count"].mean()) if len(organic) else 0.0,
        "sponsored_avg_engagement": float(sponsored["engagement_rate"].mean()) if len(sponsored) else 0.0,
        "organic_avg_engagement": float(organic["engagement_rate"].mean()) if len(organic) else 0.0,
    }


def analyze_top_videos(df: pd.DataFrame, top_n: int = 5) -> List[Dict[str, Any]]:
    if df.empty:
        return []

    ranked = df.sort_values(by="view_count", ascending=False).head(top_n)
    rows = []
    for _, row in ranked.iterrows():
        rows.append({
            "video_id": row.get("video_id"),
            "title": row.get("title"),
            "channel_title": row.get("channel_title"),
            "view_count": int(row.get("view_count", 0)),
            "engagement_rate": float(row.get("engagement_rate", 0.0)),
            "duration_seconds": int(row.get("duration_seconds", 0)),
            "duration_bucket": str(row.get("duration_bucket")),
        })

    return rows


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