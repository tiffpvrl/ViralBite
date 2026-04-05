const weeklyTopicsEl = document.getElementById("weekly-topics");
const dailyTopicsEl = document.getElementById("daily-topics");
const topicInput = document.getElementById("topic-input");
const analyzeBtn = document.getElementById("analyze-btn");
const loadingEl = document.getElementById("loading");
const dashboardEl = document.getElementById("dashboard");
const overviewCardsEl = document.getElementById("overview-cards");
const sampleDefinitionEl = document.getElementById("sample-definition");
const keywordSignalsEl = document.getElementById("keyword-signals");
const sentimentBarEl = document.getElementById("sentiment-bar");
const sentimentMetaEl = document.getElementById("sentiment-meta");
const sponsorMetaEl = document.getElementById("sponsor-meta");
const topVideosBodyEl = document.querySelector("#top-videos-table tbody");
const nlpSummaryEl = document.getElementById("nlp-summary");
const recommendationsEl = document.getElementById("recommendations");
const chatMessagesEl = document.getElementById("chat-messages");
const chatInputEl = document.getElementById("chat-input");
const chatSendBtn = document.getElementById("chat-send-btn");

let durationChart = null;
let uploadChart = null;
let sponsorChart = null;
let latestAnalysis = null;
let latestTopic = "";
let chatHistory = [];
const DEFAULT_ANALYZE_PARAMS = {
  days: 30,
  max_videos: 35,
  order: "viewCount",
  max_pages: 10,
  max_comments: 10,
};

function fmt(value, digits = 2) {
  if (value === null || value === undefined) return "N/A";
  if (typeof value === "number") {
    return value.toLocaleString(undefined, { maximumFractionDigits: digits });
  }
  return value;
}

function toMinutes(seconds) {
  if (!seconds && seconds !== 0) return "N/A";
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}m ${secs}s`;
}

function truncateText(text, maxLength = 32) {
  if (!text) return "";
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1)}...`;
}

function renderTopicButtons(target, topics) {
  target.innerHTML = "";
  topics.forEach((entry) => {
    const topic = entry.topic || entry;
    const btn = document.createElement("button");
    btn.className = "topic-pill";
    btn.textContent = topic;
    btn.addEventListener("click", () => {
      topicInput.value = topic;
      runAnalysis(topic);
    });
    target.appendChild(btn);
  });
}

async function loadHomepageTopics() {
  const response = await fetch("/homepage");
  const data = await response.json();
  renderTopicButtons(weeklyTopicsEl, data.weekly || []);
  renderTopicButtons(dailyTopicsEl, data.daily || []);
}

function renderOverview(summary, sampleDefinition) {
  const cards = [
    { label: "Total views", value: fmt(summary.total_views || 0, 0), note: `across ${fmt(summary.num_videos || 0, 0)} videos` },
    { label: "Avg engagement rate", value: `${fmt((summary.avg_engagement_rate || 0) * 100, 2)}%`, note: "likes + comments / views" },
    { label: "Median view count", value: fmt(summary.median_views || 0, 0), note: "less skewed than average" },
    { label: "Avg video length", value: toMinutes(Math.round(summary.avg_duration_seconds || 0)), note: `top bucket: ${summary.dominant_duration_bucket || "N/A"}` },
  ];

  overviewCardsEl.innerHTML = cards
    .map(
      (card) => `
      <div class="metric-card">
        <div class="metric-label">${card.label}</div>
        <div class="metric-value">${card.value}</div>
        <div class="metric-note">${card.note}</div>
      </div>`
    )
    .join("");

  const days = sampleDefinition?.window_days ?? DEFAULT_ANALYZE_PARAMS.days;
  const order = sampleDefinition?.order || DEFAULT_ANALYZE_PARAMS.order;
  const fetched = sampleDefinition?.fetched_videos ?? summary.num_videos ?? 0;
  const analyzed = sampleDefinition?.videos_analyzed ?? summary.num_videos ?? 0;
  const excluded = sampleDefinition?.excluded_not_longer_than_threshold ?? 0;
  const threshold = sampleDefinition?.min_duration_seconds_threshold ?? 60;
  const transcriptCount = sampleDefinition?.videos_with_transcript ?? 0;
  sampleDefinitionEl.textContent =
    `Fetched ${fmt(fetched, 0)} videos; analysis uses ${fmt(analyzed, 0)} with duration > ${threshold}s (${fmt(excluded, 0)} ≤${threshold}s excluded). Last ${days} days, order: ${order}. Transcripts: ${fmt(transcriptCount, 0)} videos.`;
}

function renderDurationChart(patterns) {
  const ctx = document.getElementById("durationChart");
  if (durationChart) durationChart.destroy();

  durationChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: patterns.map((p) => p.duration_bucket),
      datasets: [
        {
          label: "Avg engagement rate",
          data: patterns.map((p) => (p.avg_engagement_rate || 0) * 100),
          backgroundColor: "rgba(86, 156, 246, 0.75)",
          borderRadius: 8,
          yAxisID: "y",
        },
        {
          label: "Video count (n)",
          data: patterns.map((p) => p.video_count || 0),
          type: "line",
          borderColor: "rgba(233, 241, 252, 0.9)",
          backgroundColor: "rgba(233, 241, 252, 0.9)",
          pointRadius: 4,
          borderWidth: 2,
          tension: 0.25,
          yAxisID: "yCount",
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: true },
        tooltip: {
          callbacks: {
            afterBody(context) {
              const idx = context?.[0]?.dataIndex ?? 0;
              const median = patterns[idx]?.median_engagement_rate;
              if (typeof median === "number") {
                return [`Median engagement: ${fmt(median * 100, 2)}%`];
              }
              return [];
            },
          },
        },
      },
      scales: {
        y: { ticks: { callback: (v) => `${v}%` } },
        yCount: {
          position: "right",
          grid: { drawOnChartArea: false },
          ticks: { precision: 0 },
        },
      },
    },
  });
}

function renderUploadChart(uploadFrequency) {
  const ctx = document.getElementById("uploadChart");
  if (uploadChart) uploadChart.destroy();

  uploadChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: uploadFrequency.map((x) => x.week),
      datasets: [
        {
          label: "Videos published",
          data: uploadFrequency.map((x) => x.video_count),
          backgroundColor: "rgba(43, 116, 188, 0.8)",
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { precision: 0 },
          suggestedMax: Math.max(2, ...uploadFrequency.map((x) => x.video_count || 0)),
        },
      },
    },
  });
}

function renderKeywordSignals(keywords) {
  keywordSignalsEl.innerHTML = "";
  if (!keywords.length) {
    keywordSignalsEl.innerHTML = `<p class="muted">No keyword data available.</p>`;
    return;
  }

  keywords
    .sort((a, b) => (b.avg_engagement_rate || 0) - (a.avg_engagement_rate || 0))
    .forEach((row) => {
      const chip = document.createElement("div");
      chip.className = "keyword-chip";
      const keywordName = truncateText(row.keyword, 22);
      chip.innerHTML = `<strong>${keywordName}</strong><span>${fmt((row.avg_engagement_rate || 0) * 100, 2)}% eng · ${row.video_count} videos</span>`;
      keywordSignalsEl.appendChild(chip);
    });
}

function renderSentiment(sentiment) {
  const positive = sentiment.positive_pct || 0;
  const neutral = sentiment.neutral_pct || 0;
  const negative = sentiment.negative_pct || 0;

  sentimentBarEl.innerHTML = `
    <div class="seg positive" style="width:${positive}%">${fmt(positive, 0)}%</div>
    <div class="seg neutral" style="width:${neutral}%">${fmt(neutral, 0)}%</div>
    <div class="seg negative" style="width:${negative}%">${fmt(negative, 0)}%</div>
  `;

  const themes = (sentiment.top_positive_themes || []).join(", ") || "n/a";
  sentimentMetaEl.textContent = `Analyzed ${sentiment.num_comments_analyzed || 0} comments · Top themes: ${themes}`;
}

function renderSponsor(sponsorship) {
  const ctx = document.getElementById("sponsorChart");
  if (sponsorChart) sponsorChart.destroy();

  sponsorChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Sponsored", "Organic"],
      datasets: [
        {
          data: [sponsorship.sponsored_count || 0, sponsorship.organic_count || 0],
          backgroundColor: ["rgba(73, 131, 197, 0.9)", "rgba(165, 198, 233, 0.9)"],
        },
      ],
    },
    options: {
      responsive: true,
    },
  });

  sponsorMetaEl.textContent =
    `Sponsored avg views: ${fmt(sponsorship.sponsored_avg_views || 0, 0)} | ` +
    `Organic avg views: ${fmt(sponsorship.organic_avg_views || 0, 0)} | ` +
    `Sponsored eng: ${fmt((sponsorship.sponsored_avg_engagement || 0) * 100, 2)}% | ` +
    `Organic eng: ${fmt((sponsorship.organic_avg_engagement || 0) * 100, 2)}%`;
}

function renderTopVideos(videos) {
  topVideosBodyEl.innerHTML = "";
  videos.forEach((video, idx) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${idx + 1}</td>
      <td><strong>${video.title || "Untitled"}</strong><div class="muted">${video.channel_title || ""}</div></td>
      <td>${fmt(video.view_count || 0, 0)}</td>
      <td>${fmt((video.engagement_rate || 0) * 100, 2)}%</td>
      <td>${toMinutes(video.duration_seconds || 0)}</td>
    `;
    topVideosBodyEl.appendChild(tr);
  });
}

function addChatMessage(role, content) {
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role}`;
  bubble.textContent = content;
  chatMessagesEl.appendChild(bubble);
  chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

async function sendChat() {
  const message = chatInputEl.value.trim();
  if (!message || !latestAnalysis || !latestTopic) return;

  addChatMessage("user", message);
  chatHistory.push({ role: "user", content: message });
  chatInputEl.value = "";

  const response = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      topic: latestTopic,
      analysis: latestAnalysis,
      history: chatHistory,
      message,
    }),
  });

  const payload = await response.json();
  const text = payload.response || "No response.";
  addChatMessage("assistant", text);
  chatHistory.push({ role: "assistant", content: text });
}

function renderCreatorBrief(finalResponse) {
  const brief = finalResponse?.creator_brief || {};
  nlpSummaryEl.textContent = brief.summary || "No creator summary generated.";
  const recs = brief.recommendations || [];
  recommendationsEl.innerHTML = recs.map((r) => `<li>${r}</li>`).join("");
}

function renderDashboard(payload) {
  const analysis = payload.analysis || {};
  latestAnalysis = analysis;
  latestTopic = payload.query || topicInput.value.trim();
  chatHistory = [];
  chatMessagesEl.innerHTML = "";
  addChatMessage("assistant", `Loaded context for "${latestTopic}". Ask me anything about the dashboard.`);

  renderOverview(analysis.summary || {}, analysis.sample_definition || {});
  renderDurationChart(analysis.duration_patterns || []);
  renderUploadChart(analysis.upload_frequency || []);
  renderKeywordSignals(analysis.keyword_patterns || []);
  renderSentiment(analysis.comment_sentiment || {});
  renderSponsor(analysis.sponsorship || {});
  renderTopVideos(analysis.top_videos || []);
  renderCreatorBrief(payload.final_response || {});

  dashboardEl.classList.remove("hidden");
}

async function runAnalysis(topic) {
  const query = topic?.trim();
  if (!query) return;
  loadingEl.classList.remove("hidden");
  loadingEl.textContent = "Fetching videos and comments...";
  analyzeBtn.disabled = true;
  try {
    const params = new URLSearchParams({
      query,
      days: String(DEFAULT_ANALYZE_PARAMS.days),
      max_videos: String(DEFAULT_ANALYZE_PARAMS.max_videos),
      order: DEFAULT_ANALYZE_PARAMS.order,
      max_pages: String(DEFAULT_ANALYZE_PARAMS.max_pages),
      max_comments: String(DEFAULT_ANALYZE_PARAMS.max_comments),
    });
    const response = await fetch(`/analyze?${params.toString()}`);
    const data = await response.json();
    loadingEl.textContent = "Rendering dashboard...";
    renderDashboard(data);
  } catch (error) {
    console.error(error);
    alert("Analysis failed. Check your API keys and try again.");
  } finally {
    loadingEl.classList.add("hidden");
    loadingEl.textContent = "Running analysis...";
    analyzeBtn.disabled = false;
  }
}

analyzeBtn.addEventListener("click", () => runAnalysis(topicInput.value));
topicInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") runAnalysis(topicInput.value);
});
chatSendBtn.addEventListener("click", sendChat);
chatInputEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter") sendChat();
});

loadHomepageTopics();