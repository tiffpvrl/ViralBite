from dotenv import load_dotenv
import os
from googleapiclient.discovery import build

load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")

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


def collect_youtube_data(query, max_results=25, max_comments_per_video=10, fetch_comments=True):
    youtube = build("youtube", "v3", developerKey=API_KEY)

    search_response = youtube.search().list(
        q=query,
        part="snippet",
        type="video",
        maxResults=max_results
    ).execute()

    search_items = search_response.get("items", [])
    video_ids = [item["id"]["videoId"] for item in search_items]

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

        comments_text = []
        if fetch_comments:
            comments_text = get_comments(
                youtube=youtube,
                video_id=vid,
                max_comments=max_comments_per_video
            )

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
            "top_comments": comments_text
        }

        videos.append(video_record)

    return videos