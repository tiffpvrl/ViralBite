from pydantic import BaseModel
from typing import List, Dict, Any


class VideoQueryInput(BaseModel):
    query: str
    max_results: int = 20
    max_comments_per_video: int = 10
    fetch_comments: bool = True


class DatasetSummaryOutput(BaseModel):
    num_videos: int
    avg_views: float
    median_views: float
    avg_engagement_rate: float
    avg_duration_seconds: float


class DurationPatternRow(BaseModel):
    duration_bucket: str
    video_count: int
    avg_views: float
    avg_engagement_rate: float


class KeywordPatternRow(BaseModel):
    keyword: str
    video_count: int
    avg_views: float
    avg_engagement_rate: float


class HypothesisOutput(BaseModel):
    hypothesis: str
    supporting_evidence: List[str]
    caveats: List[str]