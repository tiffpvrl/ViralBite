# ViralBite — Project 2: Data Analyst Agent

**ViralBite** is a **creator intelligence for food-related YouTube topics**: trending signals, engagement patterns, and actionable briefs. Our hope is that content creators can use **ViralBite** as their personal data analyst + creative director + social media manager!

---
## Live URL for Running

https://viralbite-1003029735859.us-central1.run.app

---

## What is ViralBite?

**What it does:** You type a **food-related YouTube topic** (or pick a suggested one). The app **pulls real videos from YouTube**, **runs analysis** on things like titles, comments, timing, and patterns, then gives you **charts**, a **written summary**, and **idea briefs** you could use as a creator. You can also **chat** with an assistant that knows the numbers from that same run.

**Who it’s for:** **YouTube creators** and **creator-minded people** who care about **food content**—for example, anyone trying to understand what’s working in a niche and what ideas might perform next.

**How to use it:**

1. Open the **live URL** above. If asked, add a short **creator profile** (who you are, your audience, any rules). You can change this later with **Edit profile** in the sidebar.
2. Stay on **Analysis**. Pick a **trending topic chip** or **type your own topic**, then click **Analyze Topic**. Wait while the app fetches data and builds the report.
3. Scroll the **Analysis** view for **overview cards**, **charts**, and deeper sections about the sample.
4. Switch to **Brief ideas** for **ready-made content angles** tied to that analysis + your creator profile.
5. Open **Chat** to **ask follow-up questions** about the same run (for example, “What should I try first?”).

Use the sidebar tabs to move between **Analysis**, **Brief ideas**, and **Chat**. The **theme** switch (sun/moon) toggles light and dark colors.

---
## Assignment alignment (three steps)

In this project, we implemented the **data analysis lifecycle** required — **(1) Collect**, **(2) Explore / EDA**, **(3) Hypothesize** — using **real-world YouTube data**, a **frontend**, an **agent framework**, **tool calling**, and **deployment**.

| Step | Requirement | How ViralBite implements it |
|------|----------------|-----------------------------|
| **1. Collect** | Retrieve data at runtime from a real external source (not hard-coded in the system prompt). | **`collect_youtube_data()`** in `app/youtube_collector.py` calls the **YouTube Data API v3** (`search.list`, `videos.list`, comments; optional captions via `youtube-transcript-api`). Collection is invoked through the LangChain tool **`fetch_youtube_sample`** in `app/collection_agent.py` (`build_collection_tool`, `run_collection_with_tool_calling_agent`). With **Vertex** (`GOOGLE_CLOUD_PROJECT`), a model issues a **tool call** with `youtube_search_query`; without Vertex, the same tool runs with a deterministic query. |
| **2. Explore (EDA)** | Exploratory analysis with **at least one tool call** over collected data; specific findings, not only a generic dump. | **`run_eda_with_tool_calling_agent()`** in `app/eda_agent.py` exposes multiple **`@tool`** functions (`build_eda_tools`) that run **pandas / VADER / heuristics** in `app/analysis_tools.py` (e.g. `summarize_dataset`, `analyze_duration_patterns`, `analyze_keyword_patterns`, `analyze_comment_sentiment`, `analyze_sponsorship`). With Vertex, the model uses **`bind_tools`** to invoke those tools; otherwise tools are invoked deterministically via **`BaseTool.invoke`**. |
| **3. Hypothesize** | A hypothesis or analyst-style deliverable **grounded in the data**, with evidence. | **`generate_creator_brief()`** in `app/llm_client.py` takes structured **`ANALYSIS_JSON`** and returns a **creator brief** (`CreatorBriefIdeas` / Pydantic). The UI and **`format_report()`** in `app/report_formatter.py` surface recommendations, metrics, and caveats. |

**Orchestration:** **`app/graph.py`** (**LangGraph**) runs **`collector_node` → `analyst_node` → `insight_node`** (`app/agents.py`). Entry: **`run_topic_analysis()`** in `app/utils.py` → **`build_graph().invoke(...)`**.

---

## Core requirements (checklist)

| Requirement | Where it lives |
|-------------|----------------|
| **Frontend** | `app/templates/index.html`, `app/static/app.js`, `app/static/styles.css` — dashboard, brief tab, chat; **`GET /`**, **`GET /analyze`**, **`POST /chat`** in `app/main.py`. |
| **Agent framework** | **LangGraph** — `app/graph.py` (`StateGraph`, `build_graph`). |
| **Tool calling** | **Collect:** `fetch_youtube_sample` — `app/collection_agent.py`. **EDA:** `eda_*` tools — `app/eda_agent.py`. **Chat (optional drill-down):** `build_chat_analysis_tools()` — `app/chat_tools.py`; **`chat_with_analysis_context()`** — `app/llm_client.py`. |
| **Non-trivial dataset** | Live **YouTube** search + video metadata + comments (+ transcripts when available); not a small hand-curated CSV in the prompt. |
| **Multi-agent pattern** | LangGraph **orchestration** with distinct stages; **LLM** steps use **different system prompts** (e.g. collection strategist in `COLLECTION_SYSTEM_PROMPT`, EDA instructions in `eda_agent.py`, creator brief in `generate_creator_brief`, chat in `CHAT_AGENT_SYSTEM`). |
| **Deployed** | Submit the **public URL** required by the assignment (e.g. Cloud Run, Railway, Render). |
| **README** | This file: how to run, where the three steps and requirements are implemented. |

---

## Grab-bag electives (≥ 2)

| Elective | Implementation |
|----------|------------------|
| **Structured output** | Pydantic models: `CreatorBrief`, `CreatorBriefIdeas`, `CommentThemeOutput` in `app/llm_client.py` (`with_structured_output`); **`ChatRequest`** in `app/main.py`. |
| **Data visualization** | **Chart.js** in `app/static/app.js` (duration, upload frequency, sponsorship, etc.) driven by `/analyze` JSON. |
| **Second data retrieval** | **Caption/transcript** text via `youtube-transcript-api` in `app/youtube_collector.py` (alongside YouTube REST). |

---

## Environment variables

| Variable | Purpose |
|----------|---------|
| `YOUTUBE_API_KEY` | **Required** — YouTube Data API v3. |
| `GOOGLE_CLOUD_PROJECT` | **Required** for Vertex-backed collection EDA tool calls, creator brief, chat, and theme extraction. |
| `VERTEXAI_CREATOR_MODEL` | Optional — creator brief (default `gemini-2.5-pro`). |
| `VERTEXAI_CHAT_MODEL` | Optional — `/chat` (default `gemini-2.5-flash`). |
| `VERTEXAI_COLLECTION_MODEL` | Optional — collection tool-calling model (falls back via `VERTEXAI_CHAT_MODEL` / `VERTEXAI_MODEL`). |
| `VERTEXAI_EDA_MODEL` | Optional — EDA tool-calling model. |
| `VERTEXAI_MODEL` | Legacy fallback when specific model vars are unset. |
| `VERTEXAI_THEME_MODEL` | Optional — comment theme extraction (`gemini-1.5-flash` default). |
| `VIRALBITE_CACHE_TTL_SECONDS` | In-memory `/analyze` cache TTL (default `600`). |
| `VIRALBITE_COMMENT_WORKERS`, `VIRALBITE_MAX_COMMENT_VIDEOS` | Comment fetch parallelism and cap. |
| `VIRALBITE_ENABLE_TRANSCRIPTS`, `VIRALBITE_TRANSCRIPT_WORKERS`, `VIRALBITE_MAX_TRANSCRIPT_VIDEOS` | Transcript enrichment. |
| `VIRALBITE_MIN_DURATION_SECONDS` | Minimum **duration** (seconds) for analysis; default `60` excludes Shorts-style clips. |
| `VIRALBITE_MAX_SEARCH_PAGES_SAFETY` | Max **`search.list`** pagination pages (default `100`, cap `500`) to bound quota while filling `max_videos`. |

---

## API: `GET /analyze`

Query parameters include:

- `query` — topic string (required).
- `days` — lookback window (default `30`).
- `max_videos` — target long-form count (default `35`, max `50`); search paginates until enough pass the duration filter or results end.
- `order` — YouTube search order (default `viewCount`).
- `max_comments` — top comments per video.
- `creator_profile` — optional; biases **collection** query (Vertex) or concatenates in fallback.

Responses are cached in memory (key includes query + parameters + profile).

---

## Architecture summary

```
collector_node  →  analyst_node  →  insight_node
     │                  │                 │
     │                  │                 └─ generate_creator_brief()  (app/llm_client.py)
     │                  └─ run_eda_with_tool_calling_agent()  (app/eda_agent.py)
     └─ run_collection_with_tool_calling_agent()  (app/collection_agent.py)
```

- **State:** `app/graph_state.py` — `ViralBiteState`.
- **Chat:** `POST /chat` — tool-grounded Q&A over the **current analysis** JSON (`app/chat_tools.py`, `app/llm_client.py`); does not re-fetch YouTube.

---

## File map (rubric-oriented)

| Area | Files |
|------|--------|
| Graph | `app/graph.py`, `app/utils.py` (`run_topic_analysis`) |
| Collect | `app/collection_agent.py`, `app/youtube_collector.py` |
| EDA | `app/eda_agent.py`, `app/analysis_tools.py` |
| Hypothesize / LLM | `app/llm_client.py`, `app/report_formatter.py` |
| HTTP | `app/main.py` |
| UI | `app/templates/index.html`, `app/static/app.js`, `app/static/styles.css` |

`app/tools.py` is **legacy** and **not** used by the `/analyze` graph; live tools are in **`app/eda_agent.py`** and **`app/collection_agent.py`**.

---

## Quota and performance

- **`search.list`** is high quota cost per call; pagination stops when `max_videos` long-form videos are collected, search exhausts, or **`VIRALBITE_MAX_SEARCH_PAGES_SAFETY`** is hit.
- Comments and transcripts are parallelized and capped by env vars for latency and quota.

---

## Limitations

1. **YouTube Data API is a thin slice of “what a video is.”** We mostly analyze **metadata** (titles, descriptions, tags, comments, and basic stats). Even when **captions/transcripts** are available (`youtube-transcript-api`), coverage is uneven—many videos have no captions or auto-captions only—and we do **not** analyze **actual video pixels**, **audio waveforms**, or **thumbnails**. Rich understanding of visuals, editing style, or on-screen content would require **multimodal models** and heavier pipelines, which were **out of scope** for this project.

2. **Search and recall are keyword- and API-biased.** `search.list` is driven by query text and YouTube’s ranking; we do not see “all videos truly about a topic.” For example, a “matcha latte” run surfaces videos that **explicitly match the query** in title/description much more reliably than videos that are **about** matcha latte but never say it in searchable text—so **recall** for the niche is incomplete.

3. **Manual creator profile.** The optional `creator_profile` is **free text**. In a production product you would use **YouTube OAuth** (and appropriate scopes) so creators sign in and you can ground recommendations on **their channel**, **audience-facing data where permitted**, and **authorized analytics**—reducing friction and unlocking richer context than a typed blurb.

4. **Heuristic and model limits.** Comment **sentiment** (e.g. VADER) and sponsorship **heuristics** are fast but not ground truth. LLM stages depend on **Vertex** configuration; behavior differs when models or tool-calling paths are unavailable.

5. **Quota, caps, and caching.** API **quotas**, **pagination** limits (`VIRALBITE_MAX_SEARCH_PAGES_SAFETY`), and **comment/transcript caps** bound how much of the platform we observe. **`/analyze` responses are cached in memory**, so results are not a durable audit trail across restarts.

---

## Next steps

- **OAuth + creator context:** YouTube OAuth for signed-in creators; use authorized channel/analytics data (where policy allows) to drive collection, the brief, and chat instead of manual profile text.

- **Multimodal and content-level signals:** Thumbnail/frame understanding, audio hooks, and structured “what happens in the video” features—paired with embeddings—to improve relevance beyond title/comment keywords.

- **Better discovery:** Semantic search over a broader candidate set (e.g. embeddings on titles/descriptions/transcripts), or hybrid retrieval so we miss fewer relevant videos that do not match the literal query.

- **Product hardening:** Persistent runs/history, exportable reports, evaluation on real creator cohorts, and clearer disclosure of what data was and was not observed for a given brief.

---
