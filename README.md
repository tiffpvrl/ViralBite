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
- `VERTEXAI_COLLECTION_MODEL` (optional, defaults to `gemini-2.0-flash` via `VERTEXAI_CHAT_MODEL` / `VERTEXAI_MODEL`) — Vertex model that **issues the collection tool call** (`fetch_youtube_sample`) in `app/collection_agent.py` when `GOOGLE_CLOUD_PROJECT` is set
- `VERTEXAI_EDA_MODEL` (optional, defaults to `gemini-2.0-flash`) — Vertex model that **issues EDA tool calls** in `app/eda_agent.py` when `GOOGLE_CLOUD_PROJECT` is set
- `VERTEXAI_MODEL` (optional legacy) — if set, used when `VERTEXAI_CREATOR_MODEL` or `VERTEXAI_CHAT_MODEL` is omitted
- `VERTEXAI_THEME_MODEL` (optional, defaults to `gemini-1.5-flash`)
- `VIRALBITE_CACHE_TTL_SECONDS` (optional, defaults to `600`)
- `VIRALBITE_COMMENT_WORKERS` (optional, defaults to `6`)
- `VIRALBITE_MAX_COMMENT_VIDEOS` (optional, defaults to `12`; `0` means fetch comments for all videos)
- `VIRALBITE_ENABLE_TRANSCRIPTS` (optional, defaults to `1`)
- `VIRALBITE_TRANSCRIPT_WORKERS` (optional, defaults to `4`)
- `VIRALBITE_MAX_TRANSCRIPT_VIDEOS` (optional, defaults to `8`)
- `VIRALBITE_MIN_DURATION_SECONDS` (optional, defaults to `60`) — analysis includes only videos with **duration strictly greater** than this value (seconds), so the default excludes Shorts and clips ≤1 minute
- `VIRALBITE_MAX_SEARCH_PAGES_SAFETY` (optional, defaults to `100`) — upper bound on `search.list` pages while collecting long-form videos (each page up to 50 candidates). Collection stops earlier when `max_videos` qualifying rows are filled or YouTube returns no further pages.

## Analyze defaults and tuning

`GET /analyze` supports optional query parameters:

- `days` (default `30`): lookback window
- `max_videos` (default `35`, max `50`): target number of long-form videos (after duration filter); search **paginates** until enough are found or results are exhausted (see `VIRALBITE_MAX_SEARCH_PAGES_SAFETY`)
- `order` (default `viewCount`): YouTube search ordering
- `max_comments` (default `10`): top comments per selected video

The frontend uses the defaults above and the dashboard now includes a sample definition line so users can see exactly what dataset was analyzed.

## Quota + latency notes

- YouTube `search.list` is high quota cost (commonly `100` units per call). More pages may run until the target long-form count is met; cap with `VIRALBITE_MAX_SEARCH_PAGES_SAFETY` if needed.
- `videos.list` is batched and relatively cheap.
- Comment fetches are parallelized with a bounded thread pool to reduce wall-clock latency.
- To protect throughput, comments are fetched for only `VIRALBITE_MAX_COMMENT_VIDEOS` top-view videos by default.
- Transcript enrichment uses `youtube-transcript-api` for videos with public captions and is capped by `VIRALBITE_MAX_TRANSCRIPT_VIDEOS`.
- `/analyze` responses are cached in memory for `VIRALBITE_CACHE_TTL_SECONDS`, keyed by query + analysis parameters.

## Product flow

1. **Collect (tool calling)**: a LangChain `@tool` (`fetch_youtube_sample` in `app/collection_agent.py`) wraps `collect_youtube_data`. When `GOOGLE_CLOUD_PROJECT` is set, a Vertex model **calls that tool once** with `youtube_search_query` chosen from the user topic plus optional **creator profile** (so search can target the right audience, e.g. kids/family vs generic). Without Vertex, the tool runs with a deterministic query (`topic` + profile text).
2. **EDA (Option B — tool calling)**: exploratory metrics are computed **only** inside LangChain `@tool` functions in `app/eda_agent.py` (`build_eda_tools`). When `GOOGLE_CLOUD_PROJECT` is set, a Vertex model (`bind_tools`) is prompted to invoke **each** EDA tool once; if Vertex is not configured, the **same** tools are invoked deterministically in-process (still LangChain `BaseTool.invoke`, not ad-hoc pandas in `analyst_node`). Assembly-only fields (`sample_definition`, optional LLM comment themes) are added in `analyst_node` after tools return.
3. **Hypothesize**: generate a creator brief with concrete recommendations.

**Chat tab:** `POST /chat` runs a Vertex model with **LangChain tools** defined in `build_chat_analysis_tools()` (`app/chat_tools.py`) that read only from the current **analysis** JSON and optional **final_response** (brief). The request includes **creator_profile** so answers can match the saved creator context. Chat does **not** re-hit YouTube; users must run **Analyze** again for a new sample.

## Architecture (LangGraph)

State machine in `app/graph.py` with three nodes:

- `collector_node` (`app/agents.py`): `run_collection_with_tool_calling_agent()` — `app/collection_agent.py` (`fetch_youtube_sample` tool).
- `analyst_node` (`app/agents.py`): runs `run_eda_with_tool_calling_agent()` (`app/eda_agent.py`), then enriches comment themes via `extract_comment_themes_llm` and builds `sample_definition`.
- `insight_node` (`app/agents.py`): calls LLM for creator brief.

State schema: `app/graph_state.py`.

## File map by rubric step

- **Graph wiring**: `app/utils.py` invokes `build_graph().invoke(...)`
- **Core requirement — tool calling (Collect)**: `fetch_youtube_sample` in `build_collection_tool()` / `run_collection_with_tool_calling_agent()` — `app/collection_agent.py`
- **Core requirement — tool calling (EDA)**: LangChain `@tool` definitions in `build_eda_tools()` and orchestration in `run_eda_with_tool_calling_agent()` — `app/eda_agent.py`
- **Upload frequency**: `analyze_upload_frequency()` in `app/analysis_tools.py` (invoked **only** from tool `eda_upload_and_trend` in `app/eda_agent.py`)
- **Comment sentiment (VADER)**: `analyze_comment_sentiment()` in `app/analysis_tools.py` (tool `eda_comment_sentiment`)
- **Sponsored vs organic**: `analyze_sponsorship()` in `app/analysis_tools.py` (tool `eda_sponsorship`)
- **LLM creator brief**: `generate_creator_brief()` in `app/llm_client.py`
- **Chat backend**: `POST /chat` in `app/main.py` → `chat_with_analysis_context()` in `app/llm_client.py` (tool-calling over `app/chat_tools.py`)
- **Dashboard UI + chat UI**: `app/templates/index.html`, `app/static/app.js`, `app/static/styles.css`

> **Note:** `app/tools.py` is a legacy LangChain tool sketch and is **not** on the `/analyze` execution path; EDA tools live in `app/eda_agent.py`.

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
