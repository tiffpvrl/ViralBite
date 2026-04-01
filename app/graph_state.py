from typing import TypedDict, List, Dict, Any


class ViralBiteState(TypedDict):
    query: str
    videos: List[Dict[str, Any]]
    analysis: Dict[str, Any]
    final_response: Dict[str, Any]