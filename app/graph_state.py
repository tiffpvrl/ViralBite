from typing import TypedDict, List, Dict, Any, NotRequired


class ViralBiteState(TypedDict):
    query: str
    creator_profile: NotRequired[str]
    max_results: NotRequired[int]
    max_comments_per_video: NotRequired[int]
    order: NotRequired[str]
    window_days: NotRequired[int]
    max_pages: NotRequired[int]
    videos: List[Dict[str, Any]]
    collection_meta: NotRequired[Dict[str, Any]]
    analysis: Dict[str, Any]
    final_response: Dict[str, Any]