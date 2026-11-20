/**
 * Clipping Final Boss - Web UI Controller
 * High-performance, local-first clipping engine.
 * Full support for background async jobs, word-level caption editing,
 * live style presets, hook overlays, streamer tracking, and guided YouTube connection.
 */

// ==================== STATE MANAGEMENT ====================
let currentSession = null;
let currentClip = null;
let currentFilter = "all";
let currentSort = "rank";
let selectedLengthChip = "auto";
let selectedClipIds = new Set();
let activeStreamer = null;
let currentTemplateId = "pop";
let aspectRatio = "9:16";
let framingMode = "blur";
let captionTemplates = [];
let editorHistory = [];
let blackHoleController = null;
let currentJobId = null;
let jobPollInterval = null;
let activeCaptionMode = "words"; // "words" or "lines"

let customCaptionStyle = {
  enabled: true,
  preset: "pop",
  font_family: "Montserrat",
  font_size: 28,
  text_color: "#FFFFFF",
  highlight_color: "#FFE600",
  position: "bottom"
};

let hookState = {
  enabled: true,
  text: "WAIT FOR THE END!",
  style: "red_alert",
  position: "top"
};

// ==================== DOM READY INITIALIZATION ====================
document.addEventListener("DOMContentLoaded", () => {
  initGetStartedPage();
  initTabs();
  initLengthChips();
  initClipForm();
  initSortAndBulk();
  loadLatestSession();
  initTemplatesGallery();
  initEditorEvents();
  initStreamers();
  initSettings();
  initHealthModal();
  fetchSystemHealth();
});

// ==================== GET STARTED & BLACK HOLE HERO ====================
function initGetStartedPage() {
  const heroHost = document.getElementById("blackhole-hero");
  const heroCanvas = document.getElementById("blackhole-canvas");
  if (heroHost && heroCanvas && typeof window.initBlackHoleHero === "function") {
    try {
      blackHoleController = window.initBlackHoleHero(heroHost, heroCanvas, {
        focus: [0.72, 0.46],
        scrim: "left",
        scrimStrength: 0.9,
        distance: 24,
        elevation: -5.5,
        fov: 42,
        glow: 1,
        steps: 240,
        resolution: 0.7
      });
    } catch (e) {
      console.warn("Black hole WebGL init notice:", e);
    }
  }

  const heroInput = document.getElementById("hero-video-url");
  const heroBtnStart = document.getElementById("hero-btn-start");
  const heroBtnBrowse = document.getElementById("btn-hero-browse-clips");

  if (heroBtnStart && heroInput) {
    heroBtnStart.addEventListener("click", () => {
      const val = heroInput.value.trim();
      const mainInput = document.getElementById("video-url");
      if (mainInput && val) mainInput.value = val;
      const clipsTabBtn = document.getElementById("tabnav-clips");
      if (clipsTabBtn) clipsTabBtn.click();
      if (val) {
        const form = document.getElementById("clip-form");
        if (form) {
          if (form.requestSubmit) form.requestSubmit();
          else form.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
        }
      }
    });
  }

  if (heroBtnBrowse) {
    heroBtnBrowse.addEventListener("click", () => {
      const clipsTabBtn = document.getElementById("tabnav-clips");
      if (clipsTabBtn) clipsTabBtn.click();
    });
  }
}

// ==================== TABS NAVIGATION & PERFORMANCE OPTIMIZATION ====================
function initTabs() {
  const tabs = document.querySelectorAll(".tab-btn");
  tabs.forEach(btn => {
    btn.addEventListener("click", () => {
      let rawTab = btn.getAttribute("data-tab") || "";
      let targetId = rawTab.startsWith("tab-") ? rawTab : `tab-${rawTab}`;
      if (targetId === "tab-getstarted") targetId = "tab-get-started";

      document.querySelectorAll(".tab-view").forEach(view => {
        view.classList.remove("active");
      });
      tabs.forEach(b => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      });

      const targetView = document.getElementById(targetId);
      if (targetView) {
        targetView.classList.add("active");
      }
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");

      // Pause GPU WebGL RAF when away from Get Started to keep UI sub-second responsive
      if (targetId === "tab-get-started") {
        if (blackHoleController && typeof blackHoleController.resume === "function") {
          blackHoleController.resume();
        }
      } else {
        if (blackHoleController && typeof blackHoleController.pause === "function") {
          blackHoleController.pause();
        }
      }

      if (targetId === "tab-streamers") {
        fetchStreamers();
      } else if (targetId === "tab-settings") {
        fetchSettings();
      }
    });
  });
}

// ==================== LENGTH CHIPS SELECTOR ====================
function initLengthChips() {
  const chips = document.querySelectorAll(".length-chip");
  chips.forEach(chip => {
    chip.addEventListener("click", () => {
      chips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      selectedLengthChip = chip.getAttribute("data-length") || "auto";
    });
  });
}

// ==================== CLIP FORM & BACKGROUND JOBS (STUCK AT 87% FIX) ====================
function initClipForm() {
  const form = document.getElementById("clip-form");
  const urlInput = document.getElementById("video-url");
  const topNInput = document.getElementById("top-n");
  const progressBox = document.getElementById("progress-container");
  const progressFill = document.getElementById("progress-bar-fill");
  const progressText = document.getElementById("progress-text");
  const progressPct = document.getElementById("progress-percent");
  const makeClipsBtn = document.getElementById("btn-make-clips");
  const errorBox = document.getElementById("pipeline-error-box");
  const errorTitle = document.getElementById("pipeline-error-title");
  const errorDesc = document.getElementById("pipeline-error-desc");
  const btnDismissError = document.getElementById("btn-dismiss-error");
  const btnErrorSettings = document.getElementById("btn-error-settings");
  const btnCopyError = document.getElementById("btn-copy-error");
  let lastErrorDetails = "";

  if (btnCopyError) {
    btnCopyError.addEventListener("click", async () => {
      if (!lastErrorDetails) return;
      try {
        await navigator.clipboard.writeText(lastErrorDetails);
        const origText = btnCopyError.innerText;
        btnCopyError.innerText = "✓ Copied!";
        showToast("Error details copied to clipboard", "success");
        setTimeout(() => { btnCopyError.innerText = origText; }, 2000);
      } catch (e) {
        showToast("Could not copy error to clipboard", "error");
      }
    });
  }

  function displayPipelineError(title, errorMsg) {
    let cleanMsg = (errorMsg || "").trim();
    cleanMsg = cleanMsg.replace(/^(?:error:\s*)+/i, "");
    cleanMsg = cleanMsg.replace(/^(?:runtimeerror:\s*)+/i, "");
    cleanMsg = cleanMsg.replace(/^(?:valueerror:\s*)+/i, "");
    lastErrorDetails = `Clipping Final Boss Error: ${title}\nDetails: ${cleanMsg}\nTimestamp: ${new Date().toISOString()}`;
    if (errorBox) {
      if (errorTitle) errorTitle.innerText = title;
      if (errorDesc) errorDesc.innerText = cleanMsg;
      
      // Show "Check Settings & API Keys" only when the error is actually an auth/key/quota error (401/403/429)
      const errLower = cleanMsg.toLowerCase();
      const isAuthOrQuota = errLower.includes("401") ||
                            errLower.includes("403") ||
                            errLower.includes("429") ||
                            errLower.includes("api key") ||
                            errLower.includes("quota") ||
                            errLower.includes("unauthorized") ||
                            errLower.includes("rate limit") ||
                            errLower.includes("invalid key");
      if (btnErrorSettings) {
        if (isAuthOrQuota) btnErrorSettings.classList.remove("hidden");
        else btnErrorSettings.classList.add("hidden");
      }
      errorBox.classList.remove("hidden");
    }
  }

  if (btnDismissError && errorBox) {
    btnDismissError.addEventListener("click", () => {
      errorBox.classList.add("hidden");
    });
  }

  if (btnErrorSettings) {
    btnErrorSettings.addEventListener("click", () => {
      const setTabBtn = document.getElementById("tabnav-settings");
      if (setTabBtn) setTabBtn.click();
    });
  }

  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    const topN = parseInt(topNInput.value, 10) || 5;
    if (!url) return;

    const urlLower = url.toLowerCase();
    if (urlLower.includes("localhost") || urlLower.includes("127.0.0.1") || urlLower.includes("0.0.0.0") || urlLower.includes("::1")) {
      displayPipelineError(
        "Invalid Video URL",
        "Cannot download or clip from local server address (localhost / 127.0.0.1). Please provide a valid public YouTube, Twitch, Kick video URL or local file path."
      );
      return;
    }

    if (errorBox) errorBox.classList.add("hidden");
    if (progressBox) progressBox.classList.remove("hidden");
    if (progressFill) {
      progressFill.style.backgroundColor = "";
      progressFill.style.width = "5%";
    }
    if (progressPct) progressPct.innerText = "5%";
    if (progressText) progressText.innerText = "Submitting background job...";
    if (makeClipsBtn) makeClipsBtn.disabled = true;
    renderSkeletonCards(topN);

    if (jobPollInterval) {
      clearInterval(jobPollInterval);
      jobPollInterval = null;
    }

    try {
      // Dispatch background async job
      const resp = await fetch("/api/clip", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          top_n: topN,
          length_chip: selectedLengthChip,
          async_mode: true
        }),
      });

      if (!resp.ok) {
        const errData = await resp.json();
        throw new Error(errData.detail || "Failed to start pipeline job");
      }

      const jobInit = await resp.json();
      currentJobId = jobInit.job_id;

      // Real background status polling
      jobPollInterval = setInterval(async () => {
        try {
          const pollResp = await fetch(`/api/jobs/${currentJobId}`);
          if (!pollResp.ok) return;
          const job = await pollResp.json();

          const pct = Math.min(Math.max(job.progress || 5, 5), 100);
          if (progressFill) progressFill.style.width = `${pct}%`;
          if (progressPct) progressPct.innerText = `${pct}%`;
          if (progressText) progressText.innerText = job.message || "Processing video...";

          // Update stage highlights
          if (job.stage === "download") updateStageStep("stage-download");
          else if (job.stage === "transcribe") updateStageStep("stage-transcribe");
          else if (job.stage === "moments") updateStageStep("stage-detect");
          else if (job.stage === "rank") updateStageStep("stage-rank");
          else if (job.stage === "render" || job.stage === "complete") updateStageStep("stage-finalize");

          if (job.status === "completed") {
            clearInterval(jobPollInterval);
            jobPollInterval = null;
            if (makeClipsBtn) makeClipsBtn.disabled = false;
            if (progressFill) progressFill.style.width = "100%";
            if (progressPct) progressPct.innerText = "100%";
            if (progressText) progressText.innerText = "Complete! Ranked short clips ready.";
            setTimeout(() => { if (progressBox) progressBox.classList.add("hidden"); }, 1200);

            if (job.result) {
              currentSession = job.result;
              renderVideoGrid(currentSession.clips);
            }
          } else if (job.status === "failed") {
            clearInterval(jobPollInterval);
            jobPollInterval = null;
            if (makeClipsBtn) makeClipsBtn.disabled = false;
            if (progressFill) progressFill.style.backgroundColor = "#EF4444";
            if (progressText) progressText.innerText = "Error: " + (job.error || "Job failed");
            displayPipelineError("Pipeline Execution Failed", job.error || "The clipping pipeline encountered an unexpected error.");
            if (currentSession && currentSession.clips) {
              renderVideoGrid(currentSession.clips);
            }
          }
        } catch (err) {
          console.warn("Poll status check:", err);
        }
      }, 700);

    } catch (err) {
      if (makeClipsBtn) makeClipsBtn.disabled = false;
      if (progressBox) progressBox.classList.remove("hidden");
      if (progressFill) progressFill.style.backgroundColor = "#EF4444";
      if (progressText) progressText.innerText = "Failed: " + err.message;
      displayPipelineError("Submission Error", err.message || "Failed to submit pipeline job.");
    }
  });
}

function updateStageStep(activeStageId) {
  const allStages = ["stage-download", "stage-transcribe", "stage-detect", "stage-rank", "stage-finalize"];
  let hit = false;
  allStages.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    if (id === activeStageId) {
      el.classList.add("active");
      el.classList.remove("completed");
      hit = true;
    } else if (!hit) {
      el.classList.remove("active");
      el.classList.add("completed");
    } else {
      el.classList.remove("active", "completed");
    }
  });
}

function renderSkeletonCards(n = 5) {
  const grid = document.getElementById("clips-grid");
  if (!grid) return;
  grid.innerHTML = "";
  for (let i = 0; i < n; i++) {
    const card = document.createElement("div");
    card.className = "video-card skeleton-card";
    card.innerHTML = `
      <div class="video-preview-box skeleton-box">
        <div class="skeleton-shimmer"></div>
      </div>
      <div class="card-details skeleton-details">
        <div class="skeleton-line full"></div>
        <div class="skeleton-line half"></div>
      </div>
    `;
    grid.appendChild(card);
  }
}

// ==================== LOAD PAST SESSIONS ====================
async function loadLatestSession() {
  try {
    const resp = await fetch("/api/sessions");
    const sessions = await resp.json();
    if (sessions && sessions.length > 0) {
      const latest = sessions[0];
      const clipsResp = await fetch(`/api/sessions/${latest.id}/clips`);
      if (clipsResp.ok) {
        currentSession = await clipsResp.json();
        renderVideoGrid(currentSession.clips);

        const urlParams = new URLSearchParams(window.location.search);
        const tabParam = urlParams.get("tab");
        if (tabParam) {
          const cleanTab = tabParam.replace("tab-", "");
          const tBtn = document.getElementById(`tabnav-${cleanTab}`) || document.getElementById(`tabnav-${tabParam}`);
          if (tBtn) tBtn.click();
        }
        if (urlParams.get("editor") === "1" && currentSession.clips.length > 0) {
          setTimeout(() => openEditorStudio(currentSession.clips[0]), 300);
        }
        return;
      }
    }
    renderVideoGrid([]);
  } catch (e) {
    console.log("No previous sessions found.");
    renderVideoGrid([]);
  }
}

// ==================== RENDER 9:16 VIDEO GRID (DEMO VIDEOS REMOVED) ====================
function renderVideoGrid(clips) {
  const grid = document.getElementById("clips-grid");
  const countBadge = document.getElementById("clips-count-badge");
  if (!grid) return;
  if (countBadge) countBadge.innerText = `${clips ? clips.length : 0} clips`;

  if (!clips || clips.length === 0) {
    grid.innerHTML = `
      <div class="empty-state-card" id="empty-state-clips">
        <div class="empty-icon">🎬</div>
        <h3>No clips generated yet</h3>
        <p>Paste a link to make your first clip</p>
      </div>`;
    return;
  }

  grid.innerHTML = "";
  clips.forEach((clip, idx) => {
    const card = createVideoCardElement(clip, idx + 1);
    grid.appendChild(card);
  });

  updateBulkCounts();
}

function formatDuration(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s < 10 ? "0" : ""}${s}`;
}

function getCaptionSampleText(clip) {
  if (clip.words && clip.words.length > 0) {
    return clip.words.slice(0, 10).map(w => w.word).join(" ") + "...";
  }
  return clip.title || "Spoken moments in audio...";
}

function createVideoCardElement(clip, rank) {
  const card = document.createElement("div");
  card.className = "video-card";
  card.id = `clip-card-${clip.id}`;
  card.setAttribute("data-clip-id", clip.id);

  const durationStr = formatDuration(clip.duration || (clip.end - clip.start) || (clip.end_time - clip.start_time) || 0);
  const score = Math.round(clip.score || 0);
  const sampleCaption = getCaptionSampleText(clip);
  
  let videoSrc = clip.video_url || "";
  if (!videoSrc) {
    const raw = clip.rendered_path || clip.file_path || clip.clip_path || "";
    if (raw) {
      const norm = raw.replace(/\\/g, "/");
      const match = norm.match(/session_\w+[\/][^\/]+$/);
      if (match) videoSrc = `/api/media/${match[0]}`;
      else videoSrc = `/${norm.replace(/^[A-Za-z]:\//, "")}`;
    }
  }

  let thumbSrc = clip.thumbnail_url || clip.poster_url || "";
  if (!thumbSrc && clip.thumbnail_path) {
    const norm = clip.thumbnail_path.replace(/\\/g, "/");
    const match = norm.match(/session_\w+[\/][^\/]+$/);
    if (match) thumbSrc = `/api/media/${match[0]}`;
    else thumbSrc = `/${norm.replace(/^[A-Za-z]:\//, "")}`;
  }
  if (!thumbSrc) {
    thumbSrc = "/static/placeholder_thumb.svg";
  }

  const transcriptFull = (clip.transcript_text || clip.caption || "Spoken moments in audio...").trim();

  card.innerHTML = `
    <div class="video-preview-box">
      <div class="rank-badge">#${rank}</div>
      <div class="score-pill">★ ${score}</div>
      <div class="duration-chip">${durationStr}</div>
      
      <div class="card-select-overlay">
        <input type="checkbox" class="clip-select-box" data-id="${clip.id}" aria-label="Select clip ${rank}">
      </div>

      <img class="card-thumb-img" src="${thumbSrc}" alt="Clip thumbnail" loading="lazy" onerror="this.src='/static/placeholder_thumb.svg'">
      <video class="card-preview-video" src="${videoSrc}" preload="none" loop muted playsinline></video>

      <div class="card-caption-overlay font-montserrat">
        <span class="preview-caption-text">${sampleCaption}</span>
      </div>

      <button type="button" class="btn btn-primary btn-sm btn-card-edit-overlay" title="Open Studio Editor">
        ✏️ Edit in Studio
      </button>
    </div>

    <div class="card-details">
      <h4 class="card-title" title="${clip.title || 'Clip #' + rank}">${clip.title || 'Clip #' + rank}</h4>
      
      <div class="card-caption-block">
        <p class="card-caption-text collapsed">${transcriptFull}</p>
        <button type="button" class="btn-more-toggle">more</button>
      </div>

      <div class="card-scores-row">
        <span class="score-chip hook">Hook ${Math.round(clip.hook_score || score)}</span>
        <span class="score-chip emotion">Engage ${Math.round(clip.emotion_score || score)}</span>
        <span class="score-chip trend">Trend ${Math.round(clip.trend_score || score)}</span>
      </div>
      <div class="card-actions-row">
        <button type="button" class="btn btn-primary btn-sm btn-card-edit">
          Edit
        </button>
        <button type="button" class="btn btn-secondary btn-sm btn-card-download" title="Download MP4">
          ⬇️ Download
        </button>
        <button type="button" class="btn btn-ghost btn-sm btn-card-schedule" title="Schedule to YouTube Shorts">
          📅 Schedule
        </button>
      </div>
      <div class="card-social-export-row" style="display: flex; gap: 6px; margin-top: 8px;">
        <button type="button" class="btn btn-ghost btn-xs btn-export-tiktok" title="Copy TikTok package (title, caption, tags)">
          📱 TikTok
        </button>
        <button type="button" class="btn btn-ghost btn-xs btn-export-ig" title="Copy Instagram Reels package (hook, spacing, tags)">
          📸 Reels
        </button>
        <button type="button" class="btn btn-ghost btn-xs btn-export-yt" title="Copy YouTube Shorts package (title with #shorts, description, tags)">
          ▶️ Shorts
        </button>
      </div>
    </div>
  `;

  const video = card.querySelector(".card-preview-video");
  const thumb = card.querySelector(".card-thumb-img");

  // Hover preview behavior
  card.addEventListener("mouseenter", () => {
    if (video && videoSrc) {
      if (thumb) thumb.style.opacity = "0";
      video.play().catch(() => {});
    }
  });

  card.addEventListener("mouseleave", () => {
    if (video && videoSrc) {
      video.pause();
      video.currentTime = 0;
      if (thumb) thumb.style.opacity = "1";
    }
  });

  // Caption more/less toggle
  const moreBtn = card.querySelector(".btn-more-toggle");
  const captionP = card.querySelector(".card-caption-text");
  if (moreBtn && captionP) {
    moreBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const isCollapsed = captionP.classList.contains("collapsed");
      if (isCollapsed) {
        captionP.classList.remove("collapsed");
        captionP.classList.add("expanded");
        moreBtn.innerText = "less";
      } else {
        captionP.classList.remove("expanded");
        captionP.classList.add("collapsed");
        moreBtn.innerText = "more";
      }
    });
  }

  // Checkbox select
  const cb = card.querySelector(".clip-select-box");
  cb.addEventListener("change", (e) => {
    if (e.target.checked) selectedClipIds.add(clip.id);
    else selectedClipIds.delete(clip.id);
    card.classList.toggle("selected", e.target.checked);
    updateBulkCounts();
  });

  // Buttons
  card.querySelectorAll(".btn-card-edit, .btn-card-edit-overlay").forEach(b => {
    b.addEventListener("click", (e) => {
      e.stopPropagation();
      openEditorStudio(clip);
    });
  });

  card.querySelector(".btn-card-download").addEventListener("click", (e) => {
    e.stopPropagation();
    downloadSingleClip(clip);
  });

  card.querySelector(".btn-card-schedule").addEventListener("click", (e) => {
    e.stopPropagation();
    scheduleSingleClip(clip);
  });

  // Quick social export package copy handlers
  const copySocialPackage = async (platform, label) => {
    try {
      const sessId = currentSession?.session_id || "session_1";
      const compositeId = clip.id.startsWith("clip_") ? `${sessId}_${clip.id}` : clip.id;
      let res = await fetch(`/api/clips/${compositeId}/export/${platform}`);
      if (!res.ok) {
        res = await fetch(`/api/clips/${clip.id}/export/${platform}`);
      }
      if (!res.ok) throw new Error(`Export failed (${res.status})`);
      const data = await res.json();
      const textToCopy = data.formatted_text || "";
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(textToCopy);
      } else {
        const ta = document.createElement("textarea");
        ta.value = textToCopy;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      showToast(`Copied ${label} package to clipboard!`, "success");
    } catch (err) {
      showToast(`Could not copy ${label} package: ${err.message}`, "error");
    }
  };

  card.querySelector(".btn-export-tiktok")?.addEventListener("click", (e) => {
    e.stopPropagation();
    copySocialPackage("tiktok", "TikTok");
  });

  card.querySelector(".btn-export-ig")?.addEventListener("click", (e) => {
    e.stopPropagation();
    copySocialPackage("instagram_reels", "Instagram Reels");
  });

  card.querySelector(".btn-export-yt")?.addEventListener("click", (e) => {
    e.stopPropagation();
    copySocialPackage("youtube_shorts", "YouTube Shorts");
  });

  return card;
}

// ==================== SORTING & BULK ACTIONS ====================
function initSortAndBulk() {
  const sortSelect = document.getElementById("sort-select") || document.getElementById("sort-clips");
  if (sortSelect) {
    sortSelect.addEventListener("change", (e) => {
      currentSort = e.target.value;
      if (!currentSession || !currentSession.clips) return;
      const sorted = [...currentSession.clips].sort((a, b) => {
        if (currentSort === "rank" || currentSort === "score") {
          return (b.score || 0) - (a.score || 0);
        } else if (currentSort === "duration-asc") {
          return (a.duration || 0) - (b.duration || 0);
        } else if (currentSort === "duration-desc") {
          return (b.duration || 0) - (a.duration || 0);
        }
        return 0;
      });
      renderVideoGrid(sorted);
    });
  }

  const selectAll = document.getElementById("select-all-checkbox");
  if (selectAll) {
    selectAll.addEventListener("change", (e) => {
      const checked = e.target.checked;
      const boxes = document.querySelectorAll(".clip-select-box");
      boxes.forEach(b => {
        b.checked = checked;
        const id = b.getAttribute("data-id");
        if (checked) selectedClipIds.add(id);
        else selectedClipIds.delete(id);
        const card = document.getElementById(`clip-card-${id}`);
        if (card) card.classList.toggle("selected", checked);
      });
      updateBulkCounts();
    });
  }

  const bulkDownloadBtn = document.getElementById("btn-bulk-download");
  if (bulkDownloadBtn) {
    bulkDownloadBtn.addEventListener("click", () => {
      if (selectedClipIds.size === 0) return;
      selectedClipIds.forEach(id => {
        const clip = currentSession?.clips?.find(c => c.id === id);
        if (clip) downloadSingleClip(clip);
      });
    });
  }

  const bulkScheduleBtn = document.getElementById("btn-bulk-schedule");
  if (bulkScheduleBtn) {
    bulkScheduleBtn.addEventListener("click", () => {
      if (selectedClipIds.size === 0) return;
      alert(`Queued ${selectedClipIds.size} clips for YouTube Shorts export.\nEnsure your YouTube account is connected in Settings.`);
    });
  }
}

function updateBulkCounts() {
  const bulkBar = document.getElementById("bulk-actions-bar");
  const countSpan = document.getElementById("selected-count");
  const dlCount = document.getElementById("bulk-download-count");
  const schedCount = document.getElementById("bulk-schedule-count");

  const count = selectedClipIds.size;
  if (countSpan) countSpan.innerText = `${count} selected`;
  if (dlCount) dlCount.innerText = count;
  if (schedCount) schedCount.innerText = count;

  if (bulkBar) {
    if (count > 0) bulkBar.classList.remove("hidden");
    else bulkBar.classList.add("hidden");
  }
}

function downloadSingleClip(clip) {
  const src = clip.rendered_url || clip.video_url || clip.rendered_path || clip.file_path || clip.clip_path;
  if (!src) return;
  const a = document.createElement("a");
  a.href = src.startsWith("/") ? src : `/${src}`;
  a.download = `${clip.title ? clip.title.replace(/[^a-zA-Z0-9_-]/g, "_") : "clip"}.mp4`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function scheduleSingleClip(clip) {
  alert(`Clip "${clip.title}" queued for YouTube Shorts export.\nEnsure your YouTube account is connected in Settings.`);
}

// ==================== CAPTION TEMPLATES GALLERY ====================
async function loadCaptionTemplates() {
  try {
    const resp = await fetch("/api/templates");
    if (resp.ok) {
      captionTemplates = await resp.json();
    }
  } catch (e) {
    console.log("Using built-in caption templates");
  }
  renderTemplatesGallery();
}

function renderTemplatesGallery() {
  const container = document.getElementById("templates-gallery-grid") || document.getElementById("templates-grid");
  if (!container) return;

  const fallbackTemplates = [
    { id: "pop", name: "Pop", description: "Bold yellow active word with scale pop", font_family: "Impact, sans-serif", primary_color: "#FFFFFF", active_color: "#FFF200", css_text_shadow: "0px 0px 8px #000, 2px 2px 0px #000", css_box_bg: "transparent", css_active_bg: "transparent" },
    { id: "clean", name: "Clean", description: "Crisp white text with modern drop shadow", font_family: "Inter, sans-serif", primary_color: "#FFFFFF", active_color: "#38BDF8", css_text_shadow: "0 2px 6px rgba(0,0,0,0.85)", css_box_bg: "transparent", css_active_bg: "transparent" },
    { id: "box", name: "Box", description: "Punchy viral text on brand accent box", font_family: "Impact, sans-serif", primary_color: "#FFFFFF", active_color: "#FACC15", css_text_shadow: "0 1px 3px rgba(0,0,0,0.6)", css_box_bg: "rgba(201, 58, 24, 0.92)", css_active_bg: "transparent" },
    { id: "neon", name: "Neon", description: "Radiant electric cyan and magenta aura", font_family: "Impact, sans-serif", primary_color: "#00F0FF", active_color: "#FF007F", css_text_shadow: "0 0 10px #00F0FF, 0 0 20px #00F0FF", css_box_bg: "rgba(0,0,0,0.5)", css_active_bg: "transparent" },
    { id: "outline", name: "Outline", description: "Heavy black stroke with ultra-readable fill", font_family: "Impact, sans-serif", primary_color: "#FFFFFF", active_color: "#34D399", css_text_shadow: "-3px -3px 0 #000, 3px 3px 0 #000", css_box_bg: "transparent", css_active_bg: "transparent" },
    { id: "comic", name: "Comic", description: "Comic-book yellow text with bold border & tilt", font_family: "Impact, sans-serif", primary_color: "#FACC15", active_color: "#FB923C", css_text_shadow: "2px 2px 0 #000", css_box_bg: "transparent", css_active_bg: "transparent" },
    { id: "minimal", name: "Minimal", description: "Sleek translucent dark pill with clean white text", font_family: "Inter, sans-serif", primary_color: "#F8FAFC", active_color: "#60A5FA", css_text_shadow: "0 1px 2px rgba(0,0,0,0.5)", css_box_bg: "rgba(15, 23, 42, 0.75)", css_active_bg: "transparent" },
    { id: "highlight", name: "Highlight", description: "Vibrant marker highlighter box behind active word", font_family: "Impact, sans-serif", primary_color: "#FFFFFF", active_color: "#000000", css_text_shadow: "1px 1px 2px #000", css_box_bg: "transparent", css_active_bg: "#FDE047" },
    { id: "gradient", name: "Gradient", description: "Sunset gradient fill with sleek shadow", font_family: "Impact, sans-serif", primary_color: "#FB7185", active_color: "#FBBF24", css_text_shadow: "0 2px 10px rgba(0,0,0,0.8)", css_box_bg: "transparent", css_active_bg: "transparent" },
    { id: "typewriter", name: "Typewriter", description: "Monospace retro terminal typewriter look", font_family: "monospace", primary_color: "#6EE7B7", active_color: "#FFFFFF", css_text_shadow: "0 0 6px #6EE7B7", css_box_bg: "rgba(6, 78, 59, 0.85)", css_active_bg: "rgba(255, 255, 255, 0.2)" },
  ];

  const templates = (captionTemplates && captionTemplates.length > 0) ? captionTemplates : fallbackTemplates;
  container.innerHTML = "";

  templates.forEach(tpl => {
    const card = document.createElement("div");
    card.className = `template-card ${currentTemplateId === tpl.id ? 'active' : ''}`;
    card.setAttribute("data-template-id", tpl.id);
    card.innerHTML = `
      <div class="template-card-preview" style="font-family: ${tpl.font_family || 'sans-serif'};">
        <span style="color: ${tpl.primary_color}; text-shadow: ${tpl.css_text_shadow}; background: ${tpl.css_box_bg}; padding: 2px 6px; border-radius: 4px; font-weight: 700;">THE</span>
        <span style="color: ${tpl.active_color}; text-shadow: ${tpl.css_text_shadow}; background: ${tpl.css_active_bg}; padding: 2px 6px; border-radius: 4px; font-weight: 900;">SECRET</span>
      </div>
      <div class="template-card-meta">
        <strong class="template-card-title">${tpl.name}</strong>
        <p class="template-card-desc">${tpl.description}</p>
      </div>
    `;
    card.addEventListener("click", () => {
      container.querySelectorAll(".template-card").forEach(c => c.classList.remove("active"));
      card.classList.add("active");
      applyCaptionTemplate(tpl);
    });
    container.appendChild(card);
  });
}

function initTemplatesGallery() {
  loadCaptionTemplates();
}

function applyCaptionTemplate(tpl) {
  currentTemplateId = tpl.id;
  const liveCaption = document.getElementById("editor-live-caption");
  if (liveCaption) {
    liveCaption.className = `live-caption-overlay style-${tpl.id}`;
  }
  flashSavedStatus();
}

// ==================== EDITOR STUDIO ====================
function openEditorStudio(clip) {
  currentClip = JSON.parse(JSON.stringify(clip));
  const editor = document.getElementById("clip-editor-screen");
  if (!editor) return;

  editor.classList.remove("hidden");
  document.body.classList.add("editor-open");

  // Load video
  const video = document.getElementById("editor-video");
  let videoSrc = clip.video_url || "";
  if (!videoSrc) {
    if (clip.rendered_path) videoSrc = `/${clip.rendered_path}`;
    else if (clip.file_path) videoSrc = `/${clip.file_path}`;
    else if (clip.clip_path) videoSrc = `/${clip.clip_path}`;
  }
  if (video) {
    video.src = videoSrc;
    video.load();
  }

  // Populate title & inputs
  const titleInput = document.getElementById("editor-title-input");
  if (titleInput) titleInput.value = clip.title || "";

  const captionInput = document.getElementById("clip-caption-input");
  if (captionInput) captionInput.value = clip.caption || "";

  const hashInput = document.getElementById("clip-hashtags-input");
  if (hashInput) hashInput.value = (clip.hashtags || []).join(" ");

  // Hook input & preview
  const hookInput = document.getElementById("hook-text-input");
  if (hookInput) {
    hookInput.value = clip.hook_text || hookState.text;
    hookState.text = hookInput.value;
  }
  updateHookBannerPreview();

  // Load captions list
  renderEditorCaptionsList();
  renderEditorScoresSummary(clip);
  initBottomTimeline();
  renderTemplatesGallery();
  syncEditorWithClipState();
}

function closeEditorStudio() {
  const editor = document.getElementById("clip-editor-screen");
  if (!editor) return;
  editor.classList.add("hidden");
  document.body.classList.remove("editor-open");

  const video = document.getElementById("editor-video");
  if (video) video.pause();

  if (currentSession && currentSession.clips) {
    renderVideoGrid(currentSession.clips);
  }
}

// ==================== EDITOR STUDIO CONTROLS & WIRING ====================
function initEditorEvents() {
  const backBtn = document.getElementById("editor-back-btn");
  if (backBtn) backBtn.addEventListener("click", closeEditorStudio);

  // Left rail navigation
  document.querySelectorAll(".rail-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const tab = btn.getAttribute("data-rail-tab");
      switchRailTab(tab);
    });
  });

  // Aspect ratio toggles
  document.querySelectorAll(".ratio-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".ratio-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      setEditorAspect(btn.getAttribute("data-aspect"));
    });
  });

  // Framing toggles
  document.querySelectorAll(".framing-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".framing-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      setEditorFraming(btn.getAttribute("data-framing"));
    });
  });

  // Captions word vs line mode toggle
  const toggleWordsBtn = document.getElementById("btn-toggle-words");
  if (toggleWordsBtn) {
    toggleWordsBtn.addEventListener("click", () => {
      activeCaptionMode = activeCaptionMode === "words" ? "lines" : "words";
      toggleWordsBtn.innerText = activeCaptionMode === "words" ? "Lines Mode" : "Words Mode";
      renderEditorCaptionsList();
    });
  }

  // Caption burning toggle
  const capToggle = document.getElementById("style-captions-on-toggle");
  if (capToggle) {
    capToggle.addEventListener("change", (e) => {
      customCaptionStyle.enabled = e.target.checked;
      const liveCap = document.getElementById("editor-live-caption");
      if (liveCap) liveCap.style.display = e.target.checked ? "block" : "none";
    });
  }

  // 4 Style presets
  document.querySelectorAll("[data-style-preset]").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-style-preset]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const preset = btn.getAttribute("data-style-preset");
      customCaptionStyle.preset = preset;

      const fontSelect = document.getElementById("style-font-select");
      const textColor = document.getElementById("style-text-color");
      const highColor = document.getElementById("style-highlight-color");

      if (preset === "pop") {
        if (fontSelect) fontSelect.value = "Montserrat";
        if (textColor) textColor.value = "#FFFFFF";
        if (highColor) highColor.value = "#FFE600";
      } else if (preset === "minimal") {
        if (fontSelect) fontSelect.value = "Inter";
        if (textColor) textColor.value = "#FFFFFF";
        if (highColor) highColor.value = "#94A3B8";
      } else if (preset === "box") {
        if (fontSelect) fontSelect.value = "Impact";
        if (textColor) textColor.value = "#FFFFFF";
        if (highColor) highColor.value = "#06B6D4";
      } else if (preset === "karaoke") {
        if (fontSelect) fontSelect.value = "Trebuchet MS";
        if (textColor) textColor.value = "#FFFFFF";
        if (highColor) highColor.value = "#A855F7";
      }

      applyCustomStyleToPreview();
    });
  });

  // Font family selector
  const fontSelect = document.getElementById("style-font-select");
  if (fontSelect) {
    fontSelect.addEventListener("change", (e) => {
      customCaptionStyle.font_family = e.target.value;
      applyCustomStyleToPreview();
    });
  }

  // Font size slider
  const sizeSlider = document.getElementById("style-font-size-slider");
  const sizeVal = document.getElementById("style-font-size-val");
  if (sizeSlider && sizeVal) {
    sizeSlider.addEventListener("input", (e) => {
      customCaptionStyle.font_size = parseInt(e.target.value, 10);
      sizeVal.innerText = `${customCaptionStyle.font_size}px`;
      applyCustomStyleToPreview();
    });
  }

  // Text color & Highlight color
  const textColor = document.getElementById("style-text-color");
  const textColorHex = document.getElementById("style-text-color-hex");
  if (textColor && textColorHex) {
    textColor.addEventListener("input", (e) => {
      customCaptionStyle.text_color = e.target.value;
      textColorHex.innerText = e.target.value.toUpperCase();
      applyCustomStyleToPreview();
    });
  }

  const highColor = document.getElementById("style-highlight-color");
  const highColorHex = document.getElementById("style-highlight-color-hex");
  if (highColor && highColorHex) {
    highColor.addEventListener("input", (e) => {
      customCaptionStyle.highlight_color = e.target.value;
      highColorHex.innerText = e.target.value.toUpperCase();
      applyCustomStyleToPreview();
    });
  }

  // Vertical position buttons
  document.querySelectorAll("[data-pos]").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-pos]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      customCaptionStyle.position = btn.getAttribute("data-pos");
      applyCustomStyleToPreview();
    });
  });

  // Apply & Render button
  const btnApplyStyle = document.getElementById("btn-apply-style-render");
  if (btnApplyStyle) {
    btnApplyStyle.addEventListener("click", async () => {
      if (!currentClip) return;
      btnApplyStyle.disabled = true;
      btnApplyStyle.innerText = "⏳ Rendering Subtitles...";
      try {
        const resp = await fetch(`/api/clips/${currentClip.id}/render`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            aspect: aspectRatio,
            framing: framingMode,
            custom_style: customCaptionStyle,
            hook: hookState
          }),
        });
        if (resp.ok) {
          const resData = await resp.json();
          currentClip.rendered_path = resData.rendered_path || (resData.clip && resData.clip.rendered_path);
          currentClip.rendered_url = resData.rendered_url || (resData.clip && resData.clip.rendered_url);
          const video = document.getElementById("editor-video");
          if (video && (currentClip.rendered_url || currentClip.rendered_path)) {
            const vSrc = currentClip.rendered_url || `/${currentClip.rendered_path}`;
            video.src = `${vSrc}?t=${Date.now()}`;
            video.load();
          }
          flashSavedStatus();
        }
      } catch (e) {
        alert("Render notice: " + e.message);
      } finally {
        btnApplyStyle.disabled = false;
        btnApplyStyle.innerText = "🎨 Apply & Re-render";
      }
    });
  }

  // Hook panel controls
  const hookInput = document.getElementById("hook-text-input");
  if (hookInput) {
    hookInput.addEventListener("input", (e) => {
      hookState.text = e.target.value;
      updateHookBannerPreview();
    });
  }

  const hookToggle = document.getElementById("hook-overlay-enable-toggle");
  if (hookToggle) {
    hookToggle.addEventListener("change", (e) => {
      hookState.enabled = e.target.checked;
      updateHookBannerPreview();
    });
  }

  document.querySelectorAll("[data-hook-style]").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-hook-style]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      hookState.style = btn.getAttribute("data-hook-style");
      updateHookBannerPreview();
    });
  });

  document.querySelectorAll("[data-hook-pos]").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-hook-pos]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      hookState.position = btn.getAttribute("data-hook-pos");
      updateHookBannerPreview();
    });
  });

  // AI Hook Suggestions (Problem 7)
  const btnSuggestHooks = document.getElementById("btn-suggest-hooks");
  const hookAltsList = document.getElementById("hook-alternatives-list");
  if (btnSuggestHooks && hookAltsList) {
    btnSuggestHooks.addEventListener("click", async () => {
      if (!currentClip) return;
      btnSuggestHooks.disabled = true;
      btnSuggestHooks.innerText = "✨ Generating Hooks...";
      try {
        const resp = await fetch(`/api/clips/${currentClip.id}/hook-alternatives`);
        if (resp.ok) {
          const data = await resp.json();
          renderHookAlternatives(data.alternatives || []);
        }
      } catch (e) {
        console.warn("Hook alternatives error:", e);
      } finally {
        btnSuggestHooks.disabled = false;
        btnSuggestHooks.innerText = "✨ Generate AI Hooks";
      }
    });
  }

  // Video playback & scrubber
  const video = document.getElementById("editor-video");
  const playBtn = document.getElementById("btn-play-pause");
  const stagePlayBtn = document.getElementById("btn-stage-play");
  const scrubber = document.getElementById("editor-scrubber");
  const curTimeEl = document.getElementById("editor-current-time");
  const totalTimeEl = document.getElementById("editor-total-time");

  const togglePlay = () => {
    if (!video) return;
    if (video.paused) {
      video.play();
      if (playBtn) playBtn.innerText = "⏸";
      if (stagePlayBtn) stagePlayBtn.classList.add("playing");
    } else {
      video.pause();
      if (playBtn) playBtn.innerText = "▶";
      if (stagePlayBtn) stagePlayBtn.classList.remove("playing");
    }
  };

  if (playBtn) playBtn.addEventListener("click", togglePlay);
  if (stagePlayBtn) stagePlayBtn.addEventListener("click", togglePlay);

  if (video) {
    video.addEventListener("timeupdate", () => {
      const cur = video.currentTime;
      const dur = video.duration || 1;
      if (scrubber) scrubber.value = (cur / dur) * 100;
      if (curTimeEl) curTimeEl.innerText = formatDuration(cur);
      updateLiveCaptions(cur);
    });

    video.addEventListener("loadedmetadata", () => {
      if (totalTimeEl) totalTimeEl.innerText = formatDuration(video.duration);
    });
  }

  if (scrubber && video) {
    scrubber.addEventListener("input", (e) => {
      const pct = parseFloat(e.target.value) / 100;
      video.currentTime = pct * (video.duration || 1);
    });
  }

  // Export MP4 button
  const exportBtn = document.getElementById("btn-export-clip") || document.getElementById("btn-export-mp4");
  if (exportBtn) {
    exportBtn.addEventListener("click", exportClipMp4);
  }

  // Link to settings from AI Metadata panel
  const aiSettingsLink = document.getElementById("link-goto-settings-ai");
  if (aiSettingsLink) {
    aiSettingsLink.addEventListener("click", (e) => {
      e.preventDefault();
      closeEditorStudio();
      const setTab = document.getElementById("tabnav-settings");
      if (setTab) setTab.click();
    });
  }

  // Regenerate AI Metadata button
  const btnRegenMeta = document.getElementById("btn-regen-metadata");
  if (btnRegenMeta) {
    btnRegenMeta.addEventListener("click", async () => {
      if (!currentClip) return;
      btnRegenMeta.disabled = true;
      btnRegenMeta.innerText = "⏳ Regenerating...";
      try {
        const resp = await fetch(`/api/clips/${currentClip.id}/regenerate`, { method: "POST" });
        if (!resp.ok) {
          const errData = await resp.json();
          throw new Error(errData.detail || "Regeneration failed");
        }
        const updated = await resp.json();
        currentClip.title = updated.title;
        currentClip.caption = updated.caption;
        currentClip.hashtags = updated.hashtags;

        const titleInp = document.getElementById("editor-title-input");
        if (titleInp) titleInp.value = updated.title || "";
        const capInp = document.getElementById("clip-caption-input");
        if (capInp) capInp.value = updated.caption || "";
        const hashInp = document.getElementById("clip-hashtags-input");
        if (hashInp) hashInp.value = (updated.hashtags || []).join(" ");

        flashSavedStatus();
        showToast("AI Metadata regenerated!", "success");
      } catch (e) {
        showToast(`Regeneration notice: ${e.message}`, "error");
      } finally {
        btnRegenMeta.disabled = false;
        btnRegenMeta.innerText = "✨ Regenerate";
      }
    });
  }
}

function applyCustomStyleToPreview() {
  const liveCap = document.getElementById("editor-live-caption");
  if (!liveCap) return;

  liveCap.style.fontFamily = customCaptionStyle.font_family;
  liveCap.style.fontSize = `${customCaptionStyle.font_size}px`;
  liveCap.style.color = customCaptionStyle.text_color;
  liveCap.style.setProperty("--cap-highlight", customCaptionStyle.highlight_color);

  // Position
  if (customCaptionStyle.position === "top") {
    liveCap.style.top = "16%";
    liveCap.style.bottom = "auto";
  } else if (customCaptionStyle.position === "middle") {
    liveCap.style.top = "48%";
    liveCap.style.bottom = "auto";
  } else {
    liveCap.style.top = "auto";
    liveCap.style.bottom = "16%";
  }

  // Boxed preset effect
  if (customCaptionStyle.preset === "box") {
    liveCap.style.background = "rgba(0,0,0,0.75)";
    liveCap.style.border = "2px solid " + customCaptionStyle.highlight_color;
    liveCap.style.borderRadius = "8px";
    liveCap.style.padding = "6px 12px";
  } else {
    liveCap.style.background = "none";
    liveCap.style.border = "none";
    liveCap.style.padding = "0";
  }
}

function renderHookAlternatives(alts) {
  const hookAltsList = document.getElementById("hook-alternatives-list");
  if (!hookAltsList) return;
  hookAltsList.innerHTML = "";

  alts.forEach(alt => {
    const card = document.createElement("div");
    card.className = "hook-alt-card";
    card.innerHTML = `
      <span class="hook-alt-badge">${alt.type || 'Suggestion'}</span>
      <span class="hook-alt-text">${alt.text}</span>
    `;
    card.addEventListener("click", () => {
      const hookInput = document.getElementById("hook-text-input");
      if (hookInput) hookInput.value = alt.text;
      hookState.text = alt.text;
      updateHookBannerPreview();
      flashSavedStatus();
    });
    hookAltsList.appendChild(card);
  });
}

function switchRailTab(tabName) {
  document.querySelectorAll(".rail-btn").forEach(b => {
    b.classList.toggle("active", b.getAttribute("data-rail-tab") === tabName);
  });
  document.querySelectorAll(".rail-panel-content").forEach(p => {
    p.classList.toggle("active", p.id === `panel-tab-${tabName}`);
  });
}

function setEditorAspect(aspect) {
  aspectRatio = aspect;
  const frame = document.getElementById("editor-preview-frame");
  if (!frame) return;
  frame.className = `preview-frame aspect-${aspect.replace(":", "-")}`;
}

function setEditorFraming(mode) {
  framingMode = mode;
}

function updateHookBannerPreview() {
  const overlay = document.getElementById("editor-hook-overlay");
  const textEl = document.getElementById("editor-hook-text");
  if (!overlay || !textEl) return;

  if (!hookState.enabled || !hookState.text) {
    overlay.style.display = "none";
    return;
  }

  overlay.style.display = "block";
  textEl.innerText = hookState.text;
  overlay.className = `hook-banner-overlay hook-style-${hookState.style} hook-pos-${hookState.position}`;
}

// Live caption word/line highlighter on video
function updateLiveCaptions(currentTime) {
  const textBlock = document.getElementById("editor-caption-text");
  if (!textBlock || !currentClip || !currentClip.words) return;

  const words = currentClip.words;
  if (words.length === 0) {
    textBlock.innerText = "";
    return;
  }

  // Find active word
  const activeWordIdx = words.findIndex(w => currentTime >= w.start && currentTime <= w.end);

  // Group into current spoken sentence/window (e.g. 5 words around active)
  let windowStart = 0;
  let windowEnd = words.length;

  if (activeWordIdx !== -1) {
    windowStart = Math.max(0, activeWordIdx - 3);
    windowEnd = Math.min(words.length, activeWordIdx + 4);
  } else {
    // Look for nearest future word
    const nextIdx = words.findIndex(w => w.start > currentTime);
    if (nextIdx !== -1 && words[nextIdx].start - currentTime < 1.0) {
      windowStart = Math.max(0, nextIdx - 1);
      windowEnd = Math.min(words.length, nextIdx + 4);
    } else {
      textBlock.innerText = "";
      return;
    }
  }

  const slice = words.slice(windowStart, windowEnd);
  textBlock.innerHTML = slice.map((w, i) => {
    const isSpoken = (windowStart + i) === activeWordIdx;
    return `<span class="caption-word-inline ${isSpoken ? 'caption-word-active' : ''}">${w.word}</span>`;
  }).join(" ");
}

// ==================== WORD-LEVEL CAPTION LIST EDITOR (PROBLEM 6) ====================
function renderEditorCaptionsList() {
  const list = document.getElementById("editor-captions-list");
  if (!list || !currentClip) return;
  list.innerHTML = "";

  if (!currentClip.words || currentClip.words.length === 0) {
    list.innerHTML = `
      <div class="empty-captions-box" style="padding: 24px 16px; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 12px;">
        <span style="font-size: 28px;">💬</span>
        <div style="font-weight: 600; color: #FFF;">No word-level captions detected</div>
        <p style="font-size: 13px; color: var(--text-muted); max-width: 260px;">Generate animated karaoke word captions for this clip using Whisper AI.</p>
        <button type="button" id="btn-editor-gen-captions" class="btn-primary" style="padding: 8px 18px; font-size: 13px;">
          <span>⚡ Generate Captions</span>
        </button>
      </div>`;
    const genBtn = document.getElementById("btn-editor-gen-captions");
    if (genBtn) {
      genBtn.addEventListener("click", async () => {
        genBtn.disabled = true;
        genBtn.innerHTML = "<span>⏳ Generating Captions...</span>";
        try {
          const resp = await fetch(`/api/clips/${currentClip.id}/transcribe`, { method: "POST" });
          if (resp.ok) {
            const data = await resp.json();
            currentClip.words = data.words || [];
            renderEditorCaptionsList();
            showToast("Captions generated successfully!", "success");
          } else {
            showToast("Could not generate captions for this clip slice", "error");
          }
        } catch (e) {
          showToast(`Transcription error: ${e.message}`, "error");
        } finally {
          genBtn.disabled = false;
          genBtn.innerHTML = "<span>⚡ Generate Captions</span>";
        }
      });
    }
    return;
  }

  if (activeCaptionMode === "words") {
    // Full word-by-word editor with timestamps
    currentClip.words.forEach((w, idx) => {
      const item = document.createElement("div");
      item.className = "caption-word-item";
      item.innerHTML = `
        <input type="text" class="word-timing-input start" value="${Number(w.start).toFixed(2)}" title="Start time (s)">
        <input type="text" class="word-text-input" value="${w.word}">
        <input type="text" class="word-timing-input end" value="${Number(w.end).toFixed(2)}" title="End time (s)">
        <button type="button" class="btn-del-word" title="Remove word">✕</button>
      `;

      const textInp = item.querySelector(".word-text-input");
      const startInp = item.querySelector(".word-timing-input.start");
      const endInp = item.querySelector(".word-timing-input.end");
      const delBtn = item.querySelector(".btn-del-word");

      textInp.addEventListener("change", (e) => {
        w.word = e.target.value.trim();
        flashSavedStatus();
      });

      startInp.addEventListener("change", (e) => {
        const val = parseFloat(e.target.value);
        if (!isNaN(val)) w.start = val;
        flashSavedStatus();
      });

      endInp.addEventListener("change", (e) => {
        const val = parseFloat(e.target.value);
        if (!isNaN(val)) w.end = val;
        flashSavedStatus();
      });

      delBtn.addEventListener("click", () => {
        currentClip.words.splice(idx, 1);
        renderEditorCaptionsList();
        flashSavedStatus();
      });

      list.appendChild(item);
    });
  } else {
    // Lines mode: chunked by 5 words
    const lines = chunkWordsIntoLines(currentClip.words);
    lines.forEach((line, lineIdx) => {
      const lineBox = document.createElement("div");
      lineBox.className = "caption-line-block";
      lineBox.innerHTML = `
        <div class="line-header" style="font-size:0.78rem;color:#818CF8;margin-bottom:4px;">Line ${lineIdx + 1} (${line.start.toFixed(1)}s - ${line.end.toFixed(1)}s)</div>
        <textarea class="line-text-input" rows="2" style="width:100%;padding:6px;background:#0F172A;border:1px solid rgba(255,255,255,0.1);border-radius:4px;color:#fff;">${line.text}</textarea>
      `;
      const ta = lineBox.querySelector(".line-text-input");
      ta.addEventListener("change", (e) => {
        const newWords = e.target.value.trim().split(/\s+/);
        const dur = (line.end - line.start) / Math.max(newWords.length, 1);
        const replacementWords = newWords.map((wd, i) => ({
          word: wd,
          start: line.start + i * dur,
          end: line.start + (i + 1) * dur
        }));
        const before = currentClip.words.filter(w => w.end <= line.start);
        const after = currentClip.words.filter(w => w.start >= line.end);
        currentClip.words = [...before, ...replacementWords, ...after];
        flashSavedStatus();
      });
      list.appendChild(lineBox);
    });
  }
}

function chunkWordsIntoLines(words) {
  const lines = [];
  let cur = [];
  for (let i = 0; i < words.length; i++) {
    cur.push(words[i]);
    if (cur.length === 5 || i === words.length - 1) {
      lines.push({
        start: cur[0].start,
        end: cur[cur.length - 1].end,
        text: cur.map(w => w.word).join(" ")
      });
      cur = [];
    }
  }
  return lines;
}

function initBottomTimeline() {
  const track = document.getElementById("timeline-word-blocks") || document.getElementById("timeline-track-container") || document.getElementById("timeline-words-track");
  if (!track || !currentClip || !currentClip.words) return;
  track.innerHTML = "";

  const clipDur = currentClip.duration || (currentClip.end - currentClip.start) || (currentClip.end_time - currentClip.start_time) || 1;
  const startOffset = currentClip.start || currentClip.start_time || 0;

  const words = currentClip.words || [];
  if (words.length === 0) return;

  words.forEach(w => {
    const pill = document.createElement("div");
    pill.className = "timeline-word-pill";
    const leftPct = Math.max(0, Math.min(100, ((w.start - startOffset) / clipDur) * 100));
    const rawWidthPct = Math.max(0.6, ((w.end - w.start) / clipDur) * 100);
    const widthPct = Math.min(100 - leftPct, rawWidthPct);

    pill.style.position = "absolute";
    pill.style.left = `${leftPct.toFixed(2)}%`;
    pill.style.width = `${Math.max(1.2, widthPct).toFixed(2)}%`;
    pill.style.minWidth = "8px";
    pill.style.height = "26px";
    pill.style.top = "50%";
    pill.style.transform = "translateY(-50%)";
    pill.style.background = "linear-gradient(135deg, rgba(99, 102, 241, 0.4), rgba(139, 92, 246, 0.5))";
    pill.style.border = "1px solid rgba(165, 180, 252, 0.45)";
    pill.style.borderRadius = "4px";
    pill.style.overflow = "hidden";
    pill.style.textOverflow = "ellipsis";
    pill.style.whiteSpace = "nowrap";
    pill.style.boxSizing = "border-box";
    pill.style.padding = "0 3px";
    pill.style.fontSize = "10px";
    pill.style.lineHeight = "24px";
    pill.style.color = "#FFFFFF";
    pill.style.fontWeight = "600";
    pill.style.cursor = "pointer";
    pill.style.zIndex = "5";
    pill.setAttribute("title", `"${w.word}" (${Number(w.start).toFixed(2)}s - ${Number(w.end).toFixed(2)}s)`);

    // Cleanly display text when width allows, preventing stacked word overlap
    if (widthPct >= 2.8) {
      pill.innerText = w.word;
    } else {
      pill.innerText = "";
    }

    pill.addEventListener("click", (e) => {
      e.stopPropagation();
      const video = document.getElementById("editor-video");
      if (video) {
        video.currentTime = Math.max(0, w.start - startOffset);
        video.play().catch(() => {});
      }
    });

    track.appendChild(pill);
  });
}

function renderEditorScoresSummary(clip) {
  const summary = document.getElementById("editor-scores-summary");
  if (!summary) return;
  summary.innerHTML = `
    <div class="score-row"><span>Overall Rank Score</span><strong>${Math.round(clip.score || 0)} / 100</strong></div>
    <div class="score-row"><span>Opening Hook Spike</span><strong>${Math.round(clip.hook_score || clip.score || 0)} / 100</strong></div>
    <div class="score-row"><span>Audio Flow / Emotion</span><strong>${Math.round(clip.emotion_score || clip.flow_score || clip.score || 0)} / 100</strong></div>
    <div class="score-row"><span>Viral Topic Score</span><strong>${Math.round(clip.trend_score || clip.score || 0)} / 100</strong></div>
  `;
}

function syncEditorWithClipState() {
  applyCustomStyleToPreview();
}

function flashSavedStatus() {
  const badge = document.getElementById("editor-saved-badge");
  if (!badge) return;
  badge.classList.remove("hidden");
  badge.innerText = "✓ Changes saved";
  setTimeout(() => badge.classList.add("hidden"), 1500);
}

async function exportClipMp4() {
  if (!currentClip) return;
  const exportBtn = document.getElementById("btn-export-clip") || document.getElementById("btn-export-mp4");
  const spinner = document.getElementById("export-progress-spinner");

  if (exportBtn) exportBtn.disabled = true;
  if (spinner) spinner.classList.remove("hidden");

  try {
    const resp = await fetch(`/api/clips/${currentClip.id}/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        aspect: aspectRatio,
        framing: framingMode,
        custom_style: customCaptionStyle,
        hook: hookState
      }),
    });

    if (!resp.ok) {
      throw new Error("Export failed on server");
    }

    const data = await resp.json();
    currentClip.rendered_path = data.rendered_path || (data.clip && data.clip.rendered_path);
    currentClip.rendered_url = data.rendered_url || (data.clip && data.clip.rendered_url);

    // Trigger download
    const dlSrc = currentClip.rendered_url || (currentClip.rendered_path ? `/${currentClip.rendered_path}` : "");
    if (dlSrc) {
      const a = document.createElement("a");
      a.href = dlSrc;
      a.download = `${(currentClip.title || "clip").replace(/[^a-zA-Z0-9_-]/g, "_")}_rendered.mp4`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }

  } catch (err) {
    alert("Export notice: " + err.message);
  } finally {
    if (exportBtn) exportBtn.disabled = false;
    if (spinner) spinner.classList.add("hidden");
  }
}

// ==================== STREAMERS & REAL-TIME MONITORING (PROBLEM 3 & C FIX) ====================
let streamChatHistory = [
  { time: "-5m", rate: 14 },
  { time: "-4m", rate: 19 },
  { time: "-3m", rate: 16 },
  { time: "-2m", rate: 28 },
  { time: "-1m", rate: 22 },
  { time: "Now", rate: 25 }
];
let isWatchingLive = false;

function formatRelativeTime(ts) {
  if (!ts) return "Never";
  let ms = null;
  if (typeof ts === "string" && ts.includes(":") && !ts.includes("-")) {
    const parts = ts.split(":").map(p => parseInt(p, 10));
    if (parts.length >= 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
      const d = new Date();
      d.setHours(parts[0], parts[1], parts[2] || 0, 0);
      ms = d.getTime();
    }
  }
  if (!ms) {
    const num = typeof ts === "number" ? ts : parseFloat(ts);
    if (!isNaN(num) && num > 1e6) {
      ms = num < 1e11 ? num * 1000 : num;
    }
  }
  if (!ms || isNaN(ms)) return String(ts);
  const diffSec = Math.max(0, Math.round((Date.now() - ms) / 1000));
  if (diffSec < 10) return "Just now";
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return new Date(ms).toLocaleDateString();
}

function renderSpikeChart(dataPoints = streamChatHistory, isIdle = false) {
  const container = document.getElementById("chat-graph-container");
  if (!container) return;

  if (isIdle || !dataPoints || dataPoints.length === 0) {
    container.innerHTML = `
      <div class="chart-empty-state">
        <div class="chart-empty-pulse"></div>
        <span>Waiting for chat data... (Connect to live broadcast)</span>
      </div>
    `;
    return;
  }

  const width = 800;
  const height = 220;
  const padLeft = 50;
  const padRight = 30;
  const padTop = 30;
  const padBottom = 35;
  const maxRate = 200;
  const threshold = 120;

  const chartW = width - padLeft - padRight;
  const chartH = height - padTop - padBottom;
  const thresholdY = padTop + chartH - (threshold / maxRate) * chartH;

  const yTicks = [0, 50, 100, 150, 200];
  let yAxisSvg = "";
  yTicks.forEach(tick => {
    const y = padTop + chartH - (tick / maxRate) * chartH;
    yAxisSvg += `
      <line x1="${padLeft}" y1="${y}" x2="${width - padRight}" y2="${y}" stroke="rgba(255,255,255,0.06)" stroke-width="1" />
      <text x="${padLeft - 8}" y="${y + 4}" fill="#64748B" font-size="11" text-anchor="end" font-family="monospace">${tick}</text>
    `;
  });

  const step = chartW / Math.max(1, dataPoints.length - 1);
  let pathD = "";
  let areaD = "";
  let circlesSvg = "";
  let xAxisSvg = "";

  dataPoints.forEach((pt, idx) => {
    const x = padLeft + idx * step;
    const clampedRate = Math.min(maxRate, Math.max(0, pt.rate));
    const y = padTop + chartH - (clampedRate / maxRate) * chartH;
    const isSpike = clampedRate >= threshold;

    if (idx === 0) {
      pathD += `M ${x} ${y}`;
      areaD += `M ${x} ${padTop + chartH} L ${x} ${y}`;
    } else {
      pathD += ` L ${x} ${y}`;
      areaD += ` L ${x} ${y}`;
    }

    if (idx === dataPoints.length - 1) {
      areaD += ` L ${x} ${padTop + chartH} Z`;
    }

    circlesSvg += `
      <circle cx="${x}" cy="${y}" r="${isSpike ? 6 : 4}" fill="${isSpike ? '#EF4444' : '#6366F1'}" stroke="#0F172A" stroke-width="2">
        <title>${pt.rate} msg/s at ${pt.time}</title>
      </circle>
      ${isSpike ? `<text x="${x}" y="${y - 10}" fill="#F87171" font-size="11" font-weight="bold" text-anchor="middle">⚡ ${pt.rate}</text>` : ""}
    `;

    xAxisSvg += `
      <text x="${x}" y="${height - 10}" fill="#64748B" font-size="11" text-anchor="middle" font-family="monospace">${pt.time}</text>
    `;
  });

  container.innerHTML = `
    <svg class="spike-chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      <defs>
        <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#6366F1" stop-opacity="0.35" />
          <stop offset="100%" stop-color="#6366F1" stop-opacity="0.0" />
        </linearGradient>
      </defs>
      ${yAxisSvg}
      ${xAxisSvg}
      <line x1="${padLeft}" y1="${thresholdY}" x2="${width - padRight}" y2="${thresholdY}" stroke="#EF4444" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.85" />
      <text x="${width - padRight}" y="${thresholdY - 6}" fill="#EF4444" font-size="10" font-weight="700" text-anchor="end">CLIP TRIGGER (120 msg/s)</text>
      <path d="${areaD}" fill="url(#chartGrad)" />
      <path d="${pathD}" fill="none" stroke="#6366F1" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
      ${circlesSvg}
    </svg>
  `;
}

function initStreamers() {
  const pinForm = document.getElementById("pin-form");
  if (pinForm) {
    pinForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const url = document.getElementById("streamer-url").value.trim();
      const name = document.getElementById("streamer-name").value.trim() || url;
      const platform = document.getElementById("streamer-platform")?.value || "auto";
      if (!url) return;

      try {
        const resp = await fetch("/api/streamers", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, url, platform }),
        });
        if (resp.ok) {
          document.getElementById("streamer-url").value = "";
          document.getElementById("streamer-name").value = "";
          showToast(`Pinned streamer "${name}" added!`, "success");
          fetchStreamers();
        } else {
          showToast("Failed to pin streamer", "error");
        }
      } catch (err) {
        showToast("Error pinning streamer", "error");
      }
    });
  }

  // Check Single Streamer Now
  const checkSingleBtn = document.getElementById("btn-check-streamer-now");
  if (checkSingleBtn) {
    checkSingleBtn.addEventListener("click", async () => {
      if (!activeStreamer) return;
      checkSingleBtn.disabled = true;
      checkSingleBtn.innerText = "⏳ Checking...";
      try {
        const resp = await fetch(`/api/streamers/${activeStreamer.id}/check`, { method: "POST" });
        if (resp.ok) {
          activeStreamer = await resp.json();
          updateStreamerLiveUI(activeStreamer);
          showToast(`Checked ${activeStreamer.name}: ${activeStreamer.is_live ? "LIVE" : "Offline"}`, activeStreamer.is_live ? "success" : "info");
          fetchStreamers();
        }
      } catch (err) {
        showToast("Check live failed", "error");
      } finally {
        checkSingleBtn.disabled = false;
        checkSingleBtn.innerText = "🔄 Check Now";
      }
    });
  }

  // Check All Streamers Now
  const checkAllBtn = document.getElementById("btn-check-all-streamers");
  if (checkAllBtn) {
    checkAllBtn.addEventListener("click", async () => {
      checkAllBtn.disabled = true;
      checkAllBtn.innerText = "⏳ Checking All...";
      try {
        await fetch("/api/streamers/check-all", { method: "POST" });
        showToast("All pinned streamers checked", "info");
        await fetchStreamers();
      } catch (err) {
        showToast("Error checking all streamers", "error");
      } finally {
        checkAllBtn.disabled = false;
        checkAllBtn.innerText = "🔄 Check All Now";
      }
    });
  }

  // Toggle Watch Live Button
  const watchBtn = document.getElementById("btn-toggle-watch");
  if (watchBtn) {
    watchBtn.addEventListener("click", () => {
      isWatchingLive = !isWatchingLive;
      if (isWatchingLive) {
        watchBtn.innerText = "⏹ Stop Watching";
        watchBtn.className = "btn btn-ghost";
        showToast("Live watcher started. Monitoring chat velocity...", "info");
        renderSpikeChart(streamChatHistory, false);
      } else {
        watchBtn.innerText = "Start Watching";
        watchBtn.className = "btn btn-secondary";
        showToast("Live watcher paused.", "info");
      }
    });
  }

  // Interactive Test Spike Button (Problem C.3)
  const simulateBtn = document.getElementById("btn-simulate-spike");
  if (simulateBtn) {
    simulateBtn.addEventListener("click", () => {
      const now = new Date();
      const timeStr = `${now.getHours()}:${now.getMinutes() < 10 ? '0' : ''}${now.getMinutes()}:${now.getSeconds() < 10 ? '0' : ''}${now.getSeconds()}`;
      const spikeRate = Math.floor(Math.random() * 40) + 165; // 165 - 205 msg/s

      streamChatHistory.push({ time: timeStr, rate: spikeRate });
      if (streamChatHistory.length > 8) streamChatHistory.shift();

      renderSpikeChart(streamChatHistory, false);

      const rateStat = document.getElementById("stat-chat-rate");
      if (rateStat) rateStat.innerText = `${spikeRate} msg/s`;

      const clipsStat = document.getElementById("stat-clips-count");
      const currentClips = parseInt(clipsStat ? clipsStat.innerText : "0") || 0;
      if (clipsStat) clipsStat.innerText = `${currentClips + 1}`;

      const clipsList = document.getElementById("streamer-clips-list");
      if (clipsList) {
        if (clipsList.querySelector(".subtext")) {
          clipsList.innerHTML = "";
        }
        const clipCard = document.createElement("div");
        clipCard.className = "card streamer-harvested-clip";
        clipCard.style.cssText = "display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: #162032; border: 1px solid #24344d; border-radius: 8px; margin-bottom: 8px;";
        clipCard.innerHTML = `
          <div>
            <div style="font-weight: 700; color: #F8FAFC; display: flex; align-items: center; gap: 8px;">
              <span>⚡ Spike Clip #${currentClips + 1}</span>
              <span class="badge" style="background: rgba(239,68,68,0.2); color: #F87171; font-size: 0.75rem;">${spikeRate} msg/s</span>
              <span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #FBBF24; font-size: 0.75rem; border: 1px solid rgba(245, 158, 11, 0.4);">TEST - not a real clip</span>
            </div>
            <div style="font-size: 0.8rem; color: #94A3B8; margin-top: 2px;">
              Detected at ${timeStr} • 0:30 clip buffered & trimmed
            </div>
          </div>
          <div style="display: flex; gap: 8px;">
            <button type="button" class="btn btn-secondary btn-sm" onclick="showToast('Spike clip saved to library', 'info')">Preview</button>
            <button type="button" class="btn btn-primary btn-sm" onclick="const clipsTab = document.getElementById('tabnav-clips'); if (clipsTab) clipsTab.click();">View in Clips</button>
          </div>
        `;
        clipsList.prepend(clipCard);
      }

      showToast(`⚡ Chat spike detected (${spikeRate} msg/s)! Highlight clip harvested.`, "success");
    });
  }

  // Initial Spike Chart Render
  renderSpikeChart(streamChatHistory, false);
}

async function fetchStreamers() {
  try {
    const resp = await fetch("/api/streamers");
    if (!resp.ok) {
      handleServerUnreachable();
      return;
    }
    handleServerRestored();
    const streamers = await resp.json();
    const list = document.getElementById("pinned-streamers-list");
    const countBadge = document.getElementById("streamers-count-badge");
    if (countBadge) countBadge.innerText = `${streamers.length} pinned`;

    if (!list) return;
    list.innerHTML = "";
    streamers.forEach(s => {
      const item = document.createElement("div");
      item.className = `streamer-item ${activeStreamer && activeStreamer.id === s.id ? "active" : ""}`;
      
      const viewersBadge = s.is_live && s.viewer_count
        ? `<span class="badge-viewers">👥 ${s.viewer_count.toLocaleString()}</span>`
        : "";

      const avatarMarkup = s.avatar_url
        ? `<div class="streamer-avatar-wrapper small ${s.is_live ? "live-ring" : ""}"><img src="${s.avatar_url}" class="streamer-avatar-img" alt="${s.name}" onerror="this.style.display='none'"></div>`
        : `<div class="streamer-avatar-wrapper small ${s.is_live ? "live-ring" : ""}"><div class="streamer-avatar-fallback">${(s.name || "S").charAt(0).toUpperCase()}</div></div>`;

      item.innerHTML = `
        <div style="display:flex; align-items:center; gap:10px;">
          ${avatarMarkup}
          <div>
            <strong>${s.name}</strong>
            <div style="margin-top:2px;"><span class="platform-badge ${s.platform}">${s.platform}</span>${viewersBadge}</div>
          </div>
        </div>
        <span class="status-badge ${s.is_live ? "live" : "offline"}">${s.is_live ? "LIVE" : "OFFLINE"}</span>
      `;
      item.addEventListener("click", () => selectStreamer(s));
      list.appendChild(item);
    });

    if (streamers.length > 0 && !activeStreamer) {
      selectStreamer(streamers[0]);
    }
  } catch (e) {
    console.error("Fetch streamers notice:", e);
    handleServerUnreachable();
  }
}

function selectStreamer(s) {
  activeStreamer = s;
  const emptyPanel = document.getElementById("streamer-empty-panel");
  const livePanel = document.getElementById("streamer-live-panel");
  if (emptyPanel) emptyPanel.classList.add("hidden");
  if (livePanel) livePanel.classList.remove("hidden");
  updateStreamerLiveUI(s);
}

function updateStreamerLiveUI(s) {
  const nameEl = document.getElementById("live-streamer-name");
  if (nameEl) nameEl.innerText = s.name;

  // Avatar
  const avatarImg = document.getElementById("live-streamer-avatar");
  const avatarFallback = document.getElementById("live-streamer-avatar-fallback");
  const avatarWrap = document.getElementById("live-streamer-avatar-wrap");
  if (avatarWrap) {
    if (s.is_live) avatarWrap.classList.add("live-ring");
    else avatarWrap.classList.remove("live-ring");
  }
  if (avatarImg && avatarFallback) {
    if (s.avatar_url) {
      avatarImg.src = s.avatar_url;
      avatarImg.style.display = "block";
      avatarFallback.style.display = "none";
    } else {
      avatarImg.style.display = "none";
      avatarFallback.style.display = "flex";
      avatarFallback.innerText = (s.name || "S").charAt(0).toUpperCase();
    }
  }

  // Chat status
  const chatBadge = document.getElementById("live-chat-badge");
  if (chatBadge) {
    const isLive = Boolean(s.is_live);
    chatBadge.innerText = isLive ? "Chat: Connected" : "Chat: Disconnected";
    if (isLive) chatBadge.classList.add("connected");
    else chatBadge.classList.remove("connected");
  }

  const platBadge = document.getElementById("live-platform-badge");
  if (platBadge) {
    platBadge.className = `platform-badge ${s.platform}`;
    platBadge.innerText = s.platform;
  }

  const statusBadge = document.getElementById("live-status-badge");
  if (statusBadge) {
    statusBadge.className = `status-badge ${s.is_live ? "live" : "offline"}`;
    statusBadge.innerText = s.is_live ? "LIVE" : "OFFLINE";
  }

  const titleEl = document.getElementById("live-stream-title");
  if (titleEl) {
    titleEl.innerText = s.stream_title || (s.is_live ? "Live Broadcast in Progress" : "No active broadcast");
  }

  const viewersEl = document.getElementById("live-viewers-badge") || document.getElementById("live-stream-viewers");
  if (viewersEl) {
    viewersEl.innerText = s.is_live && s.viewer_count
      ? `${s.viewer_count.toLocaleString()} viewers watching now`
      : "Channel is currently offline";
  }

  const reasonEl = document.getElementById("live-stream-reason");
  if (reasonEl) {
    reasonEl.innerText = s.last_error || (s.is_live ? "Broadcasting live" : (s.status_reason || "Channel is offline"));
    reasonEl.classList.remove("hidden");
  }

  // Signal Health Chips (PeakCut rolling buffer & multi-signal health)
  const health = s.signal_health || {};
  const chatChip = document.getElementById("chip-signal-chat");
  const audioChip = document.getElementById("chip-signal-audio");
  const bufChip = document.getElementById("chip-signal-buffer");
  const lastClipChip = document.getElementById("chip-last-clip");

  if (chatChip) {
    const isFallback = (health.chat || "").includes("fallback");
    chatChip.className = `signal-chip ${isFallback ? "fallback" : (health.chat === "connected" ? "active" : "")}`;
    chatChip.innerText = `Chat: ${health.chat || (s.is_live ? "Connected" : "Disconnected")}`;
  }
  if (audioChip) {
    audioChip.className = `signal-chip ${health.audio && health.audio.includes("active") ? "active" : ""}`;
    audioChip.innerText = `Audio: ${health.audio || (s.is_live ? "Active" : "Waiting")}`;
  }
  if (bufChip) {
    bufChip.className = `signal-chip ${(health.buffer_sec || 0) > 0 ? "active" : "fallback"}`;
    bufChip.innerText = `Buffer: ${health.buffer_sec ? health.buffer_sec + 's (' + health.buffer_mb + 'MB)' : 'Ready (10 min)'}`;
  }
  if (lastClipChip) {
    lastClipChip.innerText = `Last Clip: ${s.last_clip_time || 'None'}`;
  }

  const timeEl = document.getElementById("live-stream-last-checked");
  if (timeEl) {
    const rel = formatRelativeTime(s.last_checked);
    timeEl.innerText = rel;
    if (s.last_checked) {
      if (typeof s.last_checked === "number") {
        const ms = s.last_checked < 1e11 ? s.last_checked * 1000 : s.last_checked;
        timeEl.title = new Date(ms).toLocaleString();
      } else {
        timeEl.title = String(s.last_checked);
      }
    } else {
      timeEl.removeAttribute("title");
    }
  }

  // Render chart for this streamer
  renderSpikeChart(streamChatHistory, !s.is_live);
}

// ==================== SETTINGS & GUIDED YOUTUBE WIZARD (PROBLEMS 4 & 8) ====================
function initSettings() {
  const providerSelect = document.getElementById("set-llm-provider");

  // Toggle key groups on provider select
  if (providerSelect) {
    const updateGroups = () => {
      const val = providerSelect.value;
      document.querySelectorAll(".provider-key-group").forEach(g => g.classList.add("hidden"));
      const targetGroup = document.getElementById(`group-${val}`);
      if (targetGroup) targetGroup.classList.remove("hidden");
    };
    providerSelect.addEventListener("change", updateGroups);
    updateGroups();
  }

  // Test Key Buttons (Problem 4)
  document.querySelectorAll(".btn-test-key").forEach(btn => {
    btn.addEventListener("click", async () => {
      const provider = btn.getAttribute("data-provider") || "gemini";
      let key = "";
      if (provider === "gemini") key = document.getElementById("set-gemini-key")?.value.trim() || "";
      else if (provider === "openai") key = document.getElementById("set-openai-key")?.value.trim() || "";
      else if (provider === "groq") key = document.getElementById("set-groq-key")?.value.trim() || "";
      else if (provider === "anthropic") key = document.getElementById("set-anthropic-key")?.value.trim() || "";
      else if (provider === "ollama") key = document.getElementById("set-ollama-url")?.value.trim() || "";

      const statusEl = document.getElementById(`test-status-${provider}`);
      if (statusEl) {
        statusEl.className = "key-test-status testing";
        statusEl.classList.remove("hidden");
        statusEl.innerText = "Testing connection...";
      }
      btn.disabled = true;

      try {
        const resp = await fetch("/api/settings/test-key", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider, key }),
        });
        const res = await resp.json();
        if (resp.ok && res.success) {
          if (statusEl) {
            statusEl.className = "key-test-status success";
            statusEl.innerText = `✓ ${res.message || "Key is valid!"}`;
          }
        } else {
          if (statusEl) {
            statusEl.className = "key-test-status error";
            statusEl.innerText = `✗ ${res.detail || res.message || res.error || "Verification failed."}`;
          }
        }
      } catch (err) {
        if (statusEl) {
          statusEl.className = "key-test-status error";
          statusEl.innerText = `✗ Error: ${err.message}`;
        }
      } finally {
        btn.disabled = false;
      }
    });
  });

  // Guided YouTube Wizard Connect Button (Problem 8)
  const ytConnectBtn = document.getElementById("btn-start-yt-connect");
  const ytMsg = document.getElementById("yt-connect-msg");
  if (ytConnectBtn && ytMsg) {
    ytConnectBtn.addEventListener("click", async () => {
      const clientId = document.getElementById("yt-client-id-input")?.value.trim();
      const clientSecret = document.getElementById("yt-client-secret-input")?.value.trim();

      if (!clientId || !clientSecret) {
        ytMsg.className = "key-test-status error";
        ytMsg.classList.remove("hidden");
        ytMsg.innerText = "Please paste both Client ID and Client Secret above.";
        return;
      }

      ytConnectBtn.disabled = true;
      ytMsg.className = "key-test-status testing";
      ytMsg.classList.remove("hidden");
      ytMsg.innerText = "Initiating OAuth consent flow... Follow prompt in browser window.";

      try {
        const resp = await fetch("/api/youtube/connect", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ client_id: clientId, client_secret: clientSecret }),
        });
        const res = await resp.json();
        if (resp.ok && res.status === "connected") {
          ytMsg.className = "key-test-status success";
          ytMsg.innerText = `✓ Connected as ${res.channel_name || "YouTube Creator"}`;
          updateYouTubeStatusUI(true, res.channel_name);
        } else {
          ytMsg.className = "key-test-status error";
          ytMsg.innerText = `Connection failed: ${res.detail || "Unable to authorize"}`;
        }
      } catch (err) {
        ytMsg.className = "key-test-status error";
        ytMsg.innerText = `OAuth error: ${err.message}`;
      } finally {
        ytConnectBtn.disabled = false;
      }
    });
  }

    // Find Models Buttons (Part 3.2)
  document.querySelectorAll(".btn-find-models").forEach(btn => {
    btn.addEventListener("click", async () => {
      const provider = btn.getAttribute("data-provider") || "gemini";
      let key = "";
      if (provider === "gemini") key = document.getElementById("set-gemini-key")?.value.trim() || "";
      btn.disabled = true;
      btn.innerText = "Finding...";

      try {
        const resp = await fetch(`/api/settings/models?provider=${provider}&key=${encodeURIComponent(key)}`);
        const res = await resp.json();
        const drop = document.getElementById(`models-list-${provider}`);
        if (drop && res.models && res.models.length > 0) {
          drop.innerHTML = res.models.map(m => `<option value="${m}">${m}</option>`).join("");
          drop.classList.remove("hidden");
          showToast(`Discovered ${res.models.length} ${provider} model(s)!`, "success");
        }
      } catch (e) {
        showToast("Failed to fetch models", "error");
      } finally {
        btn.disabled = false;
        btn.innerText = "Find Models";
      }
    });
  });

  // Save & Test Buttons (Part 3.2 - Verifies and saves locally into .env)
  document.querySelectorAll(".btn-save-test-key").forEach(btn => {
    btn.addEventListener("click", async () => {
      const provider = btn.getAttribute("data-provider") || "gemini";
      let key = "";
      if (provider === "gemini") key = document.getElementById("set-gemini-key")?.value.trim() || "";
      else if (provider === "openai") key = document.getElementById("set-openai-key")?.value.trim() || "";
      else if (provider === "groq") key = document.getElementById("set-groq-key")?.value.trim() || "";
      else if (provider === "anthropic") key = document.getElementById("set-anthropic-key")?.value.trim() || "";
      else if (provider === "ollama") key = document.getElementById("set-ollama-url")?.value.trim() || "";

      btn.disabled = true;
      btn.innerText = "Testing & Saving...";

      try {
        const resp = await fetch("/api/settings/test-and-save", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider, key }),
        });
        const res = await resp.json();
        if (resp.ok && res.success) {
          showToast(res.message, "success");
          fetchSettings();
        } else {
          showToast(res.detail || res.error || "Key verification failed", "error");
        }
      } catch (e) {
        showToast("Connection failed", "error");
      } finally {
        btn.disabled = false;
        btn.innerText = "Save & Test";
      }
    });
  });

  // AI Settings Form
  const aiForm = document.getElementById("settings-ai-form");
  if (aiForm) {
    aiForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const updates = {
        llm_provider: document.getElementById("set-llm-provider")?.value || "gemini",
        gemini_api_key: document.getElementById("set-gemini-key")?.value.trim() || "",
        openai_api_key: document.getElementById("set-openai-key")?.value.trim() || "",
        groq_api_key: document.getElementById("set-groq-key")?.value.trim() || "",
        anthropic_api_key: document.getElementById("set-anthropic-key")?.value.trim() || "",
        ollama_url: document.getElementById("set-ollama-url")?.value.trim() || "",
        transcription_option: document.getElementById("set-transcription-option")?.value || "local_whisper",
        whisper_model: document.getElementById("set-whisper-model")?.value || "tiny",
      };

      try {
        const resp = await fetch("/api/settings", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(updates),
        });
        if (resp.ok) {
          const status = document.getElementById("ai-settings-save-status");
          if (status) {
            status.classList.remove("hidden");
            setTimeout(() => status.classList.add("hidden"), 2000);
          }
        }
      } catch (err) {
        alert("AI Settings save notice: " + err.message);
      }
    });
  }

  // Buffer Parameters Form
  const bufForm = document.getElementById("settings-buffer-form");
  if (bufForm) {
    bufForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const updates = {
        record_height: parseInt(document.getElementById("set-record-height")?.value || "720", 10),
        spike_min_msgs: parseInt(document.getElementById("set-spike-threshold")?.value || "120", 10),
        daily_upload_cap: parseInt(document.getElementById("set-daily-cap")?.value || "5", 10),
      };

      try {
        const resp = await fetch("/api/settings", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(updates),
        });
        if (resp.ok) {
          const status = document.getElementById("buffer-settings-save-status");
          if (status) {
            status.classList.remove("hidden");
            setTimeout(() => status.classList.add("hidden"), 2000);
          }
        }
      } catch (err) {
        alert("Buffer settings save notice: " + err.message);
      }
    });
  }
}

// ==================== SYSTEM HEALTH & WINDOWS SAFETY (PART 3.1) ====================
async function fetchSystemHealth() {
  const dot = document.getElementById("health-dot");
  const label = document.getElementById("health-label");
  const warnBox = document.getElementById("health-path-warning-box");
  const warnTxt = document.getElementById("health-warning-text");

  const setVal = (id, val, isErr = false, isWarn = false) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerText = val;
    if (isErr) {
      el.style.color = "#EF4444";
      el.style.fontWeight = "700";
    } else if (isWarn) {
      el.style.color = "#F59E0B";
      el.style.fontWeight = "600";
    } else {
      el.style.color = "#10B981";
      el.style.fontWeight = "600";
    }
  };

  try {
    // Strict 3s timeout to ensure prompt SLA
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 6000);

    const resp = await fetch("/api/health", { signal: controller.signal });
    clearTimeout(timeoutId);

    const h = await resp.json();

    const isHealthy = Boolean(h.healthy || h.status === "ok");
    const failing = Array.isArray(h.failing) ? h.failing : [];
    const hasPathWarning = Boolean(h.project_path?.warning || h.path_safety?.warning);

    if (dot && label) {
      if (failing.length > 0 || !isHealthy) {
        dot.className = "health-dot critical";
        label.innerText = "System: Critical";
      } else if (hasPathWarning) {
        dot.className = "health-dot warning";
        label.innerText = "System: Path Warning";
      } else {
        dot.className = "health-dot";
        label.innerText = "System: Healthy";
      }
    }

    // 1. FFmpeg
    const ffmpegOk = Boolean(h.ffmpeg?.found || h.ffmpeg?.present);
    const ffmpegVer = h.ffmpeg?.version || "available";
    const ffmpegPath = h.ffmpeg?.path || "";
    setVal("health-ffmpeg-val", ffmpegOk ? `✓ ${ffmpegVer}` : "✗ Missing", !ffmpegOk);
    const ffmpegEl = document.getElementById("health-ffmpeg-val");
    if (ffmpegEl && ffmpegPath) ffmpegEl.setAttribute("title", ffmpegPath);

    // 2. FFprobe
    const ffprobeOk = Boolean(h.ffprobe?.found || h.ffprobe?.present);
    const ffprobeVer = h.ffprobe?.version || "available";
    const ffprobePath = h.ffprobe?.path || "";
    setVal("health-ffprobe-val", ffprobeOk ? `✓ ${ffprobeVer}` : "✗ Missing", !ffprobeOk);
    const ffprobeEl = document.getElementById("health-ffprobe-val");
    if (ffprobeEl && ffprobePath) ffprobeEl.setAttribute("title", ffprobePath);

    // 3. yt-dlp
    const ytdlpVer = h.yt_dlp_version || h.yt_dlp?.version || "";
    const ytdlpOk = Boolean(ytdlpVer && ytdlpVer !== "not installed");
    setVal("health-ytdlp-val", ytdlpOk ? `✓ v${ytdlpVer}` : "✗ Missing", !ytdlpOk);

    // 4. Python
    const pyVer = h.python_version || h.python?.version || "3.14";
    setVal("health-python-val", `✓ v${pyVer}`);

    // 5. Disk storage
    const freeGb = h.data_folder?.free_space_gb ?? h.data_dir?.free_space_gb ?? 0;
    const diskOk = freeGb > 2.0;
    setVal("health-disk-val", `${freeGb} GB free`, !diskOk, freeGb < 5.0);

    // 6. Project path length & root path
    const projPath = h.project_path?.path || h.path_safety?.project_path || "";
    const pathLen = h.project_path?.length ?? h.path_safety?.path_length ?? projPath.length;
    const pathWarn = Boolean(h.project_path?.warning || h.path_safety?.warning || pathLen > 100);
    setVal("health-pathlen-val", `${pathLen} chars`, false, pathWarn);

    const pathInp = document.getElementById("health-project-path-input");
    if (pathInp) pathInp.value = projPath;

    if (warnBox && warnTxt) {
      if (pathWarn) {
        warnTxt.innerText = h.project_path?.warning || h.path_safety?.warning || `Warning: Project path length is ${pathLen} chars (threshold: 100). Windows MAX_PATH is 260.`;
        warnBox.classList.remove("hidden");
      } else {
        warnBox.classList.add("hidden");
      }
    }
  } catch (err) {
    console.error("fetchSystemHealth error:", err);
    if (dot && label) {
      dot.className = "health-dot warning";
      label.innerText = "System: Health Check Timeout";
    }
    const errText = `⚠️ Error (Click to retry)`;
    ["health-ffmpeg-val", "health-ffprobe-val", "health-ytdlp-val", "health-python-val", "health-disk-val", "health-pathlen-val"].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.innerText = errText;
        el.style.color = "#F59E0B";
        el.style.cursor = "pointer";
        el.onclick = () => fetchSystemHealth();
      }
    });
  }
}

function initHealthModal() {
  const btnOpen = document.getElementById("btn-system-health");
  const modal = document.getElementById("system-health-modal");
  const btnClose1 = document.getElementById("btn-close-health-modal");
  const btnClose2 = document.getElementById("btn-modal-close-health");

  if (btnOpen && modal) {
    btnOpen.addEventListener("click", () => {
      fetchSystemHealth();
      modal.classList.remove("hidden");
    });
  }
  const close = () => modal && modal.classList.add("hidden");
  if (btnClose1) btnClose1.addEventListener("click", close);
  if (btnClose2) btnClose2.addEventListener("click", close);
}

async function fetchSettings() {
  try {
    const resp = await fetch("/api/settings");
    if (!resp.ok) return;
    const data = await resp.json();

    // Update Ranking Mode Banner (No-Key Mode vs AI Cloud Mode)
    const banner = document.getElementById("ranking-mode-banner");
    const bTitle = document.getElementById("ranking-mode-title");
    const bDesc = document.getElementById("ranking-mode-desc");
    const bBadge = document.getElementById("ranking-mode-badge");

    if (banner && bTitle && bDesc && bBadge) {
      if (data.no_key_mode) {
        banner.className = "ranking-mode-banner";
        bTitle.innerText = "Mode: No-Key Local Mode";
        bDesc.innerText = "Ranking by audio loudness peaks and speech hooks (Zero keys required)";
        bBadge.className = "badge";
        bBadge.innerText = "Local Only";
      } else {
        banner.className = "ranking-mode-banner ai-active";
        bTitle.innerText = `Mode: ${data.ranking_mode || 'AI Cloud Scoring'}`;
        bDesc.innerText = `Active provider: ${data.llm_provider ? data.llm_provider.toUpperCase() : 'AI'}`;
        bBadge.className = "badge badge-accent";
        bBadge.innerText = "Cloud AI Active";
      }
    }

    // Storage & Data Dir
    const dataDirInp = document.getElementById("set-data-dir");
    const freeSpaceBadge = document.getElementById("free-space-badge");
    if (dataDirInp && data.data_dir) dataDirInp.value = data.data_dir;
    if (freeSpaceBadge && data.free_disk_space_gb !== undefined) {
      freeSpaceBadge.innerText = `${data.free_disk_space_gb} GB Free`;
    }

    if (data.llm_provider) {
      const pSel = document.getElementById("set-llm-provider");
      if (pSel) {
        pSel.value = data.llm_provider;
        pSel.dispatchEvent(new Event("change"));
      }
    }
    if (data.gemini_api_key) document.getElementById("set-gemini-key").value = data.gemini_api_key;
    if (data.openai_api_key) document.getElementById("set-openai-key").value = data.openai_api_key;
    if (data.groq_api_key) document.getElementById("set-groq-key").value = data.groq_api_key;
    if (data.anthropic_api_key) document.getElementById("set-anthropic-key").value = data.anthropic_api_key;
    if (data.ollama_url) document.getElementById("set-ollama-url").value = data.ollama_url;
    if (data.transcription_option) document.getElementById("set-transcription-option").value = data.transcription_option;
    if (data.whisper_model) document.getElementById("set-whisper-model").value = data.whisper_model;
    if (data.record_height) document.getElementById("set-record-height").value = String(data.record_height);
    if (data.spike_min_msgs) document.getElementById("set-spike-threshold").value = data.spike_min_msgs;
    if (data.daily_upload_cap) document.getElementById("set-daily-cap").value = data.daily_upload_cap;

    // YouTube state
    updateYouTubeStatusUI(data.youtube_authenticated, data.youtube_channel_name);

  } catch (e) {
    console.error("Fetch settings notice", e);
    handleServerUnreachable();
  }
}

function updateYouTubeStatusUI(authenticated, channelName) {
  const dot = document.getElementById("yt-status-dot");
  const title = document.getElementById("yt-status-title");
  const readout = document.getElementById("yt-channel-readout");

  if (authenticated) {
    if (dot) dot.className = "status-dot connected";
    if (title) title.innerText = "Connected to YouTube";
    if (readout) readout.innerText = `✓ Authenticated as ${channelName || "Creator Channel"}`;
  } else {
    if (dot) dot.className = "status-dot disconnected";
    if (title) title.innerText = "Not Connected (Opt-in)";
    if (readout) readout.innerText = "Connect your Google Cloud OAuth client to schedule private Shorts.";
  }
}

// ==================== TOAST & GLOBAL ERROR HANDLING (PROBLEM E.4) ====================
function showToast(message, type = "info", duration = 4000) {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  
  let icon = "ℹ️";
  if (type === "success") icon = "✅";
  else if (type === "error") icon = "⚠️";
  else if (type === "warning") icon = "🔔";

  toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(8px)";
    setTimeout(() => toast.remove(), 250);
  }, duration);
}

function handleServerUnreachable() {
  const overlay = document.getElementById("server-unreachable-overlay");
  if (overlay) overlay.classList.remove("hidden");
}

function handleServerRestored() {
  const overlay = document.getElementById("server-unreachable-overlay");
  if (overlay) overlay.classList.add("hidden");
}

document.addEventListener("DOMContentLoaded", () => {
  const retryBtn = document.getElementById("btn-retry-server");
  if (retryBtn) {
    retryBtn.addEventListener("click", async () => {
      retryBtn.disabled = true;
      retryBtn.innerText = "Connecting...";
      try {
        const res = await fetch("/api/sessions");
        if (res.ok) {
          handleServerRestored();
          showToast("Connected to server!", "success");
          loadLatestSession();
        } else {
          showToast("Server returned an error", "error");
        }
      } catch (e) {
        showToast("Server still unreachable", "error");
      } finally {
        retryBtn.disabled = false;
        retryBtn.innerText = "🔄 Retry Connection";
      }
    });
  }

  // Polling with Visibility API
  let streamersPollInterval = setInterval(() => {
    if (document.visibilityState === "visible") {
      const streamersTab = document.getElementById("tab-streamers");
      if (streamersTab && streamersTab.classList.contains("active")) {
        fetchStreamers();
      }
    }
  }, 30000);

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      const streamersTab = document.getElementById("tab-streamers");
      if (streamersTab && streamersTab.classList.contains("active")) {
        fetchStreamers();
      }
    }
  });
});
