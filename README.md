# ViralBite

ViralBite is a multi-agent creator intelligence app for food YouTube topics.

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Set environment variables:

- `YOUTUBE_API_KEY`
- `GOOGLE_CLOUD_PROJECT` (for Vertex AI creator brief + chat)
- `VERTEXAI_CREATOR_MODEL` (optional, defaults to `gemini-2.5-pro`) — NLP summary / creator brief
- `VERTEXAI_CHAT_MODEL` (optional, defaults to `gemini-2.5-flash`) — `/chat` assistant
- `VERTEXAI_MODEL` (optional legacy) — if set, used when `VERTEXAI_CREATOR_MODEL` or `VERTEXAI_CHAT_MODEL` is omitted
- `VERTEXAI_THEME_MODEL` (optional, defaults to `gemini-1.5-flash`)
- `VIRALBITE_CACHE_TTL_SECONDS` (optional, defaults to `600`)
- `VIRALBITE_COMMENT_WORKERS` (optional, defaults to `6`)
- `VIRALBITE_MAX_COMMENT_VIDEOS` (optional, defaults to `12`; `0` means fetch comments for all videos)
- `VIRALBITE_ENABLE_TRANSCRIPTS` (optional, defaults to `1`)
- `VIRALBITE_TRANSCRIPT_WORKERS` (optional, defaults to `4`)
- `VIRALBITE_MAX_TRANSCRIPT_VIDEOS` (optional, defaults to `8`)

## Analyze defaults and tuning

`GET /analyze` supports optional query parameters:

- `days` (default `30`): lookback window
- `max_videos` (default `35`, max `50`): number of videos to analyze
- `order` (default `viewCount`): YouTube search ordering
- `max_pages` (default `2`): how many search pages to pull (up to `3`)
- `max_comments` (default `10`): top comments per selected video

The frontend uses the defaults above and the dashboard now includes a sample definition line so users can see exactly what dataset was analyzed.

## Quota + latency notes

- YouTube `search.list` is high quota cost (commonly `100` units per call). Increasing `max_pages` increases quota usage.
- `videos.list` is batched and relatively cheap.
- Comment fetches are parallelized with a bounded thread pool to reduce wall-clock latency.
- To protect throughput, comments are fetched for only `VIRALBITE_MAX_COMMENT_VIDEOS` top-view videos by default.
- Transcript enrichment uses `youtube-transcript-api` for videos with public captions and is capped by `VIRALBITE_MAX_TRANSCRIPT_VIDEOS`.
- `/analyze` responses are cached in memory for `VIRALBITE_CACHE_TTL_SECONDS`, keyed by query + analysis parameters.

## Product flow

1. **Collect**: pull topic-matched YouTube videos and comments from the API.
2. **EDA**: compute structured trend metrics for creator decision making.
3. **Hypothesize**: generate a creator brief with concrete recommendations.

## Architecture (LangGraph)

State machine in `app/graph.py` with three nodes:

- `collector_node` (`app/agents.py`): fetches topic data.
- `analyst_node` (`app/agents.py`): computes analysis features.
- `insight_node` (`app/agents.py`): calls LLM for creator brief.

State schema: `app/graph_state.py`.

## File map by rubric step

- **Graph wiring**: `app/utils.py` invokes `build_graph().invoke(...)`
- **Upload frequency**: `analyze_upload_frequency()` in `app/analysis_tools.py`
- **Comment sentiment (VADER)**: `analyze_comment_sentiment()` in `app/analysis_tools.py`
- **Sponsored vs organic**: `analyze_sponsorship()` in `app/analysis_tools.py`
- **LLM creator brief**: `generate_creator_brief()` in `app/llm_client.py`
- **Chat backend**: `POST /chat` in `app/main.py` using `chat_with_analysis_context()`
- **Dashboard UI + chat UI**: `app/templates/index.html`, `app/static/app.js`, `app/static/styles.css`

## Two grab-bags used

- **Structured output with Pydantic schemas**:
  - `CreatorBrief` schema in `app/llm_client.py`
  - request schemas for chat in `app/main.py`
- **Data visualization**:
  - Chart.js frontend charts (duration, upload frequency, sponsorship donut)
  - metric cards/table/keyword and sentiment visual blocks

## Deploy

Deploy as a single FastAPI service on Railway or Render.

- Configure `YOUTUBE_API_KEY` and `GOOGLE_CLOUD_PROJECT` in the hosting dashboard.
- Static frontend is already served by FastAPI via `StaticFiles`.
