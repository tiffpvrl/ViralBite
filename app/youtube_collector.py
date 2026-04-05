from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from googleapiclient.discovery import build
try:
    from youtube_transcript_api import YouTubeTranscriptApi
except Exception:
    YouTubeTranscriptApi = None

load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")
COMMENT_WORKERS = max(1, int(os.getenv("VIRALBITE_COMMENT_WORKERS", "6")))
MAX_COMMENT_VIDEOS_DEFAULT = int(os.getenv("VIRALBITE_MAX_COMMENT_VIDEOS", "12"))
ENABLE_TRANSCRIPTS = os.getenv("VIRALBITE_ENABLE_TRANSCRIPTS", "1") == "1"
TRANSCRIPT_WORKERS = max(1, int(os.getenv("VIRALBITE_TRANSCRIPT_WORKERS", "4")))
MAX_TRANSCRIPT_VIDEOS_DEFAULT = int(os.getenv("VIRALBITE_MAX_TRANSCRIPT_VIDEOS", "8"))

if not API_KEY:
    raise ValueError("API key not found. Check your .env file.")


def get_comments(youtube, video_id, max_comments=20):
    try:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=max_comments,
            textFormat="plainText",
            order="relevance"
        )
        response = request.execute()

        comments = []
        for item in response.get("items", []):
            comment_snippet = item["snippet"]["topLevelComment"]["snippet"]

            comments.append({
                "comment_id": item["snippet"]["topLevelComment"]["id"],
                "text": comment_snippet.get("textDisplay"),
                "author": comment_snippet.get("authorDisplayName"),
                "author_channel_url": comment_snippet.get("authorChannelUrl"),
                "like_count": comment_snippet.get("likeCount", 0),
                "published_at": comment_snippet.get("publishedAt"),
                "updated_at": comment_snippet.get("updatedAt"),
                "reply_count": item["snippet"].get("totalReplyCount", 0)
            })

        return comments

    except Exception:
        return []


def _to_rfc3339_utc(days_back: Optional[int]) -> Optional[str]:
    if not days_back or days_back <= 0:
        return None
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    return cutoff.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _fetch_comments_for_video(video_id: str, max_comments: int) -> list[dict[str, Any]]:
    youtube = build("youtube", "v3", developerKey=API_KEY)
    return get_comments(youtube=youtube, video_id=video_id, max_comments=max_comments)


def _fetch_transcript_for_video(video_id: str) -> str:
    if YouTubeTranscriptApi is None:
        return ""
    try:
        transcript_rows = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
        return " ".join(row.get("text", "").strip() for row in transcript_rows if row.get("text"))
    except Exception:
        return ""


def collect_youtube_data(
    query,
    max_results=25,
    max_comments_per_video=10,
    fetch_comments=True,
    order="viewCount",
    window_days: Optional[int] = 30,
    max_pages: int = 1,
):
    youtube = build("youtube", "v3", developerKey=API_KEY)
    target_results = max(1, min(int(max_results), 50))
    page_limit = max(1, min(int(max_pages), 3))
    published_after = _to_rfc3339_utc(window_days)
    search_items: list[dict[str, Any]] = []
    seen_video_ids = set()
    next_page_token = None

    for _ in range(page_limit):
        request_payload = {
            "q": query,
            "part": "snippet",
            "type": "video",
            "maxResults": min(50, target_results),
            "order": order,
        }
        if next_page_token:
            request_payload["pageToken"] = next_page_token
        if published_after:
            request_payload["publishedAfter"] = published_after

        search_response = youtube.search().list(**request_payload).execute()
        for item in search_response.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if not video_id or video_id in seen_video_ids:
                continue
            seen_video_ids.add(video_id)
            search_items.append(item)
            if len(search_items) >= target_results:
                break

        if len(search_items) >= target_results:
            break
        next_page_token = search_response.get("nextPageToken")
        if not next_page_token:
            break

    search_items = search_items[:target_results]
    video_ids = [item["id"]["videoId"] for item in search_items if item.get("id", {}).get("videoId")]

    if not video_ids:
        return []

    details_response = youtube.videos().list(
        part="snippet,statistics,contentDetails,status,topicDetails",
        id=",".join(video_ids)
    ).execute()

    details_map = {item["id"]: item for item in details_response.get("items", [])}

    videos = []
    for search_item in search_items:
        vid = search_item["id"]["videoId"]
        detail = details_map.get(vid, {})

        snippet = detail.get("snippet", {})
        statistics = detail.get("statistics", {})
        content_details = detail.get("contentDetails", {})
        status = detail.get("status", {})
        topic_details = detail.get("topicDetails", {})

        video_record = {
            "video_id": vid,

            # snippet / basic descriptive metadata
            "title": snippet.get("title"),
            "description": snippet.get("description"),
            "channel_title": snippet.get("channelTitle"),
            "channel_id": snippet.get("channelId"),
            "published_at": snippet.get("publishedAt"),
            "category_id": snippet.get("categoryId"),
            "tags": snippet.get("tags", []),
            "default_language": snippet.get("defaultLanguage"),
            "default_audio_language": snippet.get("defaultAudioLanguage"),
            "live_broadcast_content": snippet.get("liveBroadcastContent"),

            # thumbnails
            "thumbnails": snippet.get("thumbnails", {}),

            # statistics
            "view_count": int(statistics.get("viewCount", 0)) if statistics.get("viewCount") is not None else 0,
            "like_count": int(statistics.get("likeCount", 0)) if statistics.get("likeCount") is not None else 0,
            "favorite_count": int(statistics.get("favoriteCount", 0)) if statistics.get("favoriteCount") is not None else 0,
            "comment_count": int(statistics.get("commentCount", 0)) if statistics.get("commentCount") is not None else 0,

            # content details
            "duration": content_details.get("duration"),
            "dimension": content_details.get("dimension"),
            "definition": content_details.get("definition"),
            "caption": content_details.get("caption"),
            "licensed_content": content_details.get("licensedContent"),
            "projection": content_details.get("projection"),

            # status
            "upload_status": status.get("uploadStatus"),
            "privacy_status": status.get("privacyStatus"),
            "license": status.get("license"),
            "embeddable": status.get("embeddable"),
            "public_stats_viewable": status.get("publicStatsViewable"),
            "made_for_kids": status.get("madeForKids"),
            "self_declared_made_for_kids": status.get("selfDeclaredMadeForKids"),

            # topic details
            "topic_ids": topic_details.get("topicIds", []),
            "relevant_topic_ids": topic_details.get("relevantTopicIds", []),
            "topic_categories": topic_details.get("topicCategories", []),

            # comments
            "top_comments": [],
            "transcript_text": "",
        }

        videos.append(video_record)

    if fetch_comments and videos:
        sorted_by_views = sorted(videos, key=lambda x: x.get("view_count", 0), reverse=True)
        comment_video_budget = MAX_COMMENT_VIDEOS_DEFAULT
        if comment_video_budget and comment_video_budget > 0:
            eligible_video_ids = {video["video_id"] for video in sorted_by_views[:comment_video_budget]}
        else:
            eligible_video_ids = {video["video_id"] for video in sorted_by_views}

        comments_by_video = {}
        with ThreadPoolExecutor(max_workers=COMMENT_WORKERS) as executor:
            future_map = {
                executor.submit(_fetch_comments_for_video, video["video_id"], max_comments_per_video): video["video_id"]
                for video in videos
                if video["video_id"] in eligible_video_ids
            }
            for future in as_completed(future_map):
                video_id = future_map[future]
                try:
                    comments_by_video[video_id] = future.result()
                except Exception:
                    comments_by_video[video_id] = []

        for video in videos:
            video["top_comments"] = comments_by_video.get(video["video_id"], [])

    if ENABLE_TRANSCRIPTS and videos and YouTubeTranscriptApi is not None:
        sorted_by_views = sorted(videos, key=lambda x: x.get("view_count", 0), reverse=True)
        transcript_video_budget = MAX_TRANSCRIPT_VIDEOS_DEFAULT
        if transcript_video_budget and transcript_video_budget > 0:
            eligible_video_ids = {video["video_id"] for video in sorted_by_views[:transcript_video_budget]}
        else:
            eligible_video_ids = {video["video_id"] for video in sorted_by_views}

        transcripts_by_video = {}
        with ThreadPoolExecutor(max_workers=TRANSCRIPT_WORKERS) as executor:
            future_map = {
                executor.submit(_fetch_transcript_for_video, video["video_id"]): video["video_id"]
                for video in videos
                if video["video_id"] in eligible_video_ids
            }
            for future in as_completed(future_map):
                video_id = future_map[future]
                try:
                    transcripts_by_video[video_id] = future.result()
                except Exception:
                    transcripts_by_video[video_id] = ""

        for video in videos:
            video["transcript_text"] = transcripts_by_video.get(video["video_id"], "")

    return videos