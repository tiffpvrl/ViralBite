from typing import Any, Dict, List

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.utils import run_topic_analysis, build_homepage_cards
from app.llm_client import chat_with_analysis_context

import math

app = FastAPI(title="ViralBite API")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/artifacts", StaticFiles(directory="app/artifacts"), name="artifacts")

templates = Jinja2Templates(directory="app/templates")


def clean_nan(obj):
    if isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_nan(v) for v in obj]
    if isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"request": request}
    )


@app.get("/homepage")
def homepage():
    weekly_topics = [
        "nyc bagel",
        "matcha latte",
        "dubai chocolate",
        "brooklyn pizza",
        "korean corn dog",
    ]
    daily_topics = [
        "smash burger",
        "hot honey chicken sandwich",
        "street tacos",
    ]
    return clean_nan(
        {
            "weekly": build_homepage_cards(weekly_topics),
            "daily": build_homepage_cards(daily_topics),
        }
    )


@app.get("/analyze")
def analyze(
    query: str = Query(..., description="Topic to analyze"),
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    max_videos: int = Query(35, ge=1, le=50, description="Maximum videos to analyze"),
    order: str = Query("viewCount", description="YouTube search order"),
    max_pages: int = Query(2, ge=1, le=3, description="Maximum search result pages"),
    max_comments: int = Query(10, ge=1, le=50, description="Top comments per video"),
):
    result = run_topic_analysis(
        query=query,
        window_days=days,
        max_results=max_videos,
        order=order,
        max_pages=max_pages,
        max_comments_per_video=max_comments,
    )
    return clean_nan(result)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    topic: str
    analysis: Dict[str, Any]
    history: List[ChatMessage] = Field(default_factory=list)
    message: str


@app.post("/chat")
def chat(payload: ChatRequest):
    history = [{"role": m.role, "content": m.content} for m in payload.history]
    response_text = chat_with_analysis_context(
        topic=payload.topic,
        analysis=payload.analysis,
        history=history,
        message=payload.message,
    )
    return clean_nan({"response": response_text})