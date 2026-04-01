from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.utils import run_topic_analysis, build_homepage_cards
from app.report_formatter import format_report

app = FastAPI(title="ViralBite API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_TOPICS = [
    "nyc bagel",
    "matcha latte",
    "brooklyn pizza",
]


@app.get("/")
def root():
    return {"message": "ViralBite API is running"}


@app.get("/homepage")
def homepage():
    cards = build_homepage_cards(DEFAULT_TOPICS)
    return {"topics": cards}


@app.get("/analyze")
def analyze(query: str = Query(..., description="Topic to analyze")):
    result = run_topic_analysis(query)
    return result