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
const sentimentLegendEl = document.getElementById("sentiment-legend");
const sentimentMetaEl = document.getElementById("sentiment-meta");
const sponsorMetaEl = document.getElementById("sponsor-meta");
const sponsorLegendEl = document.getElementById("sponsor-legend");
const topVideosBodyEl = document.querySelector("#top-videos-table tbody");
const creatorBriefTitleEl = document.getElementById("creator-brief-title");
const briefConfidenceEl = document.getElementById("brief-confidence");
const creatorBriefBodyEl = document.getElementById("creator-brief-body");
const chatMessagesEl = document.getElementById("chat-messages");
const chatInputEl = document.getElementById("chat-input");
const chatSendBtn = document.getElementById("chat-send-btn");
const themeToggleBtn = document.getElementById("theme-toggle");
const creatorModalEl = document.getElementById("creator-profile-modal");
const creatorProfileInputEl = document.getElementById("creator-profile-input");
const creatorProfileSaveBtn = document.getElementById("creator-profile-save");
const creatorProfilePreviewEl = document.getElementById("creator-profile-preview");
const creatorProfileEditBtn = document.getElementById("creator-profile-edit");
const creatorProfileModalEyebrowEl = document.getElementById("creator-profile-modal-eyebrow");
const creatorProfileModalTitleEl = document.getElementById("creator-profile-modal-title");
const creatorProfileModalCopyEl = document.getElementById("creator-profile-modal-copy");

let durationChart = null;
let uploadChart = null;
let sponsorChart = null;
let latestAnalysis = null;
let latestTopic = "";
let chatHistory = [];
let creatorProfile = "";
let creatorProfileModalIsEdit = false;
const DEFAULT_ANALYZE_PARAMS = {
  days: 30,
  max_videos: 35,
  order: "viewCount",
  max_pages: 10,
  max_comments: 10,
};

const PILL_VARIANTS = ["terra", "cream"];

let lastDashboardPayload = null;
let scrollObserver = null;

function chartPalette() {
  const r = document.documentElement;
  const g = (name, fallback) => {
    const v = getComputedStyle(r).getPropertyValue(name).trim();
    return v || fallback;
  };
  return {
    paprika: g("--chart-paprika", "rgba(232, 114, 74, 0.88)"),
    chili: g("--chart-chili", "rgba(200, 75, 47, 0.92)"),
    brick: g("--chart-brick", "#8b3520"),
    saffron: g("--chart-saffron", "rgba(245, 192, 122, 0.95)"),
    grid: g("--chart-grid", "rgba(232, 224, 216, 0.85)"),
    tick: g("--chart-tick", "#8b6a4a"),
    legend: g("--chart-legend", "#1a1008"),
  };
}

function syncThemeToggleAria() {
  if (!themeToggleBtn) return;
  const dark = document.documentElement.getAttribute("data-theme") === "dark";
  themeToggleBtn.setAttribute("aria-checked", dark ? "true" : "false");
  const label = document.getElementById("theme-toggle-label");
  if (label) {
    label.textContent = dark ? "Color theme: dark" : "Color theme: light";
  }
}

function initTheme() {
  const saved = localStorage.getItem("viralbite-theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const theme = saved || (prefersDark ? "dark" : "light");
  document.documentElement.setAttribute("data-theme", theme);
  syncThemeToggleAria();
}

function initThemeToggle() {
  if (!themeToggleBtn) return;
  themeToggleBtn.addEventListener("click", () => {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("viralbite-theme", next);
    syncThemeToggleAria();
    window.dispatchEvent(new CustomEvent("viralbite-theme-change"));
  });
}

function persistCreatorProfile(value) {
  creatorProfile = String(value || "").trim();
  localStorage.setItem("viralbite-creator-profile", creatorProfile);
  if (creatorProfilePreviewEl) {
    creatorProfilePreviewEl.textContent = creatorProfile
      ? `Creator context: ${creatorProfile}`
      : "Creator context not set";
  }
}

function closeCreatorProfileModal() {
  if (!creatorModalEl) return;
  creatorModalEl.classList.add("hidden");
  creatorModalEl.setAttribute("aria-hidden", "true");
}

function openCreatorProfileModal(edit) {
  creatorProfileModalIsEdit = Boolean(edit);
  if (!creatorModalEl || !creatorProfileInputEl) return;
  creatorProfileInputEl.value = creatorProfile;
  if (creatorProfileModalIsEdit) {
    if (creatorProfileModalEyebrowEl) creatorProfileModalEyebrowEl.textContent = "Your profile";
    if (creatorProfileModalTitleEl) creatorProfileModalTitleEl.textContent = "Update creator context";
    if (creatorProfileModalCopyEl) {
      creatorProfileModalCopyEl.textContent =
        "Edit what we use to tailor brief ideas. You can clear the field to remove saved context.";
    }
    if (creatorProfileSaveBtn) creatorProfileSaveBtn.textContent = "Save changes";
  } else {
    if (creatorProfileModalEyebrowEl) creatorProfileModalEyebrowEl.textContent = "Before we start";
    if (creatorProfileModalTitleEl) creatorProfileModalTitleEl.textContent = "Who are you as a creator?";
    if (creatorProfileModalCopyEl) {
      creatorProfileModalCopyEl.textContent =
        "Share your channel context (niche, audience, constraints). Example: Mommy vlogger. 500K subscribers. Family-friendly, kids inspo videos.";
    }
    if (creatorProfileSaveBtn) creatorProfileSaveBtn.textContent = "Save profile and continue";
  }
  creatorModalEl.classList.remove("hidden");
  creatorModalEl.setAttribute("aria-hidden", "false");
  creatorProfileInputEl.focus();
}

function initCreatorProfileModal() {
  const existing = localStorage.getItem("viralbite-creator-profile") || "";
  persistCreatorProfile(existing);
  if (!creatorModalEl || !creatorProfileInputEl || !creatorProfileSaveBtn) return;

  if (creatorProfile) {
    closeCreatorProfileModal();
  } else {
    openCreatorProfileModal(false);
  }

  creatorProfileSaveBtn.addEventListener("click", () => {
    const text = creatorProfileInputEl.value.trim();
    if (!creatorProfileModalIsEdit && !text) return;
    persistCreatorProfile(text);
    closeCreatorProfileModal();
  });

  if (creatorProfileEditBtn) {
    creatorProfileEditBtn.addEventListener("click", () => openCreatorProfileModal(true));
  }

  creatorProfileInputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      creatorProfileSaveBtn.click();
    }
  });
}

function refreshChartsForTheme() {
  if (!lastDashboardPayload?.analysis) return;
  const a = lastDashboardPayload.analysis;
  renderDurationChart(a.duration_patterns || []);
  renderUploadChart(a.upload_frequency || []);
  renderSponsor(a.sponsorship || {});
}

function observeRevealElements() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    document.querySelectorAll(".reveal-on-scroll").forEach((el) => el.classList.add("is-visible"));
    return;
  }
  if (!scrollObserver) return;
  document.querySelectorAll(".reveal-on-scroll:not([data-reveal-observed])").forEach((el) => {
    el.dataset.revealObserved = "1";
    scrollObserver.observe(el);
  });
}

function setLoadingStep(stepIndex) {
  if (!loadingEl) return;
  const steps = loadingEl.querySelectorAll(".loading-step");
  const fill = document.getElementById("loading-bar-fill");
  const n = steps.length || 3;
  steps.forEach((el, i) => {
    el.classList.toggle("is-active", i === stepIndex);
    el.classList.toggle("is-done", i < stepIndex);
  });
  if (fill) {
    const pct = Math.min(100, ((stepIndex + 1) / n) * 100);
    fill.style.width = `${pct}%`;
  }
}

function setLoadingVisible(visible) {
  if (!loadingEl) return;
  loadingEl.classList.toggle("hidden", !visible);
  loadingEl.setAttribute("aria-busy", visible ? "true" : "false");
  if (visible) setLoadingStep(0);
}

function initDashboardTabs() {
  const tabButtons = document.querySelectorAll(".rail-nav-link[data-tab]");
  const panels = document.querySelectorAll("[data-tab-panel]");
  if (!tabButtons.length || !panels.length) return;

  function resizeAnalysisCharts() {
    requestAnimationFrame(() => {
      durationChart?.resize();
      uploadChart?.resize();
      sponsorChart?.resize();
    });
  }

  function setActiveTab(tabName) {
    tabButtons.forEach((btn) => {
      const sel = btn.dataset.tab === tabName;
      btn.setAttribute("aria-selected", sel ? "true" : "false");
      btn.tabIndex = sel ? 0 : -1;
    });
    panels.forEach((panel) => {
      const show = panel.dataset.tabPanel === tabName;
      panel.hidden = !show;
    });
    if (tabName === "analysis") {
      resizeAnalysisCharts();
    }
  }

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      setActiveTab(btn.dataset.tab || "analysis");
    });
  });

  tabButtons.forEach((btn) => {
    btn.addEventListener("keydown", (e) => {
      const keys = ["ArrowLeft", "ArrowRight", "Home", "End"];
      if (!keys.includes(e.key)) return;
      e.preventDefault();
      const tabs = Array.from(tabButtons);
      const cur = tabs.findIndex((b) => b.getAttribute("aria-selected") === "true");
      let next = cur >= 0 ? cur : 0;
      if (e.key === "ArrowRight") next = (next + 1) % tabs.length;
      else if (e.key === "ArrowLeft") next = (next - 1 + tabs.length) % tabs.length;
      else if (e.key === "Home") next = 0;
      else if (e.key === "End") next = tabs.length - 1;
      tabs[next].focus();
      setActiveTab(tabs[next].dataset.tab || "analysis");
    });
  });

  window.__viralbiteSetActiveTab = setActiveTab;
}

/** Chart.js measures 0×0 when the analysis tab is hidden; prime after first render. */
function primeChartsAfterDashboardRender() {
  if (!dashboardEl || !window.__viralbiteSetActiveTab) return;
  dashboardEl.style.visibility = "hidden";
  window.__viralbiteSetActiveTab("analysis");
  requestAnimationFrame(() => {
    durationChart?.resize();
    uploadChart?.resize();
    sponsorChart?.resize();
    window.__viralbiteSetActiveTab("analysis");
    dashboardEl.style.visibility = "";
  });
}

function initScrollReveal() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    document.querySelectorAll(".reveal-on-scroll").forEach((el) => el.classList.add("is-visible"));
    return;
  }
  scrollObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) e.target.classList.add("is-visible");
      });
    },
    { threshold: 0.06, rootMargin: "0px 0px -28px 0px" }
  );
  observeRevealElements();
}

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
  topics.forEach((entry, idx) => {
    const topic = entry.topic || entry;
    const btn = document.createElement("button");
    const variant = PILL_VARIANTS[idx % PILL_VARIANTS.length];
    btn.className = `topic-pill pill pill--${variant}`;
    btn.type = "button";
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

  const C = chartPalette();
  const filtered = (patterns || []).filter(
    (p) => p.duration_bucket && String(p.duration_bucket) !== "0-60s"
  );

  const sumEl = document.getElementById("duration-chart-summary");
  if (sumEl) {
    const totalN = filtered.reduce((a, p) => a + (p.video_count || 0), 0);
    sumEl.textContent = filtered.length
      ? `${filtered.length} buckets · ${fmt(totalN, 0)} videos counted (line shows n per bucket).`
      : "No duration buckets after filtering short clips.";
  }

  durationChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: filtered.map((p) => p.duration_bucket),
      datasets: [
        {
          label: "Avg engagement rate",
          data: filtered.map((p) => (p.avg_engagement_rate || 0) * 100),
          backgroundColor: C.paprika,
          borderRadius: 8,
          yAxisID: "y",
          order: 0,
        },
        {
          label: "Video count (n)",
          data: filtered.map((p) => p.video_count || 0),
          type: "line",
          borderColor: C.brick,
          backgroundColor: "transparent",
          pointBackgroundColor: C.brick,
          pointBorderColor: "#ffffff",
          pointBorderWidth: 2,
          pointRadius: 5,
          pointHoverRadius: 6,
          borderWidth: 3,
          tension: 0.25,
          yAxisID: "yCount",
          order: 1,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { top: 10, right: 8, bottom: 6, left: 4 } },
      datasets: {
        bar: {
          categoryPercentage: 0.65,
          barPercentage: 0.88,
        },
      },
      plugins: {
        legend: {
          display: true,
          labels: { color: C.legend, font: { size: 12, family: "'DM Sans', sans-serif" } },
        },
        tooltip: {
          callbacks: {
            afterBody(context) {
              const idx = context?.[0]?.dataIndex ?? 0;
              const median = filtered[idx]?.median_engagement_rate;
              if (typeof median === "number") {
                return [`Median engagement: ${fmt(median * 100, 2)}%`];
              }
              return [];
            },
          },
        },
      },
      scales: {
        x: {
          ticks: { color: C.tick, font: { size: 11 } },
          grid: { color: C.grid },
        },
        y: {
          ticks: { color: C.tick, callback: (v) => `${v}%` },
          grid: { color: C.grid },
        },
        yCount: {
          position: "right",
          grid: { drawOnChartArea: false },
          ticks: { precision: 0, color: C.tick },
        },
      },
    },
    plugins: [
      {
        id: "lineOnTop",
        afterDatasetsDraw(chart) {
          const meta = chart.getDatasetMeta(1);
          if (meta?.type === "line" && meta.controller) {
            meta.controller.draw();
          }
        },
      },
    ],
  });
}

function renderUploadChart(uploadFrequency) {
  const ctx = document.getElementById("uploadChart");
  if (uploadChart) uploadChart.destroy();

  const C = chartPalette();
  const uploadSumEl = document.getElementById("upload-chart-summary");
  if (uploadSumEl) {
    const total = (uploadFrequency || []).reduce((a, x) => a + (x.video_count || 0), 0);
    uploadSumEl.textContent = (uploadFrequency || []).length
      ? `${uploadFrequency.length} weeks · ${fmt(total, 0)} uploads in window.`
      : "";
  }

  uploadChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: uploadFrequency.map((x) => x.week),
      datasets: [
        {
          label: "Videos published",
          data: uploadFrequency.map((x) => x.video_count),
          backgroundColor: C.chili,
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { top: 8, right: 6, bottom: 4, left: 4 } },
      plugins: { legend: { display: false } },
      scales: {
        x: {
          ticks: { color: C.tick, maxRotation: 45, minRotation: 0, font: { size: 10 } },
          grid: { color: C.grid },
        },
        y: {
          beginAtZero: true,
          ticks: { precision: 0, color: C.tick },
          grid: { color: C.grid },
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
    .forEach((row, idx) => {
      const chip = document.createElement("div");
      const variant = PILL_VARIANTS[idx % PILL_VARIANTS.length];
      chip.className = `keyword-chip pill pill--${variant}`;
      const keywordName = truncateText(row.keyword, 22);
      const meta = `${fmt((row.avg_engagement_rate || 0) * 100, 2)}% eng · ${row.video_count} videos`;
      chip.innerHTML = `<strong>${keywordName}</strong><span class="keyword-chip-meta">${meta}</span>`;
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

  if (sentimentLegendEl) {
    sentimentLegendEl.innerHTML = `
      <span class="sent-legend-item"><span class="sent-swatch positive" aria-hidden="true"></span>Positive</span>
      <span class="sent-legend-item"><span class="sent-swatch neutral" aria-hidden="true"></span>Neutral</span>
      <span class="sent-legend-item"><span class="sent-swatch negative" aria-hidden="true"></span>Negative</span>
    `;
  }

  const themes = (sentiment.top_positive_themes || []).join(", ") || "n/a";
  sentimentMetaEl.textContent = "";
  const lead = document.createElement("span");
  lead.className = "insight-meta-lead";
  lead.textContent = `Analyzed ${sentiment.num_comments_analyzed || 0} comments · Top comment themes: `;
  const em = document.createElement("strong");
  em.className = "insight-meta-em";
  em.textContent = themes;
  sentimentMetaEl.appendChild(lead);
  sentimentMetaEl.appendChild(em);
}

function renderSponsor(sponsorship) {
  const ctx = document.getElementById("sponsorChart");
  if (sponsorChart) sponsorChart.destroy();

  const C = chartPalette();
  const spCount = sponsorship.sponsored_count || 0;
  const orgCount = sponsorship.organic_count || 0;
  const total = spCount + orgCount;
  const spPct = total ? (spCount / total) * 100 : 0;
  const orgPct = total ? (orgCount / total) * 100 : 0;

  if (sponsorLegendEl) {
    sponsorLegendEl.innerHTML = `
    <div class="sponsor-legend-row">
      <span class="sponsor-swatch sponsored" aria-hidden="true"></span>
      <span class="sponsor-legend-label">Sponsored</span>
      <span class="sponsor-legend-pct">${fmt(spPct, 0)}%</span>
    </div>
    <div class="sponsor-legend-row">
      <span class="sponsor-swatch organic" aria-hidden="true"></span>
      <span class="sponsor-legend-label">Organic</span>
      <span class="sponsor-legend-pct">${fmt(orgPct, 0)}%</span>
    </div>
  `;
  }

  sponsorChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Sponsored", "Organic"],
      datasets: [
        {
          data: [spCount, orgCount],
          backgroundColor: [C.chili, C.saffron],
          borderWidth: 0,
          hoverOffset: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { top: 6, right: 6, bottom: 6, left: 6 } },
      cutout: "58%",
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label(ctx) {
              const v = ctx.raw || 0;
              const p = total ? ((v / total) * 100).toFixed(1) : "0";
              return `${ctx.label}: ${fmt(v, 0)} (${p}%)`;
            },
          },
        },
      },
    },
  });

  const sv = sponsorship.sponsored_avg_views || 0;
  const ov = sponsorship.organic_avg_views || 0;
  const se = sponsorship.sponsored_avg_engagement || 0;
  const oe = sponsorship.organic_avg_engagement || 0;

  let metaHtml = "";
  if (total === 0) {
    metaHtml = `<span class="insight-meta-lead">No videos in sample.</span>`;
  } else if (spCount === 0) {
    metaHtml = `<span class="insight-meta-lead">No sponsored videos detected in this sample.</span>`;
  } else if (orgCount === 0) {
    metaHtml = `<span class="insight-meta-lead">All sampled videos are marked sponsored.</span>`;
  } else if (ov > 0 && oe > 0) {
    const vx = sv / ov;
    const ex = se / oe;
    metaHtml =
      `<span class="insight-meta-lead">Sponsored videos average </span>` +
      `<strong class="insight-meta-em">${fmt(vx, 1)}×</strong>` +
      `<span class="insight-meta-lead"> higher views but </span>` +
      `<strong class="insight-meta-em">${fmt(ex, 1)}×</strong>` +
      `<span class="insight-meta-lead"> the engagement rate vs organic.</span>`;
  } else {
    metaHtml =
      `<span class="insight-meta-lead">Avg views — sponsored </span>` +
      `<strong class="insight-meta-em">${fmt(sv, 0)}</strong>` +
      `<span class="insight-meta-lead"> · organic </span>` +
      `<strong class="insight-meta-em">${fmt(ov, 0)}</strong>` +
      `<span class="insight-meta-lead"> · engagement </span>` +
      `<strong class="insight-meta-em">${fmt(se * 100, 2)}%</strong>` +
      `<span class="insight-meta-lead"> vs </span>` +
      `<strong class="insight-meta-em">${fmt(oe * 100, 2)}%</strong>`;
  }

  sponsorMetaEl.innerHTML = metaHtml;
}

function renderTopVideos(videos) {
  topVideosBodyEl.innerHTML = "";
  videos.forEach((video, idx) => {
    const tr = document.createElement("tr");
    const vid = video.video_id != null ? String(video.video_id).trim() : "";
    const titleText = video.title || "Untitled";
    const titleHtml = escapeHtml(titleText);
    const titleCell =
      vid !== ""
        ? `<a href="https://www.youtube.com/watch?v=${encodeURIComponent(vid)}" class="video-title-link" target="_blank" rel="noopener noreferrer">${titleHtml}</a>`
        : `<strong>${titleHtml}</strong>`;
    tr.innerHTML = `
      <td>${idx + 1}</td>
      <td>${titleCell}<div class="muted">${escapeHtml(video.channel_title || "")}</div></td>
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
  if (role === "assistant") {
    bubble.innerHTML = formatChatMarkdown(content);
  } else {
    bubble.textContent = content;
  }
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

function escapeHtml(text) {
  if (text === null || text === undefined) return "";
  const d = document.createElement("div");
  d.textContent = String(text);
  return d.innerHTML;
}

/** Safe subset: **bold** only (after split, segments are escaped). */
function formatInlineMarkdown(text) {
  if (text == null) return "";
  const s = String(text);
  const parts = s.split(/\*\*([^*]+)\*\*/);
  let out = "";
  for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 0) out += escapeHtml(parts[i]);
    else out += `<strong class="brief-em">${escapeHtml(parts[i])}</strong>`;
  }
  return out;
}

/** Chat bubbles: paragraphs + line breaks + **bold** (same rules as inline markdown). */
function formatChatMarkdown(text) {
  if (text == null) return "";
  const raw = String(text).trim();
  if (!raw) return "";
  const blocks = raw.split(/\n\n+/).map((b) => b.trim()).filter(Boolean);
  if (!blocks.length) return "";
  return blocks
    .map((block) => {
      const lines = block.split("\n").map((line) => formatInlineMarkdown(line));
      return `<p class="chat-md-p">${lines.join("<br>")}</p>`;
    })
    .join("");
}

function renderBriefProseParagraphs(text) {
  const paras = String(text || "")
    .split(/\n\n+/)
    .map((p) => p.trim())
    .filter(Boolean);
  if (!paras.length) return `<p class="brief-prose"><span class="brief-prose-muted">—</span></p>`;
  return paras.map((p) => `<p class="brief-prose">${formatInlineMarkdown(p)}</p>`).join("");
}

function renderVideoConceptHtml(text) {
  const raw = String(text || "");
  const lines = raw.split(/\n/);
  let html = "";
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const colonIdx = trimmed.indexOf(":");
    if (colonIdx > 0 && colonIdx < 56) {
      const before = trimmed.slice(0, colonIdx).trim();
      const after = trimmed.slice(colonIdx + 1).trim();
      const wordCount = before.split(/\s+/).length;
      if (
        wordCount <= 8 &&
        before.length <= 52 &&
        /^[A-Za-z]/.test(before) &&
        !/^\d/.test(before.trim())
      ) {
        html += `<div class="brief-concept-row">
          <span class="brief-concept-label">${escapeHtml(before)}</span>
          <div class="brief-concept-value">${formatInlineMarkdown(after)}</div>
        </div>`;
        continue;
      }
    }
    if (/^\d+\.\s/.test(trimmed)) {
      const rest = trimmed.replace(/^\d+\.\s+/, "");
      html += `<div class="brief-concept-step">${formatInlineMarkdown(rest)}</div>`;
      continue;
    }
    html += `<p class="brief-concept-lead">${formatInlineMarkdown(trimmed)}</p>`;
  }
  const inner = html || `<p class="brief-prose">${formatInlineMarkdown(raw)}</p>`;
  return `<div class="brief-video-concept">${inner}</div>`;
}

function renderProductionBriefHtml(text) {
  const lines = String(text || "").split(/\n/);
  const bullets = [];
  const paras = [];
  for (const line of lines) {
    const t = line.trim();
    if (!t) continue;
    if (t.startsWith("- ") || t.startsWith("• ")) {
      bullets.push(`<li>${formatInlineMarkdown(t.replace(/^[-•]\s+/, ""))}</li>`);
    } else {
      paras.push(`<p class="brief-prose brief-prose-tight">${formatInlineMarkdown(t)}</p>`);
    }
  }
  let out = paras.join("");
  if (bullets.length) {
    out += `<ul class="brief-bullet-list">${bullets.join("")}</ul>`;
  }
  return out || `<p class="brief-prose-muted">—</p>`;
}

function renderCreatorBrief(finalResponse, query) {
  const topic = (query || "").trim() || "topic";
  if (creatorBriefTitleEl) {
    creatorBriefTitleEl.textContent = `Two ${topic} brief ideas for your channel`;
  }

  const brief = finalResponse?.creator_brief || {};
  const ideas = Array.isArray(brief?.ideas)
    ? brief.ideas.filter(Boolean)
    : (brief?.opportunity_statement ? [brief] : []);
  const conf = finalResponse?.brief_confidence || {};

  if (briefConfidenceEl) {
    const chips = [];
    let ci = 0;
    if (conf.sample_size != null) {
      const v = PILL_VARIANTS[ci++ % PILL_VARIANTS.length];
      chips.push(
        `<span class="brief-chip pill pill--${v}" title="Videos in analysis sample">n=${escapeHtml(fmt(conf.sample_size, 0))}</span>`
      );
    }
    if (conf.unique_channels != null) {
      const v = PILL_VARIANTS[ci++ % PILL_VARIANTS.length];
      chips.push(
        `<span class="brief-chip pill pill--${v}" title="Distinct channels">${escapeHtml(fmt(conf.unique_channels, 0))} channels</span>`
      );
    }
    if (conf.top_two_channel_share_pct != null) {
      const v = PILL_VARIANTS[ci++ % PILL_VARIANTS.length];
      chips.push(
        `<span class="brief-chip pill pill--${v}" title="Share of views from the two largest channels">Top 2 ch. ${escapeHtml(fmt(conf.top_two_channel_share_pct, 0))}%</span>`
      );
    }

    if (!chips.length && !conf.message) {
      briefConfidenceEl.classList.add("hidden");
      briefConfidenceEl.innerHTML = "";
    } else {
      briefConfidenceEl.classList.remove("hidden");
      briefConfidenceEl.innerHTML = `
        <div class="brief-confidence-inner">
          ${chips.length ? `<div class="brief-confidence-chips">${chips.join("")}</div>` : ""}
          ${conf.message ? `<p class="brief-confidence-msg">${escapeHtml(conf.message)}</p>` : ""}
        </div>`;
    }
  }

  if (!creatorBriefBodyEl) return;

  if (ideas.length) {
    creatorBriefBodyEl.innerHTML = ideas.slice(0, 2).map((idea, ideaIdx) => {
      const sections = [
        { step: "1", title: "The opportunity", html: renderBriefProseParagraphs(idea.opportunity_statement) },
        { step: "2", title: "The video concept", html: renderVideoConceptHtml(idea.video_concept) },
        { step: "3", title: "The production brief", html: renderProductionBriefHtml(idea.production_brief) },
        { step: "4", title: "The differentiation angle", html: renderBriefProseParagraphs(idea.differentiation_angle) },
      ];
      return `
      <article class="brief-idea-wrap">
        <h3 class="brief-idea-heading">Idea ${ideaIdx + 1}</h3>
        ${sections
          .map(
            (s) => `
          <article class="brief-block-card">
            <header class="brief-block-header">
              <span class="brief-block-step" aria-hidden="true">${escapeHtml(s.step)}</span>
              <h4 class="brief-block-title">${escapeHtml(s.title)}</h4>
            </header>
            <div class="brief-block-content">${s.html}</div>
          </article>`
          )
          .join("")}
      </article>`;
    }).join("");
    return;
  }

  const legacySummary = brief.summary || "No creator summary generated.";
  const recs = brief.recommendations || [];
  creatorBriefBodyEl.innerHTML = `
    <article class="brief-block-card">
      <div class="brief-block-content"><p class="brief-prose">${escapeHtml(legacySummary)}</p></div>
    </article>
    ${recs.length ? `<ul class="brief-legacy-recs">${recs.map((r) => `<li>${escapeHtml(r)}</li>`).join("")}</ul>` : ""}
  `;
}

function renderDashboard(payload) {
  lastDashboardPayload = payload;
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
  renderCreatorBrief(payload.final_response || {}, payload.query);

  dashboardEl.classList.remove("hidden");
  if (window.__viralbiteSetActiveTab) {
    window.__viralbiteSetActiveTab("analysis");
  }
  primeChartsAfterDashboardRender();
  observeRevealElements();
}

/** Lets the browser paint loading steps before the next microtask-heavy work. */
function loadingYield(ms = 140) {
  return new Promise((resolve) => {
    requestAnimationFrame(() => {
      setTimeout(resolve, ms);
    });
  });
}

async function runAnalysis(topic) {
  const query = topic?.trim();
  if (!query) return;
  if (!creatorProfile) {
    openCreatorProfileModal(false);
    return;
  }
  setLoadingVisible(true);
  analyzeBtn.disabled = true;
  try {
    const params = new URLSearchParams({
      query,
      days: String(DEFAULT_ANALYZE_PARAMS.days),
      max_videos: String(DEFAULT_ANALYZE_PARAMS.max_videos),
      order: DEFAULT_ANALYZE_PARAMS.order,
      max_pages: String(DEFAULT_ANALYZE_PARAMS.max_pages),
      max_comments: String(DEFAULT_ANALYZE_PARAMS.max_comments),
      creator_profile: creatorProfile,
    });
    const response = await fetch(`/analyze?${params.toString()}`);
    setLoadingStep(1);
    await loadingYield();
    const data = await response.json();
    setLoadingStep(2);
    await loadingYield();
    renderDashboard(data);
  } catch (error) {
    console.error(error);
    alert("Analysis failed. Check your API keys and try again.");
  } finally {
    setLoadingVisible(false);
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

initTheme();
initCreatorProfileModal();
initScrollReveal();
initThemeToggle();
initDashboardTabs();
window.addEventListener("viralbite-theme-change", refreshChartsForTheme);
loadHomepageTopics().then(() => observeRevealElements());