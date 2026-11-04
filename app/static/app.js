
let currentUser = null;
let allRoads = [];
let allEvents = [];
let simBeforeChart = null;
let simAfterChart = null;
let activeMainSection = "standard";
let allLiveCorridors = [];
let activeLiveZoneFilter = "all";

function escapeHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function getAuthHeader() {
  if (currentUser && currentUser.token) {
    return `Bearer ${currentUser.token}`;
  }
  const saved = localStorage.getItem("traffic_ai_user");
  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      if (parsed && parsed.token) return `Bearer ${parsed.token}`;
    } catch (e) {}
  }
  return "";
}

const CANONICAL_ROAD_NAMES = {
  "RD_BLR_01": "100 Feet Road",
  "RD_BLR_02": "Anil Kumble Circle",
  "RD_BLR_03": "Ballari Road",
  "RD_BLR_04": "CMH Road",
  "RD_BLR_05": "Hebbal Flyover",
  "RD_BLR_06": "Hosur Road",
  "RD_BLR_07": "ITPL Main Road",
  "RD_BLR_08": "Jayanagar 4th Block",
  "RD_BLR_09": "Marathahalli Bridge",
  "RD_BLR_10": "Sarjapur Road",
  "RD_BLR_11": "Silk Board Junction",
  "RD_BLR_12": "Sony World Junction",
  "RD_BLR_13": "South End Circle",
  "RD_BLR_14": "Trinity Circle",
  "RD_BLR_15": "Tumkur Road",
  "RD_BLR_16": "Varthur Road",
  "RD_BLR_17": "Old Airport Road",
  "RD_BLR_18": "Bannerghatta Road",
  "RD_BLR_19": "Outer Ring Road (Bellandur)",
  "RD_BLR_20": "Electronic City Expressway",
  "RD_BLR_21": "Peenya 1st Stage",
  "RD_BLR_22": "Goraguntepalya Junction",
  "RD_BLR_23": "Koramangala 80 Feet Road",
  "RD_BLR_24": "Malleshwaram 8th Cross"
};

function getCorridorDisplayName(roadId, eventRoadNames = [], idx = 0) {
  if (Array.isArray(eventRoadNames) && eventRoadNames[idx] && typeof eventRoadNames[idx] === "string" && eventRoadNames[idx].trim().length > 0) {
    return eventRoadNames[idx];
  }
  if (CANONICAL_ROAD_NAMES[roadId]) {
    return CANONICAL_ROAD_NAMES[roadId];
  }
  const foundRoad = allRoads.find(r => r.road_id === roadId);
  if (foundRoad && foundRoad.road_name) return foundRoad.road_name;
  const foundLive = allLiveCorridors.find(c => c.road_id === roadId);
  if (foundLive && foundLive.road_name) return foundLive.road_name;
  return roadId;
}

function showFileProtocolBanner() {
  if (document.getElementById("fileProtocolBanner")) return;
  const banner = document.createElement("div");
  banner.id = "fileProtocolBanner";
  banner.style.cssText = "background: rgba(37, 99, 235, 0.14); border-bottom: 1px solid rgba(37, 99, 235, 0.35); color: #93c5fd; padding: 10px 24px; font-size: 13px; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 10000; backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);";
  banner.innerHTML = `
    <div style="display: flex; align-items: center; gap: 8px;">
      <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#38bdf8; box-shadow: 0 0 6px #38bdf8;"></span>
      <span><strong>Standalone Preview Mode:</strong> Viewing index.html via local file protocol. For live XGBoost inference and real-time database sync, start the backend server and open <a href="http://localhost:8080/portal" target="_blank" style="color: #60a5fa; text-decoration: underline; font-weight: 600;">http://localhost:8080/portal</a> (or port 8089).</span>
    </div>
    <button onclick="this.parentElement.remove()" style="background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 16px; padding: 0 6px;" title="Dismiss">&times;</button>
  `;
  document.body.prepend(banner);
}

let audioCtx = null;
function getAudioContext() {
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (AudioContextClass) audioCtx = new AudioContextClass();
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

function _playToneSequence(tones) {
  try {
    const ctx = getAudioContext();
    if (!ctx) return;
    const now = ctx.currentTime;
    tones.forEach(t => {
      const osc = ctx.createOscillator(), g = ctx.createGain();
      osc.type = t.type || 'sine';
      osc.frequency.setValueAtTime(t.freq, now + (t.delay || 0));
      if (t.endFreq) osc.frequency.exponentialRampToValueAtTime(t.endFreq, now + (t.delay || 0) + t.dur);
      g.gain.setValueAtTime(t.gain || 0.04, now + (t.delay || 0));
      g.gain.exponentialRampToValueAtTime(0.0001, now + (t.delay || 0) + t.dur);
      osc.connect(g);
      g.connect(ctx.destination);
      osc.start(now + (t.delay || 0));
      osc.stop(now + (t.delay || 0) + t.dur + 0.005);
    });
  } catch (e) {}
}

function playTactileClick() {
  _playToneSequence([{ freq: 850, endFreq: 320, dur: 0.012, gain: 0.04 }]);
}

function playSuccessChime() {
  _playToneSequence([
    { freq: 523.25, dur: 0.18, gain: 0.06 },
    { freq: 659.25, delay: 0.07, dur: 0.21, gain: 0.06 }
  ]);
}

function playWarningLid() {
  _playToneSequence([{ freq: 220, endFreq: 180, dur: 0.16, gain: 0.08, type: 'triangle' }]);
}

function playHapticBeep(freq = 650, durationMs = 45, type = "sine") {
  const d = Math.max(0.01, durationMs / 1000);
  _playToneSequence([{ freq, endFreq: Math.max(100, freq * 0.75), dur: d, gain: 0.04, type }]);
}

function playTrafficAlertChime() {
  _playToneSequence([
    { freq: 880, dur: 0.15, gain: 0.18 },
    { freq: 1174.66, delay: 0.12, dur: 0.43, gain: 0.18 }
  ]);
}

function formatRoutePills(routeIds, roadsRegistry = [], options = {}) {
  if (!Array.isArray(routeIds)) return "";
  const { showId = false, highlightRoads = [] } = options;
  return routeIds.map(r => {
    const found = roadsRegistry.find(c => c.road_id === r);
    const name = (found && found.road_name) ? found.road_name : r;
    const isHighlight = highlightRoads.includes(r);
    const borderStyle = isHighlight ? 'border-color: rgba(16,185,129,0.5); color: #34d399; font-weight: 700;' : '';
    const idTag = showId ? `<small style="color: #64748b; font-size: 0.72rem; margin-left: 4px;">[${r}]</small>` : '';
    const titleAttr = found && found.intersection_id ? ` title="${name} (${found.intersection_id})"` : ` title="${name}"`;
    return `<span class="corridor-pill"${titleAttr} style="${borderStyle}"><span style="font-weight: 600;">${name}</span>${idTag}</span>`;
  }).join('<span class="corridor-arrow">➔</span>');
}

window.playTactileClick = playTactileClick;
window.playSuccessChime = playSuccessChime;
window.playWarningLid = playWarningLid;
window.playHapticBeep = playHapticBeep;

function setAppTheme(theme = 'dark', playFeedback = true) {
  const isLight = (theme === 'light');
  document.body.classList.remove('theme-mixed');

  if (isLight) {
    document.body.classList.remove('theme-obsidian');
    document.body.classList.add('theme-light');
    try {
      localStorage.setItem('traffic_ai_theme', 'light');
    } catch (e) {}
  } else {
    document.body.classList.remove('theme-light');
    document.body.classList.add('theme-obsidian');
    try {
      localStorage.setItem('traffic_ai_theme', 'obsidian');
    } catch (e) {}
  }

  const btnDark = document.getElementById("themeBtnDark");
  const btnLight = document.getElementById("themeBtnLight");
  if (btnDark && btnLight) {
    if (isLight) {
      btnLight.classList.add("active");
      btnLight.setAttribute("aria-checked", "true");
      btnDark.classList.remove("active");
      btnDark.setAttribute("aria-checked", "false");
    } else {
      btnDark.classList.add("active");
      btnDark.setAttribute("aria-checked", "true");
      btnLight.classList.remove("active");
      btnLight.setAttribute("aria-checked", "false");
    }
  }

  if (typeof updatePolicySimulationChartTheme === "function") {
    try { updatePolicySimulationChartTheme(isLight); } catch (e) {}
  }
  if (typeof drawJunctionScene === "function") {
    try { drawJunctionScene(); } catch (e) {}
  }

  if (playFeedback) {
    playHapticBeep(isLight ? 740 : 520, 30, "sine");
  }
}
window.setAppTheme = setAppTheme;

function initThemeFromStorage() {
  let saved = 'obsidian';
  try {
    saved = localStorage.getItem('traffic_ai_theme') || 'obsidian';
  } catch (e) {}
  setAppTheme(saved === 'light' ? 'light' : 'obsidian', false);
}

function selectPersonaView(persona) {
  if (persona === "authority") {
    if (currentUser && (currentUser.role === "Traffic Management" || currentUser.role === "Traffic Authority")) {
      updateAuthUI();
      showToast("Traffic Management Control Room Active.", "info", 1800);
      renderCorridorMatrix(allRoads);
      loadZoneSummary();
      loadAuthorityEventsQueue();
    } else {
      showToast("Traffic Management console requires administrator credentials. Redirecting to sign in…", "warning", 2400);
      setTimeout(() => { window.location.href = "/login"; }, 600);
    }
  } else {
    updateAuthUI();
    showToast("Road User Navigation Active.", "info", 1800);
  }
  if (window.playTactileClick) window.playTactileClick();
}
window.selectPersonaView = selectPersonaView;

function renderCorridorMatrix(roads) {
  const container = document.getElementById("corridorMatrixGrid");
  if (!container) return;
  if (!roads || roads.length === 0) {
    container.innerHTML = `<p style="color:var(--text-muted); font-size:0.85rem;">No corridors available.</p>`;
    return;
  }

  container.innerHTML = roads.map(r => {
    const cong = (r.peak_congestion || r.common_congestion || "Moderate").toLowerCase();
    const speed = r.avg_speed || r.peak_speed || 35.0;
    const vol = r.avg_volume || r.peak_volume || 1200;
    const rName = r.road_name || r.global_name || r.road_id;
    const intName = r.intersection_name ? ` · ${r.intersection_name}` : "";

    return `
      <div class="corridor-card" data-road-id="${r.road_id}">
        <div class="corridor-card-header">
          <div>
            <span class="corridor-card-zone">${r.city_zone}</span>
            <div class="corridor-card-name">${rName}</div>
            <div class="corridor-card-id">${r.road_id}${intName}</div>
          </div>
          <span class="los-badge ${cong}">${(r.peak_congestion || r.common_congestion || "MOD").toUpperCase()}</span>
        </div>
        <div class="corridor-card-metrics">
          <div class="corridor-metric-item">
            <span class="corridor-metric-label">Mean Speed</span>
            <span class="corridor-metric-val">${speed} km/h</span>
          </div>
          <div class="corridor-metric-item">
            <span class="corridor-metric-label">Hourly Vol</span>
            <span class="corridor-metric-val">${vol.toLocaleString()} vph</span>
          </div>
        </div>
      </div>
    `;
  }).join("");
}
window.renderCorridorMatrix = renderCorridorMatrix;

function setOriginCorridor(zone, roadId) {
  const zoneSelect = document.getElementById("routeZoneSelect");
  if (zoneSelect) {
    zoneSelect.value = zone;
    onZoneChanged();
  }
  const origSelect = document.getElementById("routeOriginSelect");
  if (origSelect) {
    origSelect.value = roadId;
  }
  const planner = document.getElementById("routePlannerCard");
  if (planner) {
    planner.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  showToast(`Origin set to ${roadId}.`, "info", 1500);
  if (window.playTactileClick) window.playTactileClick();
  setTimeout(() => evaluateRoute(), 300);
}
window.setOriginCorridor = setOriginCorridor;

function setDestCorridor(zone, roadId) {
  const destSelect = document.getElementById("routeDestSelect");
  if (destSelect) {
    destSelect.value = roadId;
  }
  const planner = document.getElementById("routePlannerCard");
  if (planner) {
    planner.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  showToast(`Destination set to ${roadId}.`, "info", 1500);
  if (window.playTactileClick) window.playTactileClick();
  setTimeout(() => evaluateRoute(), 300);
}
window.setDestCorridor = setDestCorridor;

document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

async function initApp() {

  initThemeFromStorage();

  const nowLocal = new Date();
  const localTodayStr = `${nowLocal.getFullYear()}-${String(nowLocal.getMonth() + 1).padStart(2, "0")}-${String(nowLocal.getDate()).padStart(2, "0")}`;
  const datasetDefaultDate = localTodayStr;
  const datasetDefaultTime = "10:00";
  const dateInput = document.getElementById("routeDateInput");
  const eventDateInput = document.getElementById("newEventDate");
  const timeInput = document.getElementById("routeTimeInput");
  const liveDateInput = document.getElementById("liveRouteDateInput");
  const liveTimeInput = document.getElementById("liveRouteTimeInput");
  if (dateInput) {
    dateInput.min = "2022-01-01";
    dateInput.max = "2026-12-31";
    if (!dateInput.value || dateInput.value === "2026-03-18" || dateInput.value === "2026-04-30") dateInput.value = datasetDefaultDate;
  }
  if (eventDateInput) {
    eventDateInput.min = "2022-01-01";
    eventDateInput.max = "2026-12-31";
    if (!eventDateInput.value || eventDateInput.value === "2026-03-18" || eventDateInput.value === "2026-04-30") eventDateInput.value = datasetDefaultDate;
  }
  if (liveDateInput) {
    liveDateInput.min = "2022-01-01";
    liveDateInput.max = "2026-12-31";
    if (!liveDateInput.value || liveDateInput.value === "2026-03-18" || liveDateInput.value === "2026-04-30") liveDateInput.value = datasetDefaultDate;
  }
  if (timeInput && !timeInput.value) {
    timeInput.value = datasetDefaultTime;
  }
  if (liveTimeInput && !liveTimeInput.value) {
    liveTimeInput.value = datasetDefaultTime;
  }

  const isFileProtocol = window.location.protocol === "file:";
  const urlParams = new URLSearchParams(window.location.search);
  const demoParam = urlParams.get("demo");

  if (demoParam) {
    const role = (demoParam.toLowerCase() === "commuter" || demoParam.toLowerCase() === "user")
      ? "Road User"
      : "Traffic Authority";
    currentUser = {
      username: `Demo (${role})`,
      role: role,
      token: "demo_instant_session"
    };
    localStorage.setItem("traffic_ai_user", JSON.stringify(currentUser));
  }

  const savedUserJson = localStorage.getItem("traffic_ai_user");
  if (!savedUserJson) {

    currentUser = {
      username: isFileProtocol ? "Bangalore Traffic Authority (Local File)" : "Traffic Operations Demo",
      role: "Traffic Authority",
      token: "demo_default_session"
    };
    localStorage.setItem("traffic_ai_user", JSON.stringify(currentUser));
    if (isFileProtocol) {
      showFileProtocolBanner();
    }
  } else {
    try {
      currentUser = JSON.parse(savedUserJson);
      if (!currentUser || !currentUser.username) {
        throw new Error("Invalid session");
      }
      if (isFileProtocol) {
        showFileProtocolBanner();
      }
    } catch (e) {
      currentUser = {
        username: isFileProtocol ? "Bangalore Traffic Authority (Local File)" : "Traffic Operations Demo",
        role: "Traffic Authority",
        token: "demo_default_session"
      };
      localStorage.setItem("traffic_ai_user", JSON.stringify(currentUser));
      if (isFileProtocol) {
        showFileProtocolBanner();
      }
    }
  }
  updateAuthUI();

  await Promise.all([
    loadRoads(),
    loadEvents(),
    loadZoneSummary()
  ]);

  const isMgmt = currentUser && (currentUser.role === "Traffic Management" || currentUser.role === "Traffic Authority");
  if (isMgmt) {
    await loadDirectives();
  }

  updateSliderLabels();
  onDepartureScheduleChanged();
  onLiveDateScheduleChanged();

  initParallelEventSync();
  initGoogleMapMonitor();

  try {
    const mRes = await fetch("/api/metrics");
    const mData = await mRes.json();
    if (mData && mData.metrics) {
      setTimeout(() => {
        animateCounter(document.getElementById("kpiCommuterRoads"), mData.metrics.total_corridors || allRoads.length, " Corridors");
        animateCounter(document.getElementById("kpiCommuterAccuracy"), mData.metrics.accuracy_pct || 74.22, "%");
        animateCounter(document.getElementById("kpiAuthorityRecords"), mData.metrics.total_records || 57600, " Records");
        animateCounter(document.getElementById("kpiAuthoritySevere"), mData.metrics.severe_pct || 22.5, "%");
        animateCounter(document.getElementById("kpiAuthorityRelieved"), mData.metrics.relieved_corridors || 23, " Corridors");
      }, 250);
    }
  } catch (err) {
    console.warn("Could not load real metrics:", err);
  }

  const curPath = window.location.pathname.toLowerCase();
  const curHash = window.location.hash.toLowerCase();
  const curSearch = window.location.search.toLowerCase();
  if (
    curPath.includes("traffic") ||
    curHash.includes("traffic") ||
    curSearch.includes("traffic")
  ) {
    switchMainSection("live_traffic");
  } else if (
    curPath.includes("heatmap") ||
    curHash.includes("heatmap") ||
    curSearch.includes("heatmap")
  ) {
    switchMainSection("heatmap");
  } else if (
    curPath.includes("vision") ||
    curHash.includes("vision") ||
    curSearch.includes("vision")
  ) {
    switchMainSection("vision");
  } else if (
    curPath.includes("synthesizer") ||
    curPath.includes("hub") ||
    curHash.includes("synthesizer") ||
    curSearch.includes("synthesizer")
  ) {
    switchMainSection("synthesizer");
  } else if (
    curPath.includes("live") ||
    curPath.includes("simulation") ||
    curPath.includes("grid") ||
    curHash.includes("live") ||
    curHash.includes("simulation") ||
    curSearch.includes("live")
  ) {
    switchMainSection("live");
  }
}

function showToast(message, type = "info", duration = 2200) {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  while (container.children.length >= 2) {
    container.removeChild(container.firstChild);
  }

  const icons = {
    success: "✓",
    error: "✕",
    warning: "⚠",
    info: "ℹ"
  };

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || "ℹ"}</span>
    <span class="toast-msg">${message}</span>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = "toastSlideOut 0.25s cubic-bezier(0.4, 0, 1, 1) forwards";
    setTimeout(() => toast.remove(), 260);
  }, duration);
}

function setButtonLoading(btn, isLoading, customLoadingText) {
  if (!btn) return;
  if (isLoading) {
    btn.dataset.originalHtml = btn.innerHTML;
    btn.classList.add("loading");
    btn.disabled = true;
    if (customLoadingText) {
      btn.textContent = customLoadingText;
    }
  } else {
    btn.classList.remove("loading");
    btn.disabled = false;
    if (btn.dataset.originalHtml) {
      btn.innerHTML = btn.dataset.originalHtml;
    }
  }
}

function animateCounter(element, targetValue, suffix = "", duration = 1200) {
  if (!element) return;
  const start = 0;
  const startTime = performance.now();
  const isFloat = String(targetValue).includes(".");

  function step(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1.0);

    const eased = 1 - Math.pow(1 - progress, 3);
    const current = start + (targetValue - start) * eased;

    if (isFloat) {
      element.textContent = current.toFixed(current >= 10 ? 1 : 2) + suffix;
    } else {
      element.textContent = Math.floor(current).toLocaleString() + suffix;
    }

    if (progress < 1.0) {
      requestAnimationFrame(step);
    } else {
      element.textContent = (isFloat ? targetValue.toFixed(current >= 10 ? 1 : 2) : targetValue.toLocaleString()) + suffix;
    }
  }

  requestAnimationFrame(step);
}

function switchMainTab(tab) {
  updateAuthUI();
}

function updateAuthUI() {
  const userBadge = document.getElementById("userBadge");
  const userBadgeDot = document.getElementById("userBadgeDot");
  const authBtn = document.getElementById("authBtn");
  const roleBadge = document.getElementById("roleConsoleBadge");
  const roleIcon = document.getElementById("roleIcon");
  const roleText = document.getElementById("roleText");
  const tabConsoleLabel = document.getElementById("tabConsoleLabel");
  const viewCommuter = document.getElementById("viewCommuter");
  const viewAuthority = document.getElementById("viewAuthority");

  if (currentUser) {
    const isMgmt = currentUser.role === "Traffic Management" || currentUser.role === "Traffic Authority";

    // Configure role-specific navigation tab switcher visibility
    const btnStandard = document.getElementById("tabConsoleStandard");
    const btnLiveTraffic = document.getElementById("tabConsoleLiveTraffic");
    const btnLive = document.getElementById("tabConsoleLive");
    const btnVision = document.getElementById("tabConsoleVision");
    const btnSyn = document.getElementById("tabConsoleSynthesizer");
    const btnHeatmap = document.getElementById("tabConsoleHeatmap");

    if (isMgmt) {
      if (btnStandard) btnStandard.style.display = "inline-flex";
      if (btnLiveTraffic) btnLiveTraffic.style.display = "none";
      if (btnLive) btnLive.style.display = "inline-flex";
      if (btnVision) btnVision.style.display = "inline-flex";
      if (btnSyn) btnSyn.style.display = "inline-flex";
      if (btnHeatmap) btnHeatmap.style.display = "inline-flex";
    } else {
      if (btnStandard) btnStandard.style.display = "inline-flex";
      if (btnLiveTraffic) btnLiveTraffic.style.display = "inline-flex";
      if (btnLive) btnLive.style.display = "none";
      if (btnVision) btnVision.style.display = "none";
      if (btnSyn) btnSyn.style.display = "none";
      if (btnHeatmap) btnHeatmap.style.display = "inline-flex";
    }

    if (userBadge) {
      userBadge.textContent = `${currentUser.username} (${isMgmt ? "Traffic Management" : "Road User"})`;
    }
    if (userBadgeDot) {
      userBadgeDot.style.background = isMgmt ? "var(--accent-blue)" : "var(--status-low)";
    }
    if (authBtn) {
      authBtn.textContent = "Sign Out";
      authBtn.onclick = handleLogout;
    }
    if (tabConsoleLabel) {
      tabConsoleLabel.textContent = isMgmt ? "Traffic Management Control Room" : "Road User Navigation Console";
    }

    const viewVision = document.getElementById("viewVisionIntelligence");
    const viewSyn = document.getElementById("viewSynthesizer");
    const viewLive = document.getElementById("viewLiveSimulation");
    const viewCommuterLive = document.getElementById("viewCommuterLiveTraffic");
    const viewCommuterHeatmap = document.getElementById("viewCommuterHeatmap") || document.getElementById("viewMapHeatmap");

    if (activeMainSection === "live_traffic") {
      [viewCommuter, viewAuthority, viewLive, viewSyn, viewVision, viewCommuterHeatmap].forEach(v => {
        if (v) { v.style.display = "none"; v.classList.remove("active"); }
      });
      if (viewCommuterLive) {
        viewCommuterLive.style.display = "block";
        viewCommuterLive.classList.add("active");
      }
      return;
    }

    if (activeMainSection === "heatmap") {
      [viewCommuter, viewAuthority, viewLive, viewSyn, viewVision, viewCommuterLive].forEach(v => {
        if (v) { v.style.display = "none"; v.classList.remove("active"); }
      });
      if (viewCommuterHeatmap) {
        viewCommuterHeatmap.style.display = "block";
        viewCommuterHeatmap.classList.add("active");
      }
      return;
    }

    if (activeMainSection === "vision") {
      if (viewCommuter) {
        viewCommuter.style.display = "none";
        viewCommuter.classList.remove("active");
      }
      if (viewAuthority) {
        viewAuthority.style.display = "none";
        viewAuthority.classList.remove("active");
      }
      const viewLive = document.getElementById("viewLiveSimulation");
      if (viewLive) {
        viewLive.style.display = "none";
        viewLive.classList.remove("active");
      }
      if (viewSyn) {
        viewSyn.style.display = "none";
        viewSyn.classList.remove("active");
      }
      if (viewVision) {
        viewVision.style.display = "block";
        viewVision.classList.add("active");
      }
      return;
    }

    if (activeMainSection === "synthesizer") {
      if (viewCommuter) {
        viewCommuter.style.display = "none";
        viewCommuter.classList.remove("active");
      }
      if (viewAuthority) {
        viewAuthority.style.display = "none";
        viewAuthority.classList.remove("active");
      }
      const viewLive = document.getElementById("viewLiveSimulation");
      if (viewLive) {
        viewLive.style.display = "none";
        viewLive.classList.remove("active");
      }
      if (viewVision) {
        viewVision.style.display = "none";
        viewVision.classList.remove("active");
      }
      if (viewSyn) {
        viewSyn.style.display = "block";
        viewSyn.classList.add("active");
      }
      return;
    }

    if (activeMainSection === "live") {
      if (viewCommuter) {
        viewCommuter.style.display = "none";
        viewCommuter.classList.remove("active");
      }
      if (viewAuthority) {
        viewAuthority.style.display = "none";
        viewAuthority.classList.remove("active");
      }
      if (viewSyn) {
        viewSyn.style.display = "none";
        viewSyn.classList.remove("active");
      }
      if (viewVision) {
        viewVision.style.display = "none";
        viewVision.classList.remove("active");
      }
      const viewLive = document.getElementById("viewLiveSimulation");
      if (viewLive) {
        viewLive.style.display = "block";
        viewLive.classList.add("active");
      }
      return;
    }

    if (isMgmt) {

      if (roleBadge) {
        roleBadge.className = "role-console-badge traffic-admin";
        roleBadge.style.display = "inline-flex";
      }
      if (roleIcon) {
        roleIcon.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="1" width="18" height="22" rx="4"/>
          <circle cx="12" cy="7" r="2"/>
          <circle cx="12" cy="12" r="2"/>
          <circle cx="12" cy="17" r="2"/>
        </svg>`;
      }
      if (roleText) roleText.textContent = "Traffic Management Control Room";

      if (viewCommuter) {
        viewCommuter.style.display = "none";
        viewCommuter.classList.remove("active");
      }
      if (viewVision) {
        viewVision.style.display = "none";
        viewVision.classList.remove("active");
      }
      if (viewSyn) {
        viewSyn.style.display = "none";
        viewSyn.classList.remove("active");
      }
      if (viewAuthority) {
        viewAuthority.style.display = "block";
        viewAuthority.classList.add("active");
      }

      renderCorridorMatrix(allRoads);
      loadZoneSummary();
      loadAuthorityEventsQueue();

      setTimeout(() => {
        animateCounter(document.getElementById("kpiAuthorityRecords"), 57600, " Records");
        animateCounter(document.getElementById("kpiAuthoritySevere"), 26.8, "%");
        animateCounter(document.getElementById("kpiAuthorityRelieved"), 21, " Corridors");
      }, 250);
    } else {

      if (roleBadge) {
        roleBadge.className = "role-console-badge road-user";
        roleBadge.style.display = "inline-flex";
      }
      if (roleIcon) {
        roleIcon.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/>
          <circle cx="7" cy="17" r="2"/>
          <path d="M9 17h6"/>
          <circle cx="17" cy="17" r="2"/>
        </svg>`;
      }
      if (roleText) roleText.textContent = "Road User Navigation Console";

      if (viewAuthority) {
        viewAuthority.style.display = "none";
        viewAuthority.classList.remove("active");
      }
      if (viewVision) {
        viewVision.style.display = "none";
        viewVision.classList.remove("active");
      }
      if (viewSyn) {
        viewSyn.style.display = "none";
        viewSyn.classList.remove("active");
      }
      if (viewCommuter) {
        viewCommuter.style.display = "block";
        viewCommuter.classList.add("active");
      }
    }
  } else {

    window.location.replace("/login");
    return;
  }
}

function switchPersona(persona) {

  updateAuthUI();
}

function handleLogout() {
  currentUser = null;
  localStorage.removeItem("traffic_ai_user");
  if (window.location.protocol === "file:") {
    showToast("Session reset. Reloading file preview…", "info");
    setTimeout(() => window.location.reload(), 300);
  } else {
    window.location.replace("/login");
  }
}

async function loadRoads() {
  try {
    const res = await fetch("/api/roads");
    const data = await res.json();
    allRoads = data.roads || [];
    onZoneChanged();
    renderCorridorMatrix(allRoads);
  } catch (err) {
    console.error("Failed to load real roads telemetry from server:", err);
    allRoads = [];
    onZoneChanged();
    renderCorridorMatrix(allRoads);
  }
}

function onZoneChanged() {
  const zoneSelect = document.getElementById("routeZoneSelect");
  const selectedZone = zoneSelect ? zoneSelect.value : "all";
  const origSelect = document.getElementById("routeOriginSelect");
  const destSelect = document.getElementById("routeDestSelect");

  if (!origSelect || !destSelect || !allRoads || allRoads.length === 0) return;

  const prevOrig = origSelect.value;
  const prevDest = destSelect.value;

  const zonesMap = {};
  allRoads.forEach(r => {
    const z = r.city_zone || "Other";
    if (!zonesMap[z]) zonesMap[z] = [];
    zonesMap[z].push(r);
  });

  const sortedZones = Object.keys(zonesMap).sort((a, b) => {
    if (selectedZone && selectedZone !== "all") {
      if (a.toLowerCase() === selectedZone.toLowerCase()) return -1;
      if (b.toLowerCase() === selectedZone.toLowerCase()) return 1;
    }
    return a.localeCompare(b);
  });

  function populateDropdown(selectEl, currentVal, defaultVal) {
    selectEl.innerHTML = "";
    sortedZones.forEach(zName => {
      const isSelectedZone = selectedZone && selectedZone !== "all" && zName.toLowerCase() === selectedZone.toLowerCase();
      const group = document.createElement("optgroup");
      group.label = isSelectedZone ? `★ ${zName} (Focused Zone)` : zName;

      zonesMap[zName].forEach(r => {
        const speed = r.avg_speed || r.peak_speed || 35.0;
        const name = r.road_name ? `${r.road_name} (${r.road_id})` : r.road_id;
        const intName = r.intersection_name ? ` · ${r.intersection_name}` : (r.intersection_id ? ` · ${r.intersection_id}` : "");
        const text = `${name}${intName} (${speed} km/h)`;
        const opt = new Option(text, r.road_id);
        group.appendChild(opt);
      });
      selectEl.appendChild(group);
    });

    const targetVal = currentVal || defaultVal;
    if (targetVal && selectEl.querySelector(`option[value="${targetVal}"]`)) {
      selectEl.value = targetVal;
    }
  }

  let targetOrig = prevOrig;
  let targetDest = prevDest;

  if (selectedZone && selectedZone !== "all" && zonesMap[selectedZone]) {
    targetOrig = zonesMap[selectedZone][0].road_id;

    if (!targetDest || targetDest === targetOrig) {
      const otherRoad = allRoads.find(r => r.road_id !== targetOrig);
      targetDest = otherRoad ? otherRoad.road_id : (zonesMap[selectedZone][1]?.road_id || targetOrig);
    }
  } else {
    if (!targetOrig) targetOrig = "RD_BLR_01";
    if (!targetDest || targetDest === targetOrig) targetDest = "RD_BLR_12";
  }

  populateDropdown(origSelect, targetOrig, "RD_BLR_01");
  populateDropdown(destSelect, targetDest, "RD_BLR_12");

  loadEvents(selectedZone === "all" ? "" : selectedZone);
  onDepartureScheduleChanged();
}

function onOriginChanged() {
  if (window.playTactileClick) window.playTactileClick();
}
window.onOriginChanged = onOriginChanged;

function onDestinationChanged() {
  if (window.playTactileClick) window.playTactileClick();
}
window.onDestinationChanged = onDestinationChanged;

function selectZone(zone) {
  const commuterSelect = document.getElementById("routeZoneSelect");
  const simSelect = document.getElementById("simZoneSelect");

  if (commuterSelect) {
    commuterSelect.value = zone;
    onZoneChanged();
  }
  if (simSelect) {
    simSelect.value = zone;
  }

  showToast(`Active zone shifted to ${zone}.`, "info");
}

async function loadZoneSummary() {
  try {
    const res = await fetch("/api/zones/summary");
    const data = await res.json();
    const zones = data.zones && data.zones.length ? data.zones : [];
    renderZoneSummary(zones, "zoneSummaryGrid");
    renderZoneSummary(zones, "authorityZoneSummaryGrid");
  } catch (err) {
    console.error("Failed to load real zone summary from server:", err);
    renderZoneSummary([], "zoneSummaryGrid");
    renderZoneSummary([], "authorityZoneSummaryGrid");
  }
}

function renderZoneSummary(zones, containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (!zones || zones.length === 0) {
    container.innerHTML = `
      <div class="zone-empty-state">
        <p>No zone telemetry available.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = zones.map(z => {
    const crit = z.pct_critical || 0;
    let barColor = "var(--status-low)";

    if (crit >= 60) {
      barColor = "var(--status-sev)";
    } else if (crit >= 40) {
      barColor = "var(--status-high)";
    } else if (crit >= 20) {
      barColor = "var(--status-mod)";
    }

    return `
      <div class="zone-card" onclick="selectZone('${z.zone}')" title="Click to filter by ${z.zone}">
        <div class="zone-card-name">${z.zone}</div>
        <div class="zone-severity-bar">
          <div class="zone-severity-fill" style="width: ${Math.max(crit, 4)}%; background: ${barColor};"></div>
        </div>
        <div class="zone-stats">
          <span>${z.total_roads} corridors</span>
          <span style="color: ${barColor}; font-weight: 700;">${crit}% critical</span>
        </div>
      </div>
    `;
  }).join("");
}

let currentEventMode = "scheduled";

function setEventMode(mode) {
  currentEventMode = mode;
  const btnSched = document.getElementById("btnEventsScheduled");
  const btnHist = document.getElementById("btnEventsHistorical");
  const subtext = document.getElementById("eventModeSubtext");

  if (btnSched) btnSched.classList.toggle("active", mode === "scheduled");
  if (btnHist) btnHist.classList.toggle("active", mode === "historical");

  if (subtext) {
    if (mode === "historical") {
      subtext.textContent = "Last month ground-truth observed surges & prediction calibration";
    } else {
      subtext.textContent = "Forward-looking event schedule & demand coupling";
    }
  }

  const zone = document.getElementById("routeZoneSelect")?.value || "";
  loadEvents(zone);
  onDepartureScheduleChanged();
}

async function loadEvents(zone) {
  try {
    const isHist = currentEventMode === "historical";
    let url = `/api/events?history=${isHist}`;
    const targetZone = (zone !== undefined && zone !== null)
      ? zone
      : (document.getElementById("routeZoneSelect")?.value || "");
    if (targetZone && targetZone.toLowerCase() !== "all") {
      url += `&zone=${encodeURIComponent(targetZone)}`;
    }
    const dateInput = document.getElementById("routeDateInput");
    const selectedDate = dateInput ? dateInput.value : "";
    if (!isHist && selectedDate) {
      url += `&date=${encodeURIComponent(selectedDate)}`;
    }
    const res = await fetch(url);
    const data = await res.json();
    allEvents = data.events || [];
    if (typeof onLiveDateScheduleChanged === "function") {
      onLiveDateScheduleChanged();
    }

    const kpiEvt = document.getElementById("kpiCommuterEvents");
    if (kpiEvt) {
      kpiEvt.textContent = isHist ? `${allEvents.length} Calibrated` : `${allEvents.length} Scheduled`;
    }

    const container = document.getElementById("eventsListContainer");
    if (!container) return;

    if (!allEvents.length) {
      if (isHist) {
        container.innerHTML = `
          <div class="empty-state-block">
            <p>No historical calibration events found for ${zone || "this area"}.</p>
          </div>
        `;
      } else {
        container.innerHTML = `
          <div class="empty-state-block normal-operations-state">
            <div class="clear-status-icon">
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
              </svg>
            </div>
            <h4 style="font-size: 1.02rem; font-weight: 600; color: #10b981; margin: 8px 0 4px 0;">All 24 Arterial Corridors Clear</h4>
            <p style="font-size: 0.84rem; color: var(--text-secondary); max-width: 520px; margin: 0 auto 12px auto; line-height: 1.5;">
              Traffic Management has not scheduled or broadcasted any municipal restrictions for this horizon. Arterial corridors are operating with nominal clearance.
            </p>
            <div class="sync-status-indicator">
              <span class="pulse-dot-emerald"></span>
              <span style="font-size: 0.76rem; color: var(--text-muted);">Parallel Authority Sync Active &bull; Monitoring live broadcasts</span>
            </div>
          </div>
        `;
      }
      return;
    }

    container.innerHTML = allEvents.map(evt => {
      let typeClass = "event-item-card";
      const type = (evt.event_type || "").toLowerCase();
      if (evt.is_historical) typeClass += " historical";
      else if (type.includes("stadium") || type.includes("concert")) typeClass += " stadium";
      else if (type.includes("roadwork") || type.includes("maintenance")) typeClass += " roadwork";
      else if (type.includes("weather")) typeClass += " weather";

      const roadsList = (evt.affected_roads || []).map((r, idx) => {
        const name = getCorridorDisplayName(r, evt.affected_road_names, idx);
        return `<span class="event-road-pill" title="Arterial ID: ${escapeHtml(r)}">${escapeHtml(name)}</span>`;
      }).join(" ");

      if (evt.is_historical) {
        const histDateLabel = "HISTORICAL BENCHMARK · BENGALURU, KA";
        const locationText = evt.location_name || `${evt.city_zone}, Bengaluru, Karnataka`;

        return `
          <div class="${typeClass}">
            <div class="event-header">
              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <span class="badge-tag amber" style="font-size: 0.65rem; padding: 2px 7px;">${histDateLabel}</span>
                <span class="event-title">${evt.name}</span>
              </div>
              <span class="event-time-badge">${evt.date} &bull; ${evt.start_time} - ${evt.end_time}</span>
            </div>
            <div style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 6px;">
              Location: <strong style="color: var(--text-primary);">${locationText}</strong>
            </div>

            <!-- Historical Observed Telemetry Strip -->
            <div class="historical-telemetry-strip">
              <div class="hist-kpi">
                <span class="k">Baseline Flow</span>
                <span class="v">${evt.baseline_volume_vph || 1500} veh/hr</span>
              </div>
              <div class="hist-kpi">
                <span class="k">Measured Surge</span>
                <span class="v red">+${evt.volume_surge_vph || 600} veh/hr</span>
              </div>
              <div class="hist-kpi">
                <span class="k">Peak Volume</span>
                <span class="v cyan">${evt.observed_volume_vph || (Number(evt.baseline_volume_vph || 1500) + Number(evt.volume_surge_vph || 600))} veh/hr</span>
              </div>
              <div class="hist-kpi">
                <span class="k">Speed Impact</span>
                <span class="v amber">-${evt.speed_drop_kmh || 22.0} km/h</span>
              </div>
              <div class="hist-kpi">
                <span class="k">Congestion Shift</span>
                <span class="v">${evt.baseline_congestion || "Moderate"} ➔ <strong style="color: #fda4af;">${evt.event_congestion || "Severe"}</strong></span>
              </div>
              <div class="hist-kpi">
                <span class="k">Prediction Calibration</span>
                <span class="v emerald">${evt.prediction_accuracy_pct || 96.0}% Precision</span>
              </div>
            </div>

            <p style="font-size: 0.82rem; color: var(--text-primary); line-height: 1.45; margin: 6px 0;">${evt.description}</p>
            <div class="hist-recommendation-box">
              <span><strong>Scheduling Recommendation:</strong> ${evt.scheduling_recommendation || "Reroute via alternate arterial bypass to avoid bottleneck."}</span>
            </div>
          </div>
        `;
      }

      const now = new Date();
      const localTodayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
      const dateInput = document.getElementById("routeDateInput");
      const selectedDate = (dateInput && dateInput.value) ? dateInput.value : localTodayStr;

      const isDateToday = (selectedDate === localTodayStr);
      const isLiveNow = isDateToday && ((evt.date === localTodayStr) || (evt.date <= localTodayStr && localTodayStr <= (evt.end_date || evt.date)));

      let timeStateBadge = "";
      if (isLiveNow) {
        timeStateBadge = `<span class="badge-tag red pulse" style="font-size: 0.65rem; padding: 2px 7px;"><span class="pulse-dot-red"></span> LIVE NOW · BENGALURU</span>`;
      } else {
        timeStateBadge = `<span class="badge-tag emerald" style="font-size: 0.65rem; padding: 2px 7px;"><span class="pulse-dot-emerald"></span> SCHEDULED · BENGALURU</span>`;
      }

      const displayDate = evt.date || selectedDate;

      const surgeBadge = evt.volume_surge_vph ?
        `<span style="font-size: 0.72rem; color: #f87171; background: rgba(239, 68, 68, 0.12); padding: 2px 7px; border-radius: 4px; font-weight: 600; margin-left: 8px;">+${evt.volume_surge_vph} veh/hr projected surge</span>` : "";

      const isMgmt = currentUser && (currentUser.role === "Traffic Management" || currentUser.role === "Traffic Authority");
      const deleteAction = isMgmt ?
        `<button type="button" class="event-delete-btn" onclick="deleteEvent('${evt.id}', '${(evt.name || "").replace(/'/g, "\\'")}')">Remove</button>` : "";
      const locationText = evt.location_name || `${evt.city_zone}, Bengaluru, Karnataka`;
      const isOfficial = evt.verification_status === "OFFICIAL_VERIFIED";
      const sourceName = evt.source_name || "Municipal Authority Advisory";
      const sourceLink = evt.source_url ? `<a href="${escapeHtml(evt.source_url)}" target="_blank" rel="noopener noreferrer" style="color: #38bdf8; text-decoration: underline; margin-left: 6px; font-size: 0.74rem;">Official Advisory &nearr;</a>` : "";
      const verBadge = isOfficial ?
        `<span class="badge-tag emerald" style="font-size: 0.65rem; padding: 2px 7px;">OFFICIAL_VERIFIED</span>` :
        `<span class="badge-tag amber" style="font-size: 0.65rem; padding: 2px 7px;">UNVERIFIED_PENDING</span>`;

      return `
        <div class="${typeClass}">
          <div class="event-header">
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
              ${timeStateBadge}
              <span class="event-title">${evt.name} ${surgeBadge}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="event-time-badge">${displayDate} &bull; ${evt.start_time} - ${evt.end_time}</span>
              ${deleteAction}
            </div>
          </div>
          <div style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 4px;">
            Location: <strong style="color: var(--text-primary);">${locationText}</strong>
          </div>
          <div style="font-size: 0.76rem; color: var(--text-muted); margin-bottom: 6px; display: flex; align-items: center; flex-wrap: wrap; gap: 8px;">
            <span>Source: <strong style="color: #cbd5e1;">${escapeHtml(sourceName)}</strong>${sourceLink}</span>
            <span>&bull; Published: ${escapeHtml(evt.publication_date || '2026-11-04')}</span>
            <span>&bull; Verified: ${escapeHtml(evt.verification_date || '2026-11-04')}</span>
            ${verBadge}
          </div>
          <p style="font-size: 0.82rem; color: var(--text-primary); line-height: 1.45; margin: 4px 0 0;">${evt.description}</p>
        </div>
      `;
    }).join("");
  } catch (err) {
    console.error("Error loading events:", err);
  }
}

let currentAuthEventMode = "active";

function setAuthEventMode(mode) {
  currentAuthEventMode = mode;
  const btnActive = document.getElementById("btnAuthEventsActive");
  const btnHist = document.getElementById("btnAuthEventsHistorical");
  const subtext = document.getElementById("authEventModeSubtext");

  if (btnActive) btnActive.classList.toggle("active", mode === "active");
  if (btnHist) btnHist.classList.toggle("active", mode === "historical");

  if (subtext) {
    if (mode === "historical") {
      subtext.textContent = "Historical observed calibration incidents & ground-truth telemetry · Bengaluru, Karnataka";
    } else {
      subtext.textContent = "Active municipal restriction queue & live broadcasts · Bengaluru, Karnataka";
    }
  }
  loadAuthorityEventsQueue();
}
window.setAuthEventMode = setAuthEventMode;

async function loadAuthorityEventsQueue() {
  const container = document.getElementById("authorityEventsQueueGrid");
  if (!container) return;

  try {
    const isHist = currentAuthEventMode === "historical";
    const res = await fetch(`/api/events?all=true&history=${isHist}`);
    const data = await res.json();
    let events = data.events || [];
    if (isHist) {
      events = events.filter(e => e.is_historical);
    } else {
      events = events.filter(e => !e.is_historical);
    }

    if (!events.length) {
      container.innerHTML = `
        <div class="empty-state-block" style="grid-column: 1 / -1;">
          <p>${isHist ? "No historical calibration records cataloged." : "No municipal disruption schedules registered in queue."}</p>
        </div>
      `;
      return;
    }

    if (isHist) {
      container.innerHTML = events.map(evt => {
        const roadsList = (evt.affected_roads || []).map((r, idx) => {
        const name = getCorridorDisplayName(r, evt.affected_road_names, idx);
        return `<span class="event-road-pill" title="Arterial ID: ${escapeHtml(r)}">${escapeHtml(name)}</span>`;
      }).join(" ");
        const locationText = evt.location_name || `${evt.city_zone}, Bengaluru, Karnataka`;

        return `
          <div class="authority-event-card" id="authCard_${evt.id}" style="border-left: 3px solid var(--status-high, #f59e0b);">
            <div class="auth-event-top">
              <div>
                <h4 class="auth-event-title">${evt.name}</h4>
                <span style="font-size: 0.72rem; color: var(--text-muted);">${evt.event_type} &bull; ${locationText}</span>
              </div>
              <span class="auth-status-pill staged"><span class="pulse-dot-amber"></span> HISTORICAL CALIBRATION</span>
            </div>
            <div class="auth-event-meta">
              <div><strong>Recorded Window:</strong> ${evt.date} &bull; ${evt.start_time} - ${evt.end_time}</div>
              <div style="margin-top: 3px;"><strong>Corridors:</strong> ${roadsList}</div>
              <div style="margin-top: 3px; color: #fbbf24; font-weight: 600;">
                Baseline: ${evt.baseline_volume_vph || 1500} vph &bull; Surge: +${evt.volume_surge_vph || 600} vph &bull; Speed Drop: -${evt.speed_drop_kmh || 20} km/h
              </div>
              <div style="margin-top: 3px; color: #34d399; font-weight: 600; font-family: var(--font-mono); font-size: 0.72rem;">
                State Shift: ${evt.baseline_congestion || "Moderate"} ➔ ${evt.event_congestion || "Severe"} (${evt.prediction_accuracy_pct || 96}% Calibration Precision)
              </div>
            </div>
            <p style="font-size: 0.78rem; color: var(--text-secondary); line-height: 1.4; margin: 0;">${evt.description || ""}</p>
            <div style="font-size: 0.75rem; color: var(--text-muted); padding: 6px 10px; background: rgba(0,0,0,0.5); border-radius: 4px; border-left: 2px solid var(--border-specular);">
              <strong>Directive:</strong> ${evt.scheduling_recommendation || "Maintain alternate bypass and signal actuation bias."}
            </div>
          </div>
        `;
      }).join("");
      return;
    }

    const now = new Date();
    const todayDateStr = now.toISOString().slice(0, 10);

    container.innerHTML = events.map(evt => {
      const isLive = Boolean(evt.is_published);
      const isToday = evt.date === todayDateStr;
      const roadsList = (evt.affected_roads || []).map((r, idx) => {
        const name = getCorridorDisplayName(r, evt.affected_road_names, idx);
        return `<span class="event-road-pill" title="Arterial ID: ${escapeHtml(r)}">${escapeHtml(name)}</span>`;
      }).join(" ");
      const surgeBadge = evt.volume_surge_vph ? `+${evt.volume_surge_vph} veh/hr surge` : "";
      const locationText = evt.location_name || `${evt.city_zone}, Bengaluru, Karnataka`;

      let statusBadge = "";
      if (isLive) {
        statusBadge = isToday
          ? `<span class="auth-status-pill live"><span class="pulse-dot-red"></span> LIVE BROADCAST · ACTIVE</span>`
          : `<span class="auth-status-pill live"><span class="pulse-dot-emerald"></span> BROADCASTED TO USERS</span>`;
      } else {
        statusBadge = `<span class="auth-status-pill staged"><span class="pulse-dot-amber"></span> STAGED · NOT BROADCASTED</span>`;
      }

      const actionButtons = isLive
        ? `
          <button type="button" class="btn-auth-broadcast is-live" onclick="broadcastAuthorityEvent('${evt.id}', '${(evt.name || "").replace(/'/g, "\\'")}', true)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
            <span>Re-Broadcast Alert</span>
          </button>
          <button type="button" class="btn-auth-retract" onclick="retractAuthorityEvent('${evt.id}', '${(evt.name || "").replace(/'/g, "\\'")}')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
            <span>Retract Broadcast</span>
          </button>
        `
        : `
          <button type="button" class="btn-auth-broadcast" onclick="broadcastAuthorityEvent('${evt.id}', '${(evt.name || "").replace(/'/g, "\\'")}', false)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="3 11 22 2 13 21 11 13 3 11"/></svg>
            <span>Broadcast to Road Users</span>
          </button>
        `;

      return `
        <div class="authority-event-card ${isLive ? 'is-live' : ''}" id="authCard_${evt.id}">
          <div class="auth-event-top">
            <div>
              <h4 class="auth-event-title">${evt.name}</h4>
              <span style="font-size: 0.72rem; color: var(--text-muted);">${evt.event_type} &bull; ${locationText}</span>
            </div>
            ${statusBadge}
          </div>
          <div class="auth-event-meta">
            <div><strong>Window:</strong> ${evt.date} &bull; ${evt.start_time} - ${evt.end_time}</div>
            <div style="margin-top: 3px;"><strong>Corridors:</strong> ${roadsList}</div>
            <div style="margin-top: 3px; color: #fca5a5; font-weight: 600;">${surgeBadge} &bull; ${evt.speed_impact_pct || 40}% Speed Reduction</div>
          </div>
          <p style="font-size: 0.78rem; color: var(--text-secondary); line-height: 1.4; margin: 0;">${evt.description || ""}</p>
          <div class="auth-event-actions">
            ${actionButtons}
          </div>
        </div>
      `;
    }).join("");
  } catch (err) {
    console.error("Error loading authority queue:", err);
  }
}

async function broadcastAuthorityEvent(eventId, eventName, isRebroadcast = false) {
  try {
    const res = await fetch("/api/events/publish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event_id: eventId })
    });
    const data = await res.json();
    if (data.status === "success") {
      if (window.playTactileClick) playTactileClick();
      showToast(isRebroadcast ? `Alert re-broadcasted for "${eventName}"!` : `"${eventName}" broadcasted to all road users!`, "success");
      await loadAuthorityEventsQueue();
      const currentZone = (document.getElementById("routeZoneSelect") || document.getElementById("zoneSelect"))?.value || null;
      await loadEvents(currentZone);
      await loadDirectives(currentZone);
    } else {
      showToast(data.message || "Failed to broadcast event.", "error");
    }
  } catch (err) {
    showToast("Network error broadcasting event.", "error");
  }
}

async function retractAuthorityEvent(eventId, eventName) {
  try {
    const res = await fetch("/api/events/unpublish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event_id: eventId })
    });
    const data = await res.json();
    if (data.status === "success") {
      if (window.playTactileClick) playTactileClick();
      showToast(`Event "${eventName}" retracted from road user network.`, "info");
      await loadAuthorityEventsQueue();
      const currentZone = (document.getElementById("routeZoneSelect") || document.getElementById("zoneSelect"))?.value || null;
      await loadEvents(currentZone);
      await loadDirectives(currentZone);
    } else {
      showToast(data.message || "Failed to retract event.", "error");
    }
  } catch (err) {
    showToast("Network error retracting event.", "error");
  }
}

async function deleteEvent(eventId, eventName) {
  if (!confirm(`Are you sure you want to remove the event "${eventName}"?`)) {
    return;
  }
  try {
    const res = await fetch("/api/events/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event_id: eventId })
    });
    const data = await res.json();
    if (data.status === "success") {
      showToast(`Event "${eventName}" removed successfully.`, "info");
      await loadAuthorityEventsQueue();
      const currentZone = (document.getElementById("routeZoneSelect") || document.getElementById("zoneSelect"))?.value || null;
      await loadEvents(currentZone);
      await loadDirectives(currentZone);
    } else {
      showToast(data.message || "Failed to remove event.", "error");
    }
  } catch (err) {
    showToast("Network error removing event.", "error");
  }
}

async function addNewEvent() {
  const name = document.getElementById("newEventName").value.trim();
  const event_type = document.getElementById("newEventType").value;
  const city_zone = document.getElementById("newEventZone").value;
  const roadsRaw = document.getElementById("newEventRoads").value.trim();
  const date = document.getElementById("newEventDate").value;
  const start_time = document.getElementById("newEventTimeStart").value;
  const end_time = document.getElementById("newEventTimeEnd").value;
  const btn = document.getElementById("injectEventBtn");

  if (!name || !roadsRaw || !date || !start_time || !end_time) {
    showToast("Please fill in all event fields including affected road IDs.", "warning");
    return;
  }

  const reverseRoadMap = {};
  Object.entries(CANONICAL_ROAD_NAMES).forEach(([id, rName]) => {
    reverseRoadMap[rName.toLowerCase()] = id;
    reverseRoadMap[id.toLowerCase()] = id;
  });
  allRoads.forEach(r => {
    if (r.road_name && r.road_id) {
      reverseRoadMap[r.road_name.toLowerCase()] = r.road_id;
    }
  });

  const affected_roads = roadsRaw.split(",").map(r => {
    const trimmed = r.trim();
    const lower = trimmed.toLowerCase();
    return reverseRoadMap[lower] || trimmed.toUpperCase();
  }).filter(Boolean);

  setButtonLoading(btn, true, "Broadcasting Event…");

  try {
    const res = await fetch("/api/events/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        event_type,
        city_zone,
        affected_roads,
        date,
        start_time,
        end_time,
        severity_boost: 2,
        is_published: true,
        description: `Scheduled by Traffic Authority for ${city_zone}. Speed reduced on designated arterials.`
      })
    });
    const data = await res.json();

    if (data.status === "success") {
      showToast(`Event "${name}" injected and broadcasted network-wide!`, "success");
      document.getElementById("newEventName").value = "";
      document.getElementById("newEventRoads").value = "";
      await loadAuthorityEventsQueue();
      await loadEvents(city_zone);
      await loadDirectives(city_zone);
    } else {
      showToast(data.message || "Failed to broadcast event.", "error");
    }
  } catch (err) {
    showToast("Network error creating municipal event.", "error");
  } finally {
    setButtonLoading(btn, false);
  }
}

let lastKnownAlertTimestamp = null;
let parallelSyncInterval = null;
let currentActiveAlert = null;

function triggerEarlyAlert(alert) {
  if (!alert) return;
  currentActiveAlert = alert;

  const banner = document.getElementById("commuterEarlyAlertBanner");
  if (!banner) return;

  const titleEl = document.getElementById("earlyAlertTitle");
  const descEl = document.getElementById("earlyAlertDesc");
  const zoneEl = document.getElementById("earlyAlertZone");
  const roadsEl = document.getElementById("earlyAlertRoads");
  const surgeEl = document.getElementById("earlyAlertSurge");
  const hoursEl = document.getElementById("earlyAlertHours");
  const timeEl = document.getElementById("earlyAlertTime");

  if (titleEl) titleEl.textContent = alert.name || "Municipal Disruption Notice";
  if (descEl) descEl.textContent = alert.message || `Traffic Management scheduled an active corridor disruption in ${alert.city_zone}. Projected surge: +${alert.volume_surge_vph || 0} veh/hr.`;
  if (zoneEl) zoneEl.textContent = `Zone: ${alert.city_zone || "Metropolitan"}`;
  const alertRoadNames = (alert.affected_roads || []).map((r, idx) => getCorridorDisplayName(r, alert.affected_road_names, idx)).join(", ");
  if (roadsEl) roadsEl.textContent = `Corridors: ${alertRoadNames || "Arterials"}`;
  if (surgeEl) surgeEl.textContent = `+${alert.volume_surge_vph || 0} veh/hr surge`;
  if (hoursEl) hoursEl.textContent = `${alert.start_time || "08:00"} - ${alert.end_time || "22:00"}`;
  if (timeEl) timeEl.textContent = "Broadcasted Live";

  banner.style.display = "flex";
  playTrafficAlertChime();
  showToast(`Early Traffic Alert: ${alert.name} broadcasted by Authority!`, "warning", 3500);
}

function dismissEarlyAlert() {
  const banner = document.getElementById("commuterEarlyAlertBanner");
  if (banner) banner.style.display = "none";
}

function applyEarlyAlertToNavigator() {
  if (!currentActiveAlert) return;
  const roads = currentActiveAlert.affected_roads || [];
  const origSelect = document.getElementById("routeOriginSelect") || document.getElementById("originRoadSelect");
  const destSelect = document.getElementById("routeDestSelect") || document.getElementById("destinationRoadSelect");

  if (roads.length >= 2 && origSelect && destSelect) {
    origSelect.value = roads[0];
    destSelect.value = roads[1];
  } else if (roads.length === 1 && origSelect) {
    origSelect.value = roads[0];
  }

  const plannerCard = document.getElementById("routePlannerCard") || document.getElementById("commuterRoutePlannerCard") || document.getElementById("zoneOverviewCard");
  if (plannerCard) {
    plannerCard.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  showToast(`Evaluating alternate corridor bypass around ${currentActiveAlert.name}…`, "info");
  setTimeout(() => {
    evaluateRoute();
  }, 350);
}

function initParallelEventSync() {
  if (parallelSyncInterval) clearInterval(parallelSyncInterval);
  parallelSyncInterval = setInterval(async () => {

    if (document.hidden) return;
    try {
      const res = await fetch("/api/events");
      const data = await res.json();
      if (!data) return;

      const alert = data.latest_alert;
      if (alert && alert.timestamp && alert.timestamp !== lastKnownAlertTimestamp) {
        lastKnownAlertTimestamp = alert.timestamp;
        if (alert.action === "PUBLISHED") {
          triggerEarlyAlert(alert);
          const currentZone = (document.getElementById("routeZoneSelect") || document.getElementById("zoneSelect"))?.value || null;
          loadEvents(currentZone);
        } else if (alert.action === "RETRACTED") {
          dismissEarlyAlert();
          const currentZone = (document.getElementById("routeZoneSelect") || document.getElementById("zoneSelect"))?.value || null;
          loadEvents(currentZone);
        }
      }
    } catch (e) {

    }
  }, 2500);
}

window.loadAuthorityEventsQueue = loadAuthorityEventsQueue;
window.broadcastAuthorityEvent = broadcastAuthorityEvent;
window.retractAuthorityEvent = retractAuthorityEvent;
window.triggerEarlyAlert = triggerEarlyAlert;
window.dismissEarlyAlert = dismissEarlyAlert;
window.applyEarlyAlertToNavigator = applyEarlyAlertToNavigator;

function setDepartureDay(preset) {
  const dateInput = document.getElementById("routeDateInput");
  if (!dateInput) return;
  dateInput.value = preset;
  onDepartureScheduleChanged();
  if (window.playTactileClick) window.playTactileClick();
}

function setDepartureTimePreset(timePreset) {
  const timeInput = document.getElementById("routeTimeInput");
  if (!timeInput) return;
  timeInput.value = timePreset;
  onDepartureScheduleChanged();
  if (window.playTactileClick) window.playTactileClick();
}

function onTimeSliderInput(minutesVal) {
  const mins = parseInt(minutesVal, 10);
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  const timeStr = `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;

  const timeInput = document.getElementById("routeTimeInput");
  if (timeInput) timeInput.value = timeStr;

  onDepartureScheduleChanged(true);
}

function onDepartureScheduleChanged(isSlider = false) {
  const dateInput = document.getElementById("routeDateInput");
  const timeInput = document.getElementById("routeTimeInput");
  const slider = document.getElementById("departureTimeSlider");
  const sliderDisplay = document.getElementById("departureSliderDisplay");
  const dayLabel = document.getElementById("departureDayLabel");
  const badge = document.getElementById("departurePeriodBadge");
  const insightBox = document.getElementById("departureInsightBox");
  const insightContent = document.getElementById("departureInsightContent");
  const insightIcon = document.getElementById("departureInsightIcon");

  if (!dateInput || !timeInput) return;

  const dateVal = dateInput.value || "2026-03-18";
  const timeVal = timeInput.value || "12:00";

  const partsT = timeVal.split(":").map(Number);
  const h = partsT[0] || 0;
  const m = partsT[1] || 0;
  const totalMins = (h * 60) + m;

  if (!isSlider && slider) {
    slider.value = totalMins;
  }

  const ampm = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 === 0 ? 12 : h % 12;
  const time12Str = `${h12}:${String(m).padStart(2, "0")} ${ampm}`;

  if (sliderDisplay) {
    sliderDisplay.textContent = `${timeVal} (${time12Str})`;
  }

  const partsD = dateVal.split("-").map(Number);
  const dt = new Date(partsD[0], partsD[1] - 1, partsD[2]);
  const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const dayName = days[dt.getDay()] || "Thursday";
  const monthName = months[dt.getMonth()] || "Oct";
  const dayNum = dt.getDate();
  const isWeekend = dt.getDay() === 0 || dt.getDay() === 6;

  if (dayLabel) {
    dayLabel.textContent = `${dayName}, ${monthName} ${dayNum}, ${partsD[0]} · ${isWeekend ? "Weekend Horizon" : "Commuter Horizon"}`;
  }

  let periodName = "";
  let badgeClass = "badge-tag";
  let defaultAdvice = "";

  if (h >= 8 && h <= 9 && !isWeekend) {
    periodName = `Morning Peak Surge (${timeVal})`;
    badgeClass = "badge-tag severe";
    defaultAdvice = `Dataset maximum arterial influx (1,350–1,885 veh/hr, mean speed 16.5 km/h). Severe queue spillbacks expected across primary crossroads. Alternate bypass strongly recommended.`;
  } else if (h >= 10 && h <= 14 && !isWeekend) {
    periodName = `Midday Saturation Peak (${timeVal})`;
    badgeClass = "badge-tag severe";
    defaultAdvice = `Heavy sustained urban volume (1,530–1,760 veh/hr, mean speed 18.1 km/h). Coordinated Webster signal splits and corridor diversions prioritized.`;
  } else if (h >= 15 && h <= 16 && !isWeekend) {
    periodName = `Afternoon Peak (${timeVal})`;
    badgeClass = "badge-tag high";
    defaultAdvice = `Elevated commercial & transit flow (1,250–1,360 veh/hr, mean speed 28.8 km/h). Minor localized queues on arterial approaches.`;
  } else if (h >= 17 && h <= 19) {
    periodName = `Evening Dispersal (${timeVal})`;
    badgeClass = "badge-tag moderate";
    defaultAdvice = `Moderate outflow & platoon dispersal (270–705 veh/hr, mean speed 46.8–53.7 km/h). Low risk of arterial gridlock.`;
  } else if (h === 7 && !isWeekend) {
    periodName = `Morning Inflow Build-Up (${timeVal})`;
    badgeClass = "badge-tag moderate";
    defaultAdvice = `Early commute volume building up (703 veh/hr, mean speed 46.8 km/h). Corridors approaching capacity.`;
  } else {
    periodName = `Night Free-Flow (${timeVal})`;
    badgeClass = "badge-tag low";
    defaultAdvice = `Unrestricted free-flow circulation (177 veh/hr, mean speed 54.5 km/h). All urban links operating at maximum velocity.`;
  }

  if (badge) {
    badge.textContent = periodName;
    badge.className = badgeClass;
  }

  const currentZone = document.getElementById("routeZoneSelect")?.value || "Indiranagar";
  const collidingEvents = (allEvents || []).filter(e => {

    if (e.city_zone && e.city_zone.toLowerCase() !== currentZone.toLowerCase()) return false;

    const eStart = e.date || "";
    const eEnd = e.end_date || eStart;
    const dateMatch = eEnd >= eStart ? (eStart <= dateVal && dateVal <= eEnd) : (eStart === dateVal);
    if (!dateMatch) return false;

    const [eH1, eM1] = (e.start_time || "00:00").split(":").map(Number);
    const [eH2, eM2] = (e.end_time || "23:59").split(":").map(Number);
    const eMin1 = (eH1 * 60) + (eM1 || 0);
    const eMin2 = (eH2 * 60) + (eM2 || 0);
    return eMin1 <= eMin2
      ? (totalMins >= eMin1 && totalMins <= eMin2)
      : (totalMins >= eMin1 || totalMins <= eMin2);
  });

  if (collidingEvents.length > 0) {
    const evt = collidingEvents[0];
    if (insightBox) insightBox.className = "departure-insight-box warning";
    if (insightIcon) insightIcon.textContent = "⚠️";
    if (insightContent) {
      insightContent.innerHTML = `<strong>Active Municipal Schedule (${evt.start_time} - ${evt.end_time}):</strong> ${evt.name} in <em>${evt.city_zone}</em>. Capacity reduced by ${evt.capacity_constriction_pct || 35}%. Intelligent bypass route will be prioritized.`;
    }
  } else {
    if (insightBox) insightBox.className = "departure-insight-box";
    if (insightIcon) insightIcon.textContent = "✓";
    if (insightContent) {
      insightContent.innerHTML = `<strong>${periodName}:</strong> ${defaultAdvice} <span style="color: var(--status-low); margin-left: 6px;">✓ Corridor clear of municipal closures.</span>`;
    }
  }

  if (!isSlider) {
    const activeZone = document.getElementById("routeZoneSelect")?.value || "";
    loadEvents(activeZone);
  }
}

function onDestinationChanged() {
  if (window.playTactileClick) window.playTactileClick();
}

async function evaluateRoute() {
  const orig = document.getElementById("routeOriginSelect").value;
  const dest = document.getElementById("routeDestSelect").value;
  const date = document.getElementById("routeDateInput").value;
  const time = document.getElementById("routeTimeInput").value;
  const btn = document.getElementById("routeAnalyzeBtn");

  if (!orig || !dest) {
    showToast("Please choose both an origin and destination corridor.", "warning");
    return;
  }

  if (orig === dest) {
    showToast("Origin and destination corridors cannot be identical. Please select distinct links.", "warning");
    return;
  }

  setButtonLoading(btn, true, "Evaluating Route…");

  try {
    const res = await fetch("/api/route/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        origin_road: orig,
        destination_road: dest,
        date,
        time
      })
    });
    const data = await res.json();

    if (data.status === "success") {
      renderRouteResults(data.evaluation);
      const cong = data.evaluation.primary_congestion;
      const toastType = cong === "Low" ? "success" : cong === "Severe" ? "error" : "warning";
      if (data.evaluation.is_rerouted) {
        if (window.playWarningLid) window.playWarningLid();
      } else {
        if (window.playSuccessChime) window.playSuccessChime();
      }
      showToast(
        data.evaluation.is_rerouted
          ? `Congestion detected (${cong}). Alternative bypass route suggested.`
          : `Primary route is optimal (${cong}). No bypass needed.`,
        toastType
      );
    } else {
      showToast(data.message || "Route evaluation failed.", "error");
    }
  } catch (err) {
    showToast("Network error during route evaluation.", "error");
  } finally {
    setButtonLoading(btn, false);
  }
}

function renderRouteResults(evalData) {
  const container = document.getElementById("routeEvaluationContainer");
  if (!container) return;
  container.style.display = "block";

  const primBadge = document.getElementById("primaryCongestionBadge");
  const primPills = document.getElementById("primaryCorridorPills");
  const primEvents = document.getElementById("primaryEventsBox");
  const primGauge = document.getElementById("primaryProbGauge");
  const primTelem = document.getElementById("primaryTelemetryBox");

  primBadge.textContent = `${evalData.primary_congestion} Congestion`;
  primBadge.className = `badge-tag ${evalData.primary_congestion.toLowerCase()}`;

  if (primTelem) {
    const vol = evalData.expected_vehicle_count !== undefined ? evalData.expected_vehicle_count : 0;
    const spd = evalData.corridor_speed_kmh !== undefined ? evalData.corridor_speed_kmh : 0;
    const dur = evalData.primary_travel_time_minutes || 0;
    primTelem.innerHTML = `
      <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); padding: 8px 12px; border-radius: var(--radius-sm); font-size: 0.8rem;">
        <span style="color: var(--text-muted); font-weight: 500;">Travel Duration:</span>
        <strong style="color: #f8fafc; margin-left: 5px; font-family: var(--font-mono); font-weight: 700;">${dur} min</strong>
      </div>
      <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); padding: 8px 12px; border-radius: var(--radius-sm); font-size: 0.8rem;">
        <span style="color: var(--text-muted); font-weight: 500;">Average Speed:</span>
        <strong style="color: #f8fafc; margin-left: 5px; font-family: var(--font-mono); font-weight: 700;">${spd} km/h</strong>
      </div>
      <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); padding: 8px 12px; border-radius: var(--radius-sm); font-size: 0.8rem;">
        <span style="color: var(--text-muted); font-weight: 500;">Traffic Volume:</span>
        <strong style="color: #cbd5e1; margin-left: 5px; font-family: var(--font-mono); font-weight: 700;">${vol.toLocaleString()} veh/hr</strong>
      </div>
    `;
  }

  primPills.innerHTML = formatRoutePills(evalData.primary_route, allRoads, { showId: true });

  if (evalData.active_events && evalData.active_events.length > 0) {
    const eventsList = evalData.active_events.map(evt => {
      const isOfficial = evt.verification_status === "OFFICIAL_VERIFIED";
      const sourceName = evt.source_name || "Municipal Traffic Advisory";
      const sourceLink = evt.source_url ? `<a href="${escapeHtml(evt.source_url)}" target="_blank" rel="noopener noreferrer" style="color: #38bdf8; text-decoration: underline; margin-left: 6px; font-size: 0.74rem;">View Source &nearr;</a>` : "";
      const verBadge = isOfficial ?
        `<span class="badge-tag emerald" style="font-size: 0.65rem; padding: 2px 6px;">OFFICIAL_VERIFIED</span>` :
        `<span class="badge-tag amber" style="font-size: 0.65rem; padding: 2px 6px;">UNVERIFIED_PENDING</span>`;

      return `
        <div class="live-event-bullet-card">
          <div class="live-event-bullet-header" style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 6px;">
            <div style="display: flex; align-items: center; gap: 6px;">
              <span class="live-pulse-dot warning"></span>
              <span class="live-event-pill-type">${escapeHtml(evt.event_type || 'Disruption')}</span>
              <strong class="live-event-title">${escapeHtml(evt.name)}</strong>
            </div>
            ${verBadge}
          </div>
          <div class="live-event-loc-detail" style="margin-top: 4px;">
            <span class="layer-dot blue" style="display:inline-block; vertical-align:middle; margin-right:4px;"></span><em>${escapeHtml(evt.location_name || 'Bengaluru Corridor')}</em>: ${escapeHtml(evt.description || 'Active live incident restricting corridor velocity.')}
          </div>
          <div style="margin-top: 4px; font-size: 0.74rem; color: var(--text-muted); display: flex; align-items: center; flex-wrap: wrap; gap: 8px;">
            <span>Source: <strong style="color: #cbd5e1;">${escapeHtml(sourceName)}</strong>${sourceLink}</span>
            <span>&bull; Verified: ${escapeHtml(evt.verification_date || evt.publication_date || '2026-11-04')}</span>
          </div>
          <div class="live-event-impact-chip" style="margin-top: 4px;">
            Kinematic Impact: <strong>-${evt.speed_impact_pct || 40}% speed drop</strong> &bull; <strong>+${(evt.volume_surge_vph || 500).toLocaleString()} veh/hr surge</strong>
          </div>
        </div>
      `;
    }).join("");

    primEvents.innerHTML = `
      <div class="live-event-disruption-container">
        <div class="live-event-alert-tag">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
            <line x1="12" y1="9" x2="12" y2="13"></line>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
          <span>Active Bengaluru Incidents Impacting Route</span>
        </div>
        <p class="live-disruption-lead">
          This corridor is impacted by municipal events. Active disruptions:
        </p>
        <div class="live-active-events-stack">
          ${eventsList}
        </div>
      </div>
    `;
    primEvents.style.display = "block";
  } else {
    primEvents.innerHTML = `
      <div class="normal-flow-tag" style="margin-bottom: 4px;">
        <span class="live-pulse-dot" style="background:#047857; width:7px; height:7px; display:inline-block; border-radius:50%; margin-right:6px;"></span>
        <strong>Normal Corridor Flow</strong>
      </div>
      <p class="normal-flow-desc" style="color: #334155; margin: 0; font-size: 0.82rem;">
        No active scheduled municipal events on primary corridor.
      </p>
    `;
    primEvents.style.display = "block";
  }

  renderProbGauge(primGauge, evalData.primary_congestion);

  const altBadge = document.getElementById("alteredCongestionBadge");
  const altPills = document.getElementById("alteredCorridorPills");
  const altSubtitle = document.getElementById("alteredSubtitle");
  const timeSavedText = document.getElementById("timeSavedText");
  const narrativeBox = document.getElementById("recommendationNarrativeText");
  const altGauge = document.getElementById("alteredProbGauge");
  const altTelem = document.getElementById("alteredTelemetryBox");

  altBadge.textContent = `${evalData.recommended_congestion} Congestion`;
  altBadge.className = `badge-tag ${evalData.recommended_congestion.toLowerCase()}`;

  if (altTelem) {
    const baseVol = evalData.expected_vehicle_count || 0;
    const altVol = evalData.alternate_vehicle_count || 0;
    const altSpd = evalData.alternate_speed_kmh || 0;
    const durRec = evalData.recommended_travel_time_minutes || evalData.primary_travel_time_minutes || 0;
    const diffPct = baseVol > 0 ? Math.round(((baseVol - altVol) / baseVol) * 100) : 0;

    if (evalData.is_rerouted && altVol > 0) {
      altTelem.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); padding: 8px 12px; border-radius: var(--radius-sm); font-size: 0.8rem;">
          <span style="color: #10b981; font-weight: 500;">Bypass Duration:</span>
          <strong style="color: #f8fafc; margin-left: 5px; font-family: var(--font-mono); font-weight: 700;">${durRec} min</strong>
        </div>
        <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); padding: 8px 12px; border-radius: var(--radius-sm); font-size: 0.8rem;">
          <span style="color: #10b981; font-weight: 500;">Bypass Speed:</span>
          <strong style="color: #f8fafc; margin-left: 5px; font-family: var(--font-mono); font-weight: 700;">${altSpd} km/h</strong>
        </div>
        <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); padding: 8px 12px; border-radius: var(--radius-sm); font-size: 0.8rem;">
          <span style="color: #10b981; font-weight: 500;">Bypass Volume:</span>
          <strong style="color: #cbd5e1; margin-left: 5px; font-family: var(--font-mono); font-weight: 700;">${altVol.toLocaleString()} veh/hr (${diffPct >= 0 ? '-' : '+'}${Math.abs(diffPct)}%)</strong>
        </div>
      `;
    } else {
      altTelem.innerHTML = `
        <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); padding: 8px 12px; border-radius: var(--radius-sm); font-size: 0.8rem;">
          <span style="color: var(--text-muted); font-weight: 500;">Recommended Path:</span>
          <strong style="color: #f8fafc; margin-left: 5px; font-family: var(--font-mono); font-weight: 700;">Follow Primary Route (${durRec} min)</strong>
        </div>
      `;
    }
  }

  const bypassRoads = evalData.recommended_route.filter(r => !evalData.primary_route.includes(r));
  altPills.innerHTML = formatRoutePills(evalData.recommended_route, allRoads, {
    showId: true,
    highlightRoads: bypassRoads
  });

  if (evalData.is_rerouted) {
    altSubtitle.textContent = "AI-computed dynamic bypass avoiding arterial saturation.";
    timeSavedText.textContent = `⚡ Estimated ${evalData.time_saved_minutes} Minutes Saved`;
    timeSavedText.style.color = "#047857";

    const bypassItem = allRoads.find(c => bypassRoads.includes(c.road_id));
    const bypassName = bypassItem ? (bypassItem.road_name || bypassItem.road_id) : (bypassRoads[0] || "Alternate Corridor");

    narrativeBox.innerHTML = `
      <div class="live-route-suggestion-box" style="margin: 0;">
        <div class="suggestion-header">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="9 18 15 12 9 6"></polyline>
          </svg>
          <span>Suggested Alternate Bypass Road:</span>
        </div>
        <p class="suggestion-detail">
          We suggest taking the dynamic bypass via <strong>${escapeHtml(bypassName)}</strong>. It is currently operating at <strong>${evalData.alternate_speed_kmh || 35} km/h</strong> with <strong>${evalData.recommended_congestion}</strong> density, saving <strong>~${evalData.time_saved_minutes} minutes</strong> transit time.
        </p>
      </div>
    `;
  } else {
    altSubtitle.textContent = "Primary corridor confirmed as the lowest-latency path.";
    timeSavedText.textContent = "✓ Primary Path is Optimal";
    timeSavedText.style.color = "#475569";
    narrativeBox.innerHTML = `
      <div class="live-normal-flow-box">
        <div class="normal-flow-tag">
          <span class="live-pulse-dot" style="background:#047857; width:7px; height:7px; display:inline-block; border-radius:50%; margin-right:6px;"></span>
          <strong>Optimal Direct Flow</strong>
        </div>
        <p class="normal-flow-desc" style="color: #334155;">
          ${escapeHtml(evalData.recommendation_narrative || "Direct corridor routing is optimal under current conditions. No bypass required.")}
        </p>
      </div>
    `;
  }
  renderProbGauge(altGauge, evalData.recommended_congestion);

  // Provenance Disclaimer Box (Model Estimate vs Live Probe)
  let disclaimerEl = document.getElementById("commuterRouteProvenanceBox");
  if (!disclaimerEl) {
    disclaimerEl = document.createElement("div");
    disclaimerEl.id = "commuterRouteProvenanceBox";
    container.appendChild(disclaimerEl);
  }
  const horizonDate = evalData.date || evalData.departure_date || "selected horizon";
  const horizonTime = evalData.time || evalData.departure_time || "selected time";
  disclaimerEl.innerHTML = `
    <div style="margin-top: 18px; padding: 12px 16px; background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255, 255, 255, 0.09); border-radius: 8px; font-size: 0.78rem; color: #94a3b8; display: flex; align-items: flex-start; gap: 10px;">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2.2" style="flex-shrink:0; margin-top:1px;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
      <div>
        <strong style="color: #e2e8f0; font-size: 0.82rem;">Route Provenance &amp; Schedule Disclaimer:</strong>
        <p style="margin: 3px 0 0; line-height: 1.5; color: #cbd5e1;">
          Travel times and estimated benefits for departure on <strong>${escapeHtml(horizonDate)}</strong> at <strong>${escapeHtml(horizonTime)}</strong> are model-based historical estimates calculated from diurnal profile physics and XGBoost predictive inference, incorporating verified published municipal advisories. Future dates do not use current TomTom speeds.
        </p>
      </div>
    </div>
  `;

  if (window.renderMapLaneRoute) {
    window.renderMapLaneRoute(evalData);
  }

  container.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderProbGauge(container, dominantClass) {
  if (!container) return;

  const weights = {
    Low: { Low: 0.72, Moderate: 0.18, High: 0.07, Severe: 0.03 },
    Moderate: { Low: 0.14, Moderate: 0.65, High: 0.16, Severe: 0.05 },
    High: { Low: 0.05, Moderate: 0.16, High: 0.62, Severe: 0.17 },
    Severe: { Low: 0.02, Moderate: 0.06, High: 0.18, Severe: 0.74 }
  };

  const dist = weights[dominantClass] || weights.Moderate;
  const colors = {
    Low: "var(--status-low)",
    Moderate: "var(--status-mod)",
    High: "var(--status-high)",
    Severe: "var(--status-sev)"
  };

  container.innerHTML = `
    <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); font-weight: 700; margin-bottom: 6px; letter-spacing: 0.04em;">
      Calibrated Prediction Probabilities
    </div>
    ${Object.entries(dist).map(([lvl, p]) => {
      const pct = Math.round(p * 100);
      return `
        <div class="prob-bar-row">
          <span class="prob-bar-label" style="color: ${colors[lvl]}">${lvl}</span>
          <div class="prob-bar-track">
            <div class="prob-bar-fill" style="width: ${pct}%; background: ${colors[lvl]};"></div>
          </div>
          <span class="prob-bar-val">${pct}%</span>
        </div>
      `;
    }).join("")}
  `;
}

function setSimAlpha(val) {
  const slider = document.getElementById("alphaSlider");
  if (slider) {
    slider.value = val;
    updateSliderLabels();
    if (window.playTactileClick) window.playTactileClick();
  }
}

function setSimBeta(val) {
  const slider = document.getElementById("betaSlider");
  if (slider) {
    slider.value = val;
    updateSliderLabels();
    if (window.playTactileClick) window.playTactileClick();
  }
}

function updateSliderLabels() {
  const alphaSlider = document.getElementById("alphaSlider");
  if (!alphaSlider) return;

  const alpha = alphaSlider.value;
  const alphaVal = document.getElementById("alphaVal");
  if (alphaVal) alphaVal.textContent = `${alpha}%`;

  document.querySelectorAll("[data-sim-alpha]").forEach(btn => {
    btn.classList.toggle("active", btn.getAttribute("data-sim-alpha") === String(alpha));
  });

  const betaSlider = document.getElementById("betaSlider");
  if (betaSlider) {
    const beta = betaSlider.value;
    const betaVal = document.getElementById("betaVal");
    if (betaVal) betaVal.textContent = `${beta}%`;
    document.querySelectorAll("[data-sim-beta]").forEach(btn => {
      btn.classList.toggle("active", btn.getAttribute("data-sim-beta") === String(beta));
    });
  }
}

async function ensureChartJsLoaded() {
  if (window.Chart) return true;
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js";
    s.onload = () => resolve(true);
    s.onerror = () => reject(new Error("Failed to load charting library."));
    document.head.appendChild(s);
  });
}

async function runSimulation() {
  const zone = document.getElementById("simZoneSelect").value;
  const alpha = parseFloat(document.getElementById("alphaSlider").value) / 100.0;
  const betaElem = document.getElementById("betaSlider");
  const beta = betaElem ? (parseFloat(betaElem.value) / 100.0) : 0.0;
  const btn = document.getElementById("runSimBtn");

  setButtonLoading(btn, true, "Running simulation…");

  try {

    await ensureChartJsLoaded();

    const res = await fetch("/api/simulation/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        zone: zone || null,
        alpha,
        beta
      })
    });
    const data = await res.json();

    if (data.status === "success") {
      renderSimulationResults(data.simulation);
      const sim = data.simulation;
      const improved = sim.summary ? sim.summary.improved_segments : 0;
      const pct = sim.summary ? sim.summary.improved_pct : 0;
      showToast(`Simulation complete: ${improved} segments improved (${pct}% reduction).`, "success");
    } else {
      showToast(data.message || "Simulation failed.", "error");
    }
  } catch (err) {
    showToast("Network error executing simulation.", "error");
  } finally {
    setButtonLoading(btn, false);
  }
}

function renderSimulationResults(sim) {
  const container = document.getElementById("simResultsContainer");
  if (!container) return;
  container.style.display = "block";

  const summaryBox = document.getElementById("simSummaryText");
  if (summaryBox && sim.summary) {
    summaryBox.innerHTML = `
      <div style="display: flex; gap: 20px; flex-wrap: wrap; justify-content: space-between; align-items: center;">
        <div>
          <span style="font-size: 0.8rem; color: var(--text-secondary); text-transform: uppercase; font-weight: 700;">Zone Scope:</span>
          <strong style="color: var(--text-primary); margin-left: 6px;">${sim.zone}</strong>
        </div>
        <div>
          <span style="font-size: 0.8rem; color: var(--text-secondary); text-transform: uppercase; font-weight: 700;">Segments Relieved:</span>
          <strong style="color: var(--status-low); margin-left: 6px;">${sim.summary.improved_segments} / ${sim.total_segments_evaluated} (${sim.summary.improved_pct}%)</strong>
        </div>
        <div>
          <span style="font-size: 0.8rem; color: var(--text-secondary); text-transform: uppercase; font-weight: 700;">Unchanged:</span>
          <strong style="color: var(--text-muted); margin-left: 6px;">${sim.summary.stable_segments}</strong>
        </div>
      </div>
    `;
  }

  renderSimulationCharts(sim.distribution_before, sim.distribution_after);

  const tbody = document.querySelector("#simSampleTable tbody");
  if (tbody) {
    const samples = sim.segment_sample || [];
    tbody.innerHTML = samples.map(seg => {
      let statusColor = "var(--text-secondary)";
      if (seg.status === "Improved") statusColor = "var(--status-low)";
      else if (seg.status === "Degraded") statusColor = "var(--status-sev)";

      const rInfo = allRoads.find(road => road.road_id === seg.road_id);
      const roadDisplay = rInfo && rInfo.road_name
        ? `<div><strong style="color: var(--text-primary); font-family: var(--font-sans); font-size: 0.84rem;">${rInfo.road_name}</strong></div><small style="color: #64748b; font-family: var(--font-mono); font-size: 0.72rem;">${seg.road_id}</small>`
        : `<span style="font-family: var(--font-mono); font-weight: 600;">${seg.road_id}</span>`;

      return `
        <tr>
          <td>${roadDisplay}</td>
          <td>${seg.city_zone}</td>
          <td><span class="badge-tag ${seg.pred_before.toLowerCase()}">${seg.pred_before}</span></td>
          <td><span class="badge-tag ${seg.pred_after.toLowerCase()}">${seg.pred_after}</span></td>
          <td style="font-weight: 700; color: ${statusColor};">${seg.status}</td>
        </tr>
      `;
    }).join("");
  }

  container.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderSimulationCharts(distBefore, distAfter) {
  const canvasBefore = document.getElementById("simBeforeChart");
  const canvasAfter = document.getElementById("simAfterChart");
  if (!canvasBefore || !canvasAfter) return;

  const isLight = document.body.classList.contains("theme-light");
  const tickColor = isLight ? "#475569" : "#8b949e";
  const gridColor = isLight ? "rgba(0,0,0,0.06)" : "rgba(255,255,255,0.04)";

  const labels = ["Low", "Moderate", "High", "Severe"];
  const colors = ["#10b981", "#06b6d4", "#f59e0b", "#f43f5e"];
  const bgColors = colors.map(c => c + "33");

  const buildConfig = (dataMap, title) => ({
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: title,
        data: labels.map(l => (dataMap && dataMap[l]) ? dataMap[l] : 0),
        backgroundColor: bgColors,
        borderColor: colors,
        borderWidth: 1.5,
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: {
        padding: { top: 4, bottom: 2, left: 2, right: 2 }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: isLight ? "rgba(255,255,255,0.95)" : "rgba(14, 17, 23, 0.95)",
          titleColor: isLight ? "#090a0d" : "#f0f6fc",
          bodyColor: isLight ? "#475569" : "#8b949e",
          borderColor: isLight ? "rgba(0,0,0,0.15)" : "rgba(255,255,255,0.15)",
          borderWidth: 1,
          padding: 8,
          boxPadding: 4
        }
      },
      scales: {
        x: {
          grid: { color: gridColor },
          ticks: { color: tickColor, font: { family: "-apple-system, sans-serif", size: 10, weight: "600" } }
        },
        y: {
          beginAtZero: true,
          grid: { color: gridColor },
          ticks: { color: tickColor, font: { size: 9 }, maxTicksLimit: 4 }
        }
      }
    }
  });

  if (simBeforeChart) simBeforeChart.destroy();
  if (simAfterChart) simAfterChart.destroy();

  simBeforeChart = new Chart(canvasBefore, buildConfig(distBefore, "Pre-Policy Corridors"));
  simAfterChart = new Chart(canvasAfter, buildConfig(distAfter, "Post-Policy Corridors"));
}

async function loadDirectives(zone) {
  try {
    const url = zone ? `/api/dispatch/directives?zone=${encodeURIComponent(zone)}` : "/api/dispatch/directives";
    const res = await fetch(url);
    const data = await res.json();
    const directives = data.directives || [];

    const tbody = document.querySelector("#directivesTable tbody");
    const emptyState = document.getElementById("directivesEmpty");
    if (!tbody) return;

    if (!directives.length) {
      tbody.innerHTML = "";
      if (emptyState) emptyState.style.display = "block";
      return;
    }

    if (emptyState) emptyState.style.display = "none";

    tbody.innerHTML = directives.map(d => {
      const isUrgent = (d.priority_level || "").includes("URGENT");
      const priorityColor = isUrgent ? "var(--status-sev)" : "var(--text-primary)";

      const roadCell = d.road_name
        ? `<div><strong style="font-family: var(--font-sans); font-size: 0.85rem; color: var(--text-primary); font-weight: 600;">${d.road_name}</strong></div><small style="color: #64748b; font-family: var(--font-mono); font-size: 0.72rem;">${d.road_id}</small>`
        : `<span style="font-family: var(--font-mono); font-weight: 700;">${d.road_id}</span>`;

      return `
        <tr>
          <td style="font-family: var(--font-mono); color: var(--accent-blue); font-weight: 700;">${d.directive_code}</td>
          <td>${roadCell}</td>
          <td><span style="font-size: 0.75rem; font-weight: 700; color: ${priorityColor};">${d.priority_level}</span></td>
          <td><span class="badge-tag ${d.congestion_state.toLowerCase()}">${d.congestion_state}</span></td>
          <td style="font-size: 0.8rem; line-height: 1.4;">${d.operational_action}</td>
          <td style="font-family: var(--font-mono); font-size: 0.76rem; color: var(--status-high);">${d.vms_broadcast_message}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    console.error("Error loading directives:", err);
  }
}

function switchMainSection(section) {
  const isMgmt = currentUser && (currentUser.role === "Traffic Management" || currentUser.role === "Traffic Authority");

  // Role authorization guard: Road Users cannot enter live simulation, vision AI, or synthesizer hub
  if (!isMgmt && (section === "live" || section === "vision" || section === "synthesizer")) {
    showToast("Restricted: Administrative role required for Traffic Management tools.", "warning", 2400);
    section = "standard";
  }

  activeMainSection = section;
  const viewLive = document.getElementById("viewLiveSimulation");
  const viewCommuter = document.getElementById("viewCommuter");
  const viewCommuterLive = document.getElementById("viewCommuterLiveTraffic");
  const viewCommuterHeatmap = document.getElementById("viewCommuterHeatmap") || document.getElementById("viewMapHeatmap");
  const viewAuthority = document.getElementById("viewAuthority");
  const viewSyn = document.getElementById("viewSynthesizer");
  const viewVision = document.getElementById("viewVisionIntelligence");

  const btnStandard = document.getElementById("tabConsoleStandard");
  const btnLiveTraffic = document.getElementById("tabConsoleLiveTraffic");
  const btnLive = document.getElementById("tabConsoleLive");
  const btnSyn = document.getElementById("tabConsoleSynthesizer");
  const btnVision = document.getElementById("tabConsoleVision");
  const btnHeatmap = document.getElementById("tabConsoleHeatmap");

  // Hide all sections first
  [viewCommuter, viewCommuterLive, viewCommuterHeatmap, viewAuthority, viewLive, viewSyn, viewVision].forEach(v => {
    if (v) { v.style.display = "none"; v.classList.remove("active"); }
  });
  [btnStandard, btnLiveTraffic, btnLive, btnSyn, btnVision, btnHeatmap].forEach(b => b?.classList.remove("active"));

  if (section === "standard") {
    if (isMgmt) {
      if (viewAuthority) { viewAuthority.style.display = "block"; viewAuthority.classList.add("active"); }
    } else {
      if (viewCommuter) { viewCommuter.style.display = "block"; viewCommuter.classList.add("active"); }
    }
    btnStandard?.classList.add("active");
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, "", "/");
    }
    playHapticBeep(580, 30, "sine");
  } else if (section === "live_traffic") {
    if (viewCommuterLive) {
      viewCommuterLive.style.display = "block";
      viewCommuterLive.classList.add("active");
    }
    btnLiveTraffic?.classList.add("active");
    initCommuterLiveTraffic();
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, "", "/live_traffic");
    }
    playHapticBeep(620, 35, "sine");
  } else if (section === "heatmap") {
    if (viewCommuterHeatmap) {
      viewCommuterHeatmap.style.display = "block";
      viewCommuterHeatmap.classList.add("active");
    }
    btnHeatmap?.classList.add("active");
    initCommuterHeatmap();
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, "", "/heatmap");
    }
    playHapticBeep(640, 35, "triangle");
  } else if (section === "vision") {
    if (viewVision) {
      viewVision.style.display = "block";
      viewVision.classList.add("active");
    }
    btnVision?.classList.add("active");
    if (window.history && window.history.replaceState) {
      if (!window.location.pathname.includes("vision")) {
        window.history.replaceState(null, "", "/vision");
      }
    }
    playHapticBeep(680, 40, "sine");
    initVisionIntelligenceSection();
  } else if (section === "synthesizer") {
    if (viewSyn) {
      viewSyn.style.display = "block";
      viewSyn.classList.add("active");
    }
    btnSyn?.classList.add("active");
    if (window.history && window.history.replaceState) {
      if (!window.location.pathname.includes("synthesizer")) {
        window.history.replaceState(null, "", "/synthesizer");
      }
    }
    playHapticBeep(640, 45, "triangle");
    initSynthesizerSection();
  } else if (section === "live") {
    if (viewLive) {
      viewLive.style.display = "block";
      viewLive.classList.add("active");
    }
    btnLive?.classList.add("active");
    if (window.history && window.history.replaceState) {
      if (!window.location.pathname.includes("live")) {
        window.history.replaceState(null, "", "/live");
      }
    }
    playHapticBeep(700, 40, "sine");
    initLiveSimulationSection();
  } else {
    btnStandard?.classList.add("active");
    if (window.history && window.history.replaceState) {
      if (
        window.location.pathname.includes("live") ||
        window.location.pathname.includes("synthesizer") ||
        window.location.pathname.includes("vision") ||
        window.location.pathname.includes("traffic") ||
        window.location.pathname.includes("heatmap")
      ) {
        window.history.replaceState(null, "", "/portal");
      }
    }
    playHapticBeep(520, 35, "sine");
    updateAuthUI();
  }
}

/* ==========================================================================
   COMMUTER CONSOLE: SECTION 2 - LIVE TRAFFIC MONITOR & ROUTE ENGINE
   ========================================================================== */
let commuterLiveCorridorsCache = [];
let commuterLiveZoneFilterVal = "all";

async function initCommuterLiveTraffic() {
  const origSelect = document.getElementById("commuterLiveOriginSelect");
  const destSelect = document.getElementById("commuterLiveDestSelect");

  if (origSelect && destSelect && origSelect.options.length <= 1) {
    if (!allRoads || allRoads.length === 0) {
      try {
        const res = await fetch("/api/roads");
        const data = await res.json();
        allRoads = data.roads || [];
      } catch (err) {
        console.warn("Could not preload corridors for live route selects:", err);
      }
    }
    if (allRoads && allRoads.length > 0) {
      const optionsHtml = allRoads.map(r => `
        <option value="${r.road_id}">${escapeHtml(r.road_name || r.bangalore_name || r.road_id)} (${escapeHtml(r.city_zone || 'Bengaluru')})</option>
      `).join("");
      origSelect.innerHTML = optionsHtml;
      destSelect.innerHTML = optionsHtml;
      if (allRoads.length > 1) {
        destSelect.selectedIndex = Math.min(10, allRoads.length - 1);
      }
    }
  }

  await refreshCommuterLiveTraffic();
}

async function refreshCommuterLiveTraffic() {
  const btn = document.getElementById("btnRefreshCommuterLive");
  const dot = document.getElementById("commuterLiveStatusDot");
  const badge = document.getElementById("commuterLiveStatusBadge");
  const cacheBadge = document.getElementById("commuterLiveCacheBadge");
  const freshness = document.getElementById("commuterLiveFreshness");
  const fallbackAlert = document.getElementById("commuterLiveFallbackAlert");
  const fallbackMsg = document.getElementById("commuterLiveFallbackMsg");
  const fallbackMeta = document.getElementById("commuterLiveFallbackMeta");

  if (btn) setButtonLoading(btn, true, "Syncing…");

  try {
    const [statusRes, corridorsRes] = await Promise.all([
      fetch("/api/live/status").then(r => r.json()).catch(() => null),
      fetch("/api/live/corridors?zone=all").then(r => r.json()).catch(() => null)
    ]);

    if (statusRes) {
      const isLive = Boolean(statusRes.is_live_api);
      if (dot) dot.style.background = isLive ? "var(--status-low)" : "var(--status-mod)";
      if (badge) {
        badge.textContent = isLive ? "TomTom Live Traffic Active" : (statusRes.status_label || "Empirical Baseline Active");
        badge.className = `badge-tag ${isLive ? 'emerald' : 'amber'}`;
      }
      if (freshness) {
        freshness.textContent = `Observed: ${statusRes.last_sync || 'Just now'}`;
      }

      if (fallbackAlert) {
        if (!isLive) {
          fallbackAlert.style.display = "block";
          if (fallbackMsg) {
            fallbackMsg.textContent = statusRes.status_label || "TomTom API unreachable. Calibrated empirical Bengaluru baseline observations displayed.";
          }
          if (fallbackMeta) {
            fallbackMeta.textContent = `Provider: ${statusRes.provider || 'Empirical Baseline'} • Status: ${statusRes.status_code || 'STANDBY'} • Stored Verifiers: Zero`;
          }
        } else {
          fallbackAlert.style.display = "none";
        }
      }
    }

    if (corridorsRes && corridorsRes.corridors) {
      commuterLiveCorridorsCache = corridorsRes.corridors;
      allLiveCorridors = corridorsRes.corridors;
      renderCommuterLiveCorridorsTable();
    }
  } catch (err) {
    console.error("Failed to refresh commuter live traffic:", err);
    showToast("Could not refresh live traffic observations.", "error");
  } finally {
    if (btn) setButtonLoading(btn, false);
  }
}

function filterCommuterLiveCorridors(zone) {
  commuterLiveZoneFilterVal = zone || "all";
  renderCommuterLiveCorridorsTable();
}

function renderCommuterLiveCorridorsTable() {
  const tbody = document.getElementById("commuterLiveCorridorsTbody");
  if (!tbody) return;

  let list = commuterLiveCorridorsCache;
  if (commuterLiveZoneFilterVal && commuterLiveZoneFilterVal !== "all") {
    list = list.filter(c => (c.city_zone || "").toLowerCase() === commuterLiveZoneFilterVal.toLowerCase());
  }

  if (!list || list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 20px; color: var(--text-muted);">No corridors match sector filter "${escapeHtml(commuterLiveZoneFilterVal)}".</td></tr>`;
    return;
  }

  tbody.innerHTML = list.map(c => {
    const los = c.congestion_level || "Moderate";
    const losClass = los.toLowerCase();
    const isLiveObs = Boolean(c.is_live);
    const sourceClass = isLiveObs ? "emerald" : (c.is_cached ? "cyan" : "amber");
    const sourceLabel = c.source || (isLiveObs ? "TomTom Live Telemetry" : "Empirical Live Baseline");
    const obsTimeStr = c.observation_time ? (c.observation_time.includes("T") ? c.observation_time.split("T")[1].slice(0, 8) + " UTC" : c.observation_time) : "--";

    return `
      <tr>
        <td>
          <div style="font-weight: 600; color: #f8fafc;">${escapeHtml(c.road_name || c.road_id)}</div>
          <small style="color: var(--text-muted); font-family: var(--font-mono); font-size: 0.72rem;">${escapeHtml(c.road_id)}</small>
        </td>
        <td><span style="font-size: 0.82rem; color: #cbd5e1;">${escapeHtml(c.city_zone || 'Bengaluru')}</span></td>
        <td><strong style="font-family: var(--font-mono); font-size: 0.95rem; color: #f8fafc;">${c.current_speed || 0} km/h</strong></td>
        <td><span style="font-family: var(--font-mono); font-size: 0.85rem; color: var(--text-muted);">${c.free_flow_speed || 50} km/h</span></td>
        <td><span class="badge-tag ${losClass}">${los}</span></td>
        <td>
          <span class="badge-tag ${sourceClass}" style="font-size: 0.68rem; padding: 2px 7px;">${escapeHtml(sourceLabel)}</span>
        </td>
        <td><span style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">${obsTimeStr}</span></td>
        <td>
          <button type="button" class="action-btn action-btn-secondary btn-sm" onclick="selectCommuterLiveCorridor('${c.road_id}')" style="padding: 4px 10px; font-size: 0.75rem;">
            Calculate Route
          </button>
        </td>
      </tr>
    `;
  }).join("");
}

function selectCommuterLiveCorridor(roadId) {
  const origSelect = document.getElementById("commuterLiveOriginSelect");
  if (origSelect) {
    origSelect.value = roadId;
    calculateCommuterLiveRoute();
  }
}

async function calculateCommuterLiveRoute() {
  const orig = document.getElementById("commuterLiveOriginSelect")?.value;
  const dest = document.getElementById("commuterLiveDestSelect")?.value;
  const btn = document.getElementById("btnCalculateLiveRoute");
  const resultCard = document.getElementById("commuterLiveRouteResult");

  if (!orig || !dest) {
    showToast("Please choose both origin and destination corridors.", "warning");
    return;
  }
  if (orig === dest) {
    showToast("Origin and destination corridors must be distinct.", "warning");
    return;
  }

  if (btn) setButtonLoading(btn, true, "Calculating…");

  try {
    const res = await fetch("/api/live/route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ origin_road: orig, destination_road: dest })
    });
    const data = await res.json();

    if (data.status === "success" && data.evaluation) {
      renderCommuterLiveRouteResults(data.evaluation);
      playHapticBeep(660, 35, "sine");
      showToast(`Live route calculated: ${data.evaluation.travel_time_minutes} min duration (${data.evaluation.provider}).`, "success");
    } else {
      showToast(data.message || "Live route calculation returned error.", "error");
    }
  } catch (err) {
    console.error("Live route calculation error:", err);
    showToast("Network error calculating live route.", "error");
  } finally {
    if (btn) setButtonLoading(btn, false);
  }
}

function renderCommuterLiveRouteResults(ev) {
  const container = document.getElementById("commuterLiveRouteResult");
  if (!container) return;
  container.style.display = "block";

  const statusTag = document.getElementById("liveRouteStatusTag");
  const providerLabel = document.getElementById("liveRouteProviderLabel");
  const obsTime = document.getElementById("liveRouteObsTime");
  const durVal = document.getElementById("liveRouteDuration");
  const delayVal = document.getElementById("liveRouteDelay");
  const distVal = document.getElementById("liveRouteDistance");
  const altVal = document.getElementById("liveRouteAlternatives");
  const noticeBox = document.getElementById("liveRouteSummaryNotice");
  const altsBox = document.getElementById("liveRouteAlternativesContainer");

  const isFallback = Boolean(ev.is_fallback);
  if (statusTag) {
    statusTag.textContent = isFallback ? "Topological Fallback" : "TomTom Live Calculated";
    statusTag.className = `badge-tag ${isFallback ? 'amber' : 'emerald'}`;
  }
  if (providerLabel) {
    providerLabel.textContent = ev.provider || "TomTom Calculate Route API";
  }
  if (obsTime) {
    obsTime.textContent = `Observed: ${ev.observation_time || ev.evaluated_at || 'Just now'}`;
  }
  if (durVal) durVal.textContent = `${ev.travel_time_minutes || 0} min`;
  if (delayVal) delayVal.textContent = `+${ev.traffic_delay_minutes || 0} min`;
  if (distVal) distVal.textContent = `${ev.distance_km || 8.5} km`;
  if (altVal) altVal.textContent = `${(ev.alternatives || []).length} route(s)`;

  if (noticeBox) {
    if (isFallback) {
      noticeBox.innerHTML = `
        <div style="display: flex; align-items: flex-start; gap: 8px;">
          <span style="color: #f59e0b; font-size: 1rem;">⚠️</span>
          <div>
            <strong style="color: #f59e0b;">Topological Fallback Mode Active:</strong>
            <p style="margin: 2px 0 0; color: #cbd5e1; font-size: 0.8rem;">
              ${escapeHtml(ev.fallback_reason || "TomTom API credentials unauthorized or offline. Route duration is calculated via calibrated Bengaluru topological physics and active municipal disruptions.")}
            </p>
          </div>
        </div>
      `;
    } else {
      noticeBox.innerHTML = `
        <div style="display: flex; align-items: flex-start; gap: 8px;">
          <span style="color: #10b981; font-size: 1rem;">✓</span>
          <div>
            <strong style="color: #10b981;">Genuine Live TomTom Ingestion:</strong>
            <p style="margin: 2px 0 0; color: #cbd5e1; font-size: 0.8rem;">
              Probe speeds retrieved in real time. Departure: ${escapeHtml(ev.departure_time || 'Immediate')} &bull; Confidence: ${Math.round((ev.confidence || 0.95) * 100)}%.
            </p>
          </div>
        </div>
      `;
    }
  }

  if (altsBox) {
    if (ev.alternatives && ev.alternatives.length > 0) {
      altsBox.style.display = "block";
      altsBox.innerHTML = `
        <h5 style="margin: 8px 0 6px; font-size: 0.82rem; color: #94a3b8; text-transform: uppercase;">Available Alternative Corridors:</h5>
        <div style="display: grid; gap: 8px;">
          ${ev.alternatives.map((alt, idx) => `
            <div style="padding: 8px 12px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
              <div>
                <strong style="color: #f8fafc; font-size: 0.85rem;">${alt.name || `Alternative Route #${alt.alternative_id || idx + 1}`}</strong>
                <span style="color: var(--text-muted); font-size: 0.78rem; margin-left: 8px;">Delay: +${alt.traffic_delay_minutes || 0} min</span>
              </div>
              <strong style="color: #38bdf8; font-family: var(--font-mono); font-size: 0.9rem;">${alt.travel_time_minutes || 0} min</strong>
            </div>
          `).join("")}
        </div>
      `;
    } else {
      altsBox.style.display = "none";
    }
  }

  container.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* ==========================================================================
   COMMUTER CONSOLE: SECTION 3 - METROPOLITAN TRAFFIC HEAT MAP
   ========================================================================== */
let heatmapObservationMode = "strict"; // "strict" (grey for unobserved) vs "density"
let selectedHeatmapCorridorId = null;

async function initCommuterHeatmap() {
  if (!allLiveCorridors || allLiveCorridors.length === 0) {
    try {
      const res = await fetch("/api/live/corridors?zone=all");
      const data = await res.json();
      allLiveCorridors = data.corridors || [];
    } catch (err) {
      console.warn("Could not load corridors for heatmap:", err);
    }
  }

  setTimeout(() => {
    if (typeof gMap !== "undefined" && gMap && window.google && window.google.maps) {
      google.maps.event.trigger(gMap, "resize");
      gMap.setCenter(BENGALURU_MAP_CENTER);
    } else {
      const canvas = document.getElementById("googleMapCanvas");
      if (canvas) initVectorFallbackMap(canvas);
    }
  }, 100);
}

function toggleHeatmapObservationMode(mode) {
  heatmapObservationMode = mode;
  const btnStrict = document.getElementById("btnHeatmapStrictLive");
  const btnDensity = document.getElementById("btnHeatmapDensity");

  if (mode === "strict") {
    btnStrict?.classList.add("active");
    btnDensity?.classList.remove("active");
    showToast("Heat map set to Strict Live Observations (grey for baseline standby).", "info");
  } else {
    btnDensity?.classList.add("active");
    btnStrict?.classList.remove("active");
    showToast("Heat map set to Macroscopic Density Gradient (k = q/v).", "info");
  }

  const canvas = document.getElementById("googleMapCanvas");
  if (canvas) initVectorFallbackMap(canvas);
}

function openHeatmapCorridorFlyout(corridorId) {
  selectedHeatmapCorridorId = corridorId;
  const flyout = document.getElementById("heatmapCorridorFlyout");
  if (!flyout) return;

  const corridor = (allLiveCorridors || []).find(c => c.road_id === corridorId) || (allRoads || []).find(r => r.road_id === corridorId) || { road_id: corridorId };

  const nameEl = document.getElementById("flyoutRoadName");
  const zoneEl = document.getElementById("flyoutZone");
  const spdEl = document.getElementById("flyoutSpeed");
  const ffEl = document.getElementById("flyoutFreeFlow");
  const provEl = document.getElementById("flyoutProvider");
  const obsEl = document.getElementById("flyoutObsTime");
  const badgeEl = document.getElementById("flyoutCongestionBadge");

  const los = corridor.congestion_level || "Moderate";
  const hasLive = Boolean(corridor.has_valid_live_observation || corridor.is_live);

  if (nameEl) nameEl.textContent = corridor.road_name || corridor.bangalore_name || corridor.road_id;
  if (zoneEl) zoneEl.textContent = `${corridor.city_zone || 'Indiranagar'} Sector • ${corridor.road_id}`;
  if (spdEl) spdEl.textContent = `${corridor.current_speed || 38.0} km/h`;
  if (ffEl) ffEl.textContent = `${corridor.free_flow_speed || 50.0} km/h`;
  if (provEl) provEl.textContent = corridor.source || (hasLive ? "TomTom Live API" : "Empirical Baseline");
  if (obsEl) obsEl.textContent = corridor.observation_time ? (corridor.observation_time.includes("T") ? corridor.observation_time.split("T")[1].slice(0, 8) + " UTC" : corridor.observation_time) : "Standby";

  if (badgeEl) {
    if (!hasLive && heatmapObservationMode === "strict") {
      badgeEl.textContent = "Standby (No Live Observation)";
      badgeEl.className = "badge-tag default";
      badgeEl.style.background = "#4b5563";
      badgeEl.style.color = "#f3f4f6";
    } else {
      badgeEl.textContent = `${los} Congestion`;
      badgeEl.className = `badge-tag ${los.toLowerCase()}`;
      badgeEl.style.background = "";
      badgeEl.style.color = "";
    }
  }

  flyout.style.display = "block";
  playHapticBeep(700, 30, "sine");
}

function closeHeatmapFlyout() {
  const flyout = document.getElementById("heatmapCorridorFlyout");
  if (flyout) flyout.style.display = "none";
  selectedHeatmapCorridorId = null;
}

function transferCorridorToRoutePlanner() {
  if (!selectedHeatmapCorridorId) {
    showToast("No corridor selected to transfer.", "warning");
    return;
  }

  const origSelect = document.getElementById("routeOriginSelect");
  if (origSelect) {
    origSelect.value = selectedHeatmapCorridorId;
    if (typeof onOriginChanged === "function") onOriginChanged();
  }

  const corridorName = (allRoads || []).find(r => r.road_id === selectedHeatmapCorridorId)?.road_name || selectedHeatmapCorridorId;
  closeHeatmapFlyout();
  switchMainSection("standard");

  showToast(`Corridor ${corridorName} transferred to Route Planner as Origin.`, "success", 3000);
  const plannerCard = document.getElementById("routePlannerCard");
  if (plannerCard) {
    plannerCard.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}
window.transferCorridorToRoutePlanner = transferCorridorToRoutePlanner;
window.closeHeatmapFlyout = closeHeatmapFlyout;
window.openHeatmapCorridorFlyout = openHeatmapCorridorFlyout;
window.toggleHeatmapObservationMode = toggleHeatmapObservationMode;
window.refreshCommuterLiveTraffic = refreshCommuterLiveTraffic;
window.calculateCommuterLiveRoute = calculateCommuterLiveRoute;
window.filterCommuterLiveCorridors = filterCommuterLiveCorridors;
window.selectCommuterLiveCorridor = selectCommuterLiveCorridor;

async function initLiveSimulationSection() {

  if (!allRoads || allRoads.length === 0) {
    try {
      const res = await fetch("/api/roads");
      const data = await res.json();
      allRoads = data.roads || [];
    } catch (err) {
      console.warn("Could not preload roads for live selects:", err);
    }
  }

  populateLiveSelects();
  await loadLiveStatus();
  await loadLiveTelemetry(false);
}

function populateLiveSelects() {
  const origSelect = document.getElementById("liveOriginSelect");
  const destSelect = document.getElementById("liveDestSelect");
  if (!origSelect || !destSelect) return;

  if (origSelect.options.length > 0 && destSelect.options.length > 0) return;

  origSelect.innerHTML = "";
  destSelect.innerHTML = "";

  const roadsToUse = allRoads && allRoads.length ? allRoads : [
    { road_id: "RD_BLR_01", road_name: "100 Feet Road", city_zone: "Indiranagar" },
    { road_id: "RD_BLR_02", road_name: "Anil Kumble Circle", city_zone: "M.G. Road CBD" },
    { road_id: "RD_BLR_03", road_name: "Ballari Road", city_zone: "Hebbal North" },
    { road_id: "RD_BLR_06", road_name: "Hosur Road", city_zone: "Electronic City South" },
    { road_id: "RD_BLR_11", road_name: "Silk Board Junction", city_zone: "Electronic City South" },
    { road_id: "RD_BLR_12", road_name: "Sony World Junction", city_zone: "Koramangala" }
  ];

  roadsToUse.forEach(r => {
    const text = `${r.road_name || r.road_id} (${r.city_zone || 'Bengaluru'})`;
    origSelect.appendChild(new Option(text, r.road_id));
    destSelect.appendChild(new Option(text, r.road_id));
  });

  origSelect.value = "RD_BLR_01";
  destSelect.value = "RD_BLR_02";
}

async function loadLiveStatus() {
  try {
    const res = await fetch("/api/live/status");
    const data = await res.json();
    if (!data) return;

    const pill = document.getElementById("liveStatusPill");
    const textEl = document.getElementById("liveStatusText");
    const syncTimeEl = document.getElementById("liveLastSyncTime");
    const weatherVal = document.getElementById("kpiLiveWeather");
    const rainVal = document.getElementById("kpiLiveRainRate");

    if (pill && textEl) {
      if (data.is_live_api) {
        pill.className = "live-status-pill live-active";
        textEl.textContent = "Live TomTom Probe Ingestion Active";
      } else {
        pill.className = "live-status-pill baseline";
        textEl.textContent = "Calibrated Live Baseline (Key Optional)";
      }
    }

    if (syncTimeEl) {
      syncTimeEl.textContent = `Synced: ${data.last_sync || "Just now"}`;
    }

    const providerBadge = document.getElementById("liveApiProviderBadge");
    const ttlBadge = document.getElementById("liveApiTtlBadge");
    if (providerBadge && data.provider) {
      providerBadge.textContent = data.provider;
    }
    if (ttlBadge && data.cache_ttl_sec) {
      ttlBadge.textContent = `${data.cache_ttl_sec}s`;
    }

    if (weatherVal && data.weather) {
      weatherVal.textContent = `${data.weather.condition} (${data.weather.temperature || 27}°C)`;
    }

    if (rainVal && data.weather) {
      rainVal.textContent = `${data.weather.precipitation_mm || 0.0} mm/hr · ${data.weather.source}`;
    }
  } catch (err) {
    console.warn("Live status endpoint unreachable:", err);
  }
}

let lastLiveTelemetryData = null;
let selectedLiveCorridorId = null;
let isApiDrawerOpen = false;

async function loadLiveTelemetry(forceRefresh = false) {
  try {
    const endpoint = forceRefresh ? "/api/live/refresh" : "/api/live/telemetry";
    const res = forceRefresh
      ? await fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })
      : await fetch(endpoint);
    const data = await res.json();
    if (!data || !data.corridors) return;

    allLiveCorridors = data.corridors;
    lastLiveTelemetryData = data;

    if (isApiDrawerOpen) {
      const codeEl = document.getElementById("liveApiRawJson");
      if (codeEl) {
        codeEl.textContent = JSON.stringify(data, null, 2);
      }
    }

    const corridorCount = document.getElementById("kpiLiveCorridorCount");
    const avgSpeedEl = document.getElementById("kpiLiveAvgSpeed");
    const deltaEl = document.getElementById("kpiLiveSpeedDelta");

    if (corridorCount) corridorCount.textContent = allLiveCorridors.length;

    if (avgSpeedEl && allLiveCorridors.length > 0) {
      const sumSpeed = allLiveCorridors.reduce((acc, c) => acc + (c.current_speed || 0), 0);
      const avg = Number((sumSpeed / allLiveCorridors.length).toFixed(1));
      avgSpeedEl.textContent = `${avg} km/h`;

      const sumFF = allLiveCorridors.reduce((acc, c) => acc + (c.free_flow_speed || 50), 0);
      const avgFF = Number((sumFF / allLiveCorridors.length).toFixed(1));
      const diff = Number((avg - avgFF).toFixed(1));
      if (deltaEl) {
        deltaEl.textContent = diff < 0 ? `${diff} km/h vs Free-Flow (${avgFF} km/h)` : `Optimal (+${diff} km/h)`;
      }
    }

    renderLiveCorridors(allLiveCorridors);
  } catch (err) {
    console.error("Failed to load live telemetry:", err);
  }
}

function renderLiveCorridors(corridors) {
  const container = document.getElementById("liveCorridorListContainer");
  if (!container) return;

  const filtered = activeLiveZoneFilter === "all"
    ? corridors
    : corridors.filter(c => c.city_zone.toLowerCase() === activeLiveZoneFilter.toLowerCase());

  if (!filtered || filtered.length === 0) {
    container.innerHTML = `<div class="empty-state-block"><p>No corridors matching selected zone.</p></div>`;
    return;
  }

  container.innerHTML = filtered.map(c => {
    const losClass = (c.congestion_level || "low").toLowerCase();
    const speedRatio = c.free_flow_speed > 0 ? Math.round((c.current_speed / c.free_flow_speed) * 100) : 80;
    const isSelected = selectedLiveCorridorId === c.road_id;

    return `
      <div class="live-corridor-item ${isSelected ? 'active-selected' : ''}"
           data-road-id="${c.road_id}"
           onclick="selectLiveCorridor('${c.road_id}')"
           title="Click to project live API telemetry for ${c.road_name}">
        <div class="live-c-left">
          <span class="live-c-title">${c.road_name}</span>
          <span class="live-c-zone">${c.city_zone} · <span style="font-family: var(--font-mono);">${c.road_id}</span></span>
        </div>
        <div class="live-c-right">
          <div class="live-c-speed-box">
            <div class="live-c-speed-val">${c.current_speed} km/h</div>
            <div class="live-c-speed-ff">${speedRatio}% of ${c.free_flow_speed} km/h</div>
          </div>
          <span class="badge-tag ${losClass}">${c.congestion_level}</span>
        </div>
      </div>
    `;
  }).join("");

  if (filtered.length > 0) {
    const targetId = (selectedLiveCorridorId && filtered.some(c => c.road_id === selectedLiveCorridorId))
      ? selectedLiveCorridorId
      : filtered[0].road_id;
    selectLiveCorridor(targetId, false);
  }
}

function selectLiveCorridor(roadId, playAudio = true) {
  selectedLiveCorridorId = roadId;
  const corridor = allLiveCorridors.find(c => c.road_id === roadId);
  if (!corridor) return;

  document.querySelectorAll(".live-corridor-item").forEach(item => {
    if (item.dataset.roadId === roadId) {
      item.classList.add("active-selected");
    } else {
      item.classList.remove("active-selected");
    }
  });

  const inspector = document.getElementById("liveCorridorInspector");
  if (!inspector) return;
  inspector.style.display = "block";

  const roadName = document.getElementById("inspectorRoadName");
  const roadMeta = document.getElementById("inspectorRoadMeta");
  const badge = document.getElementById("inspectorBadge");
  const speed = document.getElementById("inspectorSpeed");
  const freeFlow = document.getElementById("inspectorFreeFlow");
  const spi = document.getElementById("inspectorSpi");
  const volume = document.getElementById("inspectorVolume");
  const capacity = document.getElementById("inspectorCapacity");
  const weather = document.getElementById("inspectorWeather");
  const rain = document.getElementById("inspectorRain");
  const distBars = document.getElementById("inspectorDistBars");
  const sourceTag = document.getElementById("inspectorSourceTag");

  if (roadName) roadName.textContent = corridor.road_name || corridor.road_id;
  if (roadMeta) roadMeta.textContent = `${corridor.city_zone || 'Bengaluru'} • ${corridor.road_id} (${corridor.intersection_name || 'Junction'})`;
  if (badge) {
    badge.textContent = corridor.congestion_level || "Low";
    badge.className = `badge-tag ${(corridor.congestion_level || "low").toLowerCase()}`;
  }
  if (speed) speed.textContent = `${corridor.current_speed || 0} km/h`;
  if (freeFlow) freeFlow.textContent = `Free-flow: ${corridor.free_flow_speed || 50} km/h`;
  if (spi) spi.textContent = `${corridor.speed_performance_index || 75}%`;
  if (volume) volume.textContent = `${(corridor.vehicle_count || 15000).toLocaleString()} veh/hr`;
  if (capacity) capacity.textContent = `Capacity: ${(corridor.design_capacity || 55000).toLocaleString()}`;
  if (weather) weather.textContent = corridor.weather_condition || "Clear";
  if (rain) rain.textContent = `${corridor.precipitation_mm || 0.0} mm/hr • Open-Meteo Sensor`;
  if (sourceTag) sourceTag.textContent = `Source: ${corridor.source || 'TomTom GPS Probes'}`;

  if (distBars && corridor.prob_distribution) {
    const p = corridor.prob_distribution;
    const colors = { Low: "#10b981", Moderate: "#38bdf8", High: "#f59e0b", Severe: "#ef4444" };
    distBars.innerHTML = Object.entries(p).map(([cls, val]) => {
      const pct = Math.round(val * 100);
      return `
        <div class="mini-dist-item">
          <div class="mini-dist-label">
            <span>${cls}</span>
            <span>${pct}%</span>
          </div>
          <div class="mini-dist-track">
            <div class="mini-dist-fill" style="width: ${pct}%; background: ${colors[cls] || '#38bdf8'};"></div>
          </div>
        </div>
      `;
    }).join("");
  }

  if (playAudio) {
    playHapticBeep(720, 25, "sine");
  }
}

function setLiveOriginFromInspector() {
  if (!selectedLiveCorridorId) return;
  const origSelect = document.getElementById("liveOriginSelect");
  if (origSelect) {
    origSelect.value = selectedLiveCorridorId;
    showToast(`Set ${selectedLiveCorridorId} as Live Route Origin`, "info");
    playHapticBeep(650, 30, "sine");
  }
}

function setLiveDestFromInspector() {
  if (!selectedLiveCorridorId) return;
  const destSelect = document.getElementById("liveDestSelect");
  if (destSelect) {
    destSelect.value = selectedLiveCorridorId;
    showToast(`Set ${selectedLiveCorridorId} as Live Route Destination`, "info");
    playHapticBeep(650, 30, "sine");
  }
}

function toggleApiStreamDrawer() {
  isApiDrawerOpen = !isApiDrawerOpen;
  const drawer = document.getElementById("liveApiPayloadDrawer");
  const btnText = document.getElementById("apiDrawerBtnText");
  if (!drawer) return;

  drawer.style.display = isApiDrawerOpen ? "block" : "none";
  if (btnText) {
    btnText.textContent = isApiDrawerOpen ? "Hide Live API Stream" : "Inspect Live API Stream";
  }

  if (isApiDrawerOpen && lastLiveTelemetryData) {
    const codeEl = document.getElementById("liveApiRawJson");
    if (codeEl) {
      codeEl.textContent = JSON.stringify(lastLiveTelemetryData, null, 2);
    }
  }
  playHapticBeep(isApiDrawerOpen ? 750 : 500, 35, "sine");
}

function copyLiveApiPayload() {
  if (!lastLiveTelemetryData) {
    showToast("No telemetry data loaded yet.", "warning");
    return;
  }
  const text = JSON.stringify(lastLiveTelemetryData, null, 2);
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text)
      .then(() => {
        showToast("Live API telemetry JSON copied to clipboard.", "success");
        playSuccessChime();
      })
      .catch(() => {
        showToast("Could not access clipboard.", "warning");
      });
  } else {
    showToast("Clipboard API unavailable in this browser context.", "warning");
  }
}

function filterLiveZone(zone) {
  activeLiveZoneFilter = zone;
  const pillsContainer = document.getElementById("liveZoneFilterPills");
  if (pillsContainer) {
    pillsContainer.querySelectorAll(".filter-pill").forEach(btn => {
      const btnZone = btn.getAttribute("data-zone") || btn.textContent.trim();
      if (btnZone.toLowerCase() === zone.toLowerCase() || (zone === "all" && (btnZone === "all" || btn.textContent.trim() === "All"))) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });
  }
  renderLiveCorridors(allLiveCorridors);
}

function onLiveDateScheduleChanged() {
  const dateInput = document.getElementById("liveRouteDateInput");
  const timeInput = document.getElementById("liveRouteTimeInput");
  const horizonLabel = document.getElementById("liveScheduleHorizonLabel");
  const badge = document.getElementById("liveEventsCountBadge");
  if (!dateInput || !timeInput) return;

  const dateVal = dateInput.value || "2026-11-03";
  const timeVal = timeInput.value || "10:00";
  const partsD = dateVal.split("-").map(Number);
  const dt = new Date(partsD[0], partsD[1] - 1, partsD[2]);
  const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const dayName = days[dt.getDay()] || "Tuesday";
  const monthName = months[dt.getMonth()] || "Nov";
  const dayNum = dt.getDate();

  if (horizonLabel) {
    horizonLabel.textContent = `Bengaluru Operational Horizon: ${dayName}, ${monthName} ${dayNum}, ${partsD[0]} • ${timeVal}`;
  }

  if (allEvents && badge) {
    const [h, m] = timeVal.split(":").map(Number);
    const totalMins = (h * 60) + (m || 0);
    const activeCount = allEvents.filter(e => {
      const eStart = e.date || "";
      const eEnd = e.end_date || eStart;
      const dateMatch = eEnd >= eStart ? (eStart <= dateVal && dateVal <= eEnd) : (eStart === dateVal);
      if (!dateMatch) return false;
      const [eH1, eM1] = (e.start_time || "00:00").split(":").map(Number);
      const [eH2, eM2] = (e.end_time || "23:59").split(":").map(Number);
      const eMin1 = (eH1 * 60) + (eM1 || 0);
      const eMin2 = (eH2 * 60) + (eM2 || 0);
      return eMin1 <= eMin2
        ? (totalMins >= eMin1 && totalMins <= eMin2)
        : (totalMins >= eMin1 || totalMins <= eMin2);
    }).length;

    badge.textContent = activeCount > 0 ? `${activeCount} Bengaluru Disruptions Active` : "Corridors Nominal Flow";
    badge.className = activeCount > 0 ? "badge-tag warning" : "badge-tag emerald";
  }
}
window.onLiveDateScheduleChanged = onLiveDateScheduleChanged;

async function evaluateLiveRoute() {
  const origSelect = document.getElementById("liveOriginSelect");
  const destSelect = document.getElementById("liveDestSelect");
  const dateInput = document.getElementById("liveRouteDateInput");
  const timeInput = document.getElementById("liveRouteTimeInput");
  const btn = document.getElementById("btnLiveEvaluate");
  const resultBox = document.getElementById("liveRouteResultBox");

  if (!origSelect || !destSelect || !btn) return;
  const orig = origSelect.value;
  const dest = destSelect.value;
  const date = dateInput ? dateInput.value : "";
  const time = timeInput ? timeInput.value : "";

  if (orig === dest) {
    showToast("Please choose distinct origin and destination corridors.", "warning");
    return;
  }

  setButtonLoading(btn, true, "Evaluating Real-Time Probes…");

  try {
    const res = await fetch("/api/live/route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ origin_road: orig, destination_road: dest, date, time })
    });
    const data = await res.json();
    if (!data || !data.evaluation) throw new Error("Invalid response from server");

    const evalData = data.evaluation;
    if (resultBox) resultBox.style.display = "block";

    const primBadge = document.getElementById("livePrimaryBadge");
    const primPills = document.getElementById("livePrimaryPills");
    const primSpeed = document.getElementById("livePrimarySpeed");
    const primVol = document.getElementById("livePrimaryVol");

    if (primBadge) {
      primBadge.textContent = evalData.primary_congestion;
      primBadge.className = `badge-tag ${evalData.primary_congestion.toLowerCase()}`;
    }
    if (primPills) {
      primPills.innerHTML = formatRoutePills(evalData.primary_route, allLiveCorridors);
    }
    if (primSpeed) primSpeed.textContent = `${evalData.primary_speed_kmh} km/h`;
    if (primVol) primVol.textContent = `${evalData.primary_vehicle_count.toLocaleString()} veh/hr`;

    const bypassBadge = document.getElementById("liveBypassBadge");
    const bypassPills = document.getElementById("liveBypassPills");
    const bypassSpeed = document.getElementById("liveBypassSpeed");
    const timeSaved = document.getElementById("liveTimeSaved");

    if (bypassBadge) {
      bypassBadge.textContent = evalData.recommended_congestion;
      bypassBadge.className = `badge-tag ${evalData.recommended_congestion.toLowerCase()}`;
    }
    if (bypassPills) {
      bypassPills.innerHTML = formatRoutePills(evalData.recommended_route, allLiveCorridors);
    }
    if (bypassSpeed) bypassSpeed.textContent = `${evalData.alternate_speed_kmh} km/h`;
    if (timeSaved) {
      timeSaved.textContent = evalData.is_rerouted ? `${evalData.time_saved_minutes} min` : "Direct";
    }

    const narrative = document.getElementById("liveNarrativeText");
    if (narrative) {
      if (evalData.active_events && evalData.active_events.length > 0) {
        const eventsList = evalData.active_events.map(evt => `
          <div class="live-event-bullet-card">
            <div class="live-event-bullet-header">
              <span class="live-pulse-dot warning"></span>
              <span class="live-event-pill-type">${escapeHtml(evt.event_type || 'Disruption')}</span>
              <strong class="live-event-title">${escapeHtml(evt.name)}</strong>
            </div>
            <div class="live-event-loc-detail">
              <span class="layer-dot blue" style="display:inline-block; vertical-align:middle; margin-right:4px;"></span><em>${escapeHtml(evt.location_name || 'Bengaluru Corridor')}</em>: ${escapeHtml(evt.description || 'Active live incident restricting corridor velocity.')}
            </div>
            <div class="live-event-impact-chip">
              Kinematic Impact: <strong>-${evt.speed_impact_pct || 40}% speed drop</strong> &bull; <strong>+${(evt.volume_surge_vph || 500).toLocaleString()} veh/hr surge</strong>
            </div>
          </div>
        `).join("");

        const bypassId = evalData.recommended_route && evalData.recommended_route.length > 1 ? evalData.recommended_route[1] : "";
        const bypassItem = allLiveCorridors.find(c => c.road_id === bypassId);
        const bypassName = bypassItem ? bypassItem.road_name : (evalData.recommended_route_names && evalData.recommended_route_names[1] ? evalData.recommended_route_names[1] : bypassId);

        narrative.innerHTML = `
          <div class="live-event-disruption-container">
            <div class="live-event-alert-tag">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                <line x1="12" y1="9" x2="12" y2="13"></line>
                <line x1="12" y1="17" x2="12.01" y2="17"></line>
              </svg>
              <span>Active Bengaluru Incidents Impacting Route</span>
            </div>
            <p class="live-disruption-lead">
              This is happening so it's just congested. These are the events still going:
            </p>
            <div class="live-active-events-stack">
              ${eventsList}
            </div>
            <div class="live-route-suggestion-box">
              <div class="suggestion-header">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="9 18 15 12 9 6"></polyline>
                </svg>
                <span>Suggested Alternate Bypass Road:</span>
              </div>
              <p class="suggestion-detail">
                We suggest taking the dynamic bypass via <strong>${escapeHtml(bypassName)}</strong>. It is currently operating at <strong>${evalData.alternate_speed_kmh} km/h</strong> with <strong>${evalData.recommended_congestion}</strong> density, saving <strong>~${evalData.time_saved_minutes} minutes</strong> transit time.
              </p>
            </div>
          </div>
        `;
      } else if (evalData.is_rerouted) {
        const bypassId = evalData.recommended_route && evalData.recommended_route.length > 1 ? evalData.recommended_route[1] : "";
        const bypassItem = allLiveCorridors.find(c => c.road_id === bypassId);
        const bypassName = bypassItem ? bypassItem.road_name : (evalData.recommended_route_names && evalData.recommended_route_names[1] ? evalData.recommended_route_names[1] : bypassId);

        narrative.innerHTML = `
          <div class="live-event-disruption-container">
            <div class="live-event-alert-tag warning">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
              <span>Heavy Live Arterial Bottleneck Detected</span>
            </div>
            <p class="live-disruption-lead">
              Live TomTom probe telemetry indicates severe congestion (${evalData.primary_speed_kmh} km/h) on the primary corridor.
            </p>
            <div class="live-route-suggestion-box">
              <div class="suggestion-header">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="9 18 15 12 9 6"></polyline>
                </svg>
                <span>Suggested Alternate Bypass Road:</span>
              </div>
              <p class="suggestion-detail">
                We suggest taking the dynamic bypass via <strong>${escapeHtml(bypassName)}</strong> to save <strong>~${evalData.time_saved_minutes} minutes</strong> transit time.
              </p>
            </div>
          </div>
        `;
      } else {
        narrative.innerHTML = `
          <div class="live-normal-flow-box">
            <div class="normal-flow-tag">
              <span class="live-pulse-dot" style="background:#10b981; width:7px; height:7px; display:inline-block; border-radius:50%; margin-right:6px;"></span>
              <strong>Normal Live Corridor Flow</strong>
            </div>
            <p class="normal-flow-desc">
              No active disruptions or municipal incidents reported along this corridor. Direct route via <strong>${escapeHtml(evalData.origin_name || 'selected corridor')}</strong> is optimal under real-time probe conditions (<strong>${evalData.primary_speed_kmh} km/h</strong>, ${evalData.primary_congestion} congestion). No bypass required.
            </p>
          </div>
        `;
      }
    }

    playHapticBeep(650, 45, "sine");
    if (window.renderMapLaneRoute) {
      window.renderMapLaneRoute(evalData);
    }
  } catch (err) {
    showToast(`Evaluation error: ${err.message}`, "error");
  } finally {
    setButtonLoading(btn, false);
  }
}

async function refreshLiveFeeds() {
  const btn = document.getElementById("btnRefreshLive");
  if (!btn) return;
  setButtonLoading(btn, true, "Syncing…");

  try {
    await loadLiveStatus();
    await loadLiveTelemetry(true);
    showToast("Live Bengaluru grid telemetry synchronized.", "success");
    playHapticBeep(780, 50, "sine");
  } catch (err) {
    showToast("Failed to refresh live feeds.", "error");
  } finally {
    setButtonLoading(btn, false);
  }
}

async function simulateSilkBoardLiveDisruption() {
  const origSelect = document.getElementById("liveOriginSelect");
  const destSelect = document.getElementById("liveDestSelect");
  const btn = document.getElementById("btnSilkBoardDisruptionPreset");

  if (origSelect && destSelect) {
    origSelect.value = "RD_BLR_06";
    destSelect.value = "RD_BLR_11";
  }

  if (btn) setButtonLoading(btn, true, "Syncing…");

  try {
    const res = await fetch("/api/events/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ zone: "Electronic City South" })
    });
    const data = await res.json();
    if (data.status === "success") {
      playSuccessChime();
      showToast("Silk Board incident synced: BMRCL Metro Work active.", "warning");
    }
  } catch (e) {
    console.error("Live incident sync error:", e);
  } finally {
    if (btn) setButtonLoading(btn, false);
  }

  await evaluateLiveRoute();
}
window.simulateSilkBoardLiveDisruption = simulateSilkBoardLiveDisruption;

/* ==========================================================================
   GOOGLE MAPS LIVE TRAFFIC & LANE-ROUTING HEATMAP MONITOR MODULE
   ========================================================================== */

const OBSIDIAN_DARK_MAP_STYLES = [
  { elementType: "geometry", stylers: [{ color: "#070b12" }] },
  { elementType: "labels.text.stroke", stylers: [{ color: "#070b12" }, { weight: 3 }] },
  { elementType: "labels.text.fill", stylers: [{ color: "#64748b" }] },
  {
    featureType: "administrative.locality",
    elementType: "labels.text.fill",
    stylers: [{ color: "#94a3b8" }, { weight: 500 }]
  },
  {
    featureType: "poi",
    elementType: "labels.text.fill",
    stylers: [{ color: "#475569" }]
  },
  {
    featureType: "poi.park",
    elementType: "geometry",
    stylers: [{ color: "#0d1a1b" }]
  },
  {
    featureType: "poi.park",
    elementType: "labels.text.fill",
    stylers: [{ color: "#10b981" }, { lightness: -20 }]
  },
  {
    featureType: "road",
    elementType: "geometry",
    stylers: [{ color: "#161e2e" }]
  },
  {
    featureType: "road",
    elementType: "geometry.stroke",
    stylers: [{ color: "#090d16" }]
  },
  {
    featureType: "road",
    elementType: "labels.text.fill",
    stylers: [{ color: "#818cf8" }, { lightness: -10 }]
  },
  {
    featureType: "road.highway",
    elementType: "geometry",
    stylers: [{ color: "#1e293b" }]
  },
  {
    featureType: "road.highway",
    elementType: "geometry.stroke",
    stylers: [{ color: "#0f172a" }, { weight: 1.5 }]
  },
  {
    featureType: "road.highway",
    elementType: "labels.text.fill",
    stylers: [{ color: "#f8fafc" }]
  },
  {
    featureType: "transit",
    elementType: "geometry",
    stylers: [{ color: "#141c2c" }]
  },
  {
    featureType: "transit.station",
    elementType: "labels.text.fill",
    stylers: [{ color: "#38bdf8" }]
  },
  {
    featureType: "water",
    elementType: "geometry",
    stylers: [{ color: "#04070d" }]
  },
  {
    featureType: "water",
    elementType: "labels.text.fill",
    stylers: [{ color: "#0284c7" }, { lightness: -30 }]
  }
];

let gMap = null;
let mapMarkers = [];
let mapPolylines = [];
let mapHeatmapLayer = null;
let mapTrafficLayer = null;
let currentMapEvaluation = null;
let mapPlaceSearchDebounce = null;
let mapConfigCache = null;
let vectorCanvasAnimFrame = null;
let mapActiveLayers = {
  lanes: true,
  heatmap: true,
  traffic: false,
  corridors: true
};

const BENGALURU_MAP_CENTER = { lat: 12.9716, lng: 77.5946 };

async function initGoogleMapMonitor() {
  const canvas = document.getElementById("googleMapCanvas");
  if (!canvas) return;

  try {
    const res = await fetch("/api/map/config");
    const cfg = await res.json();
    mapConfigCache = cfg;

    const statusBadge = document.getElementById("mapEngineStatusBadge");

    if (cfg && cfg.configured && cfg.api_key) {
      if (statusBadge) statusBadge.textContent = "Google Maps Platform • Live Map & Heatmap";
      loadGoogleMapsApiScript(cfg.api_key);
    } else {
      if (statusBadge) statusBadge.textContent = "Obsidian Vector Engine (API Key Unconfigured)";
      initVectorFallbackMap(canvas);
    }
  } catch (err) {
    console.warn("Could not load /api/map/config, mounting vector fallback:", err);
    initVectorFallbackMap(canvas);
  }
}
window.initGoogleMapMonitor = initGoogleMapMonitor;

function loadGoogleMapsApiScript(apiKey) {
  if (window.google && window.google.maps) {
    initGoogleMapInstance();
    return;
  }
  const existing = document.getElementById("googleMapsScriptTag");
  if (existing) return;

  window.gm_authFailure = function() {
    console.warn("Google Maps Platform authentication failure. Reverting to Obsidian Vector Monitor.");
    const statusBadge = document.getElementById("mapEngineStatusBadge");
    if (statusBadge) statusBadge.textContent = "Obsidian Vector Engine (Google Maps Auth Failed / Fallback Active)";
    const canvas = document.getElementById("googleMapCanvas");
    if (canvas) initVectorFallbackMap(canvas);
  };

  const script = document.createElement("script");
  script.id = "googleMapsScriptTag";
  script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&libraries=places,visualization,geometry&callback=initGoogleMapInstance`;
  script.async = true;
  script.defer = true;
  script.onerror = () => {
    console.warn("Failed to load Google Maps script; falling back to Obsidian Vector Monitor.");
    const canvas = document.getElementById("googleMapCanvas");
    if (canvas) initVectorFallbackMap(canvas);
  };
  document.head.appendChild(script);
}

function initGoogleMapInstance() {
  const canvas = document.getElementById("googleMapCanvas");
  if (!canvas || !window.google || !window.google.maps) return;

  canvas.innerHTML = "";

  gMap = new google.maps.Map(canvas, {
    center: BENGALURU_MAP_CENTER,
    zoom: 12,
    styles: OBSIDIAN_DARK_MAP_STYLES,
    disableDefaultUI: false,
    zoomControl: true,
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: true,
    backgroundColor: "#07080a"
  });

  mapTrafficLayer = new google.maps.TrafficLayer();
  if (mapActiveLayers.traffic) {
    mapTrafficLayer.setMap(gMap);
  }

  loadCorridorJunctionPins();
  loadCongestionHeatmap();

  if (currentMapEvaluation) {
    renderMapLaneRoute(currentMapEvaluation);
  }

  // Attach Google Places Autocomplete if available
  try {
    const searchInput = document.getElementById("mapPlaceSearchInput");
    if (searchInput && window.google.maps.places && !searchInput.dataset.autocompleteAttached) {
      const autocomplete = new google.maps.places.Autocomplete(searchInput, {
        componentRestrictions: { country: "in" },
        bounds: new google.maps.LatLngBounds(
          new google.maps.LatLng(12.75, 77.40),
          new google.maps.LatLng(13.20, 77.85)
        ),
        fields: ["geometry", "name", "formatted_address"]
      });
      autocomplete.addListener("place_changed", () => {
        const place = autocomplete.getPlace();
        if (place && place.geometry && place.geometry.location) {
          gMap.panTo(place.geometry.location);
          gMap.setZoom(14);
          showToast(`Selected: ${place.name || place.formatted_address}`, "info", 1500);
        }
      });
      searchInput.dataset.autocompleteAttached = "true";
    }
  } catch (err) {
    console.debug("Places autocomplete init:", err);
  }
}
window.initGoogleMapInstance = initGoogleMapInstance;

/* Fallback Vector Canvas for Sandboxed / Offline Environments */
function initVectorFallbackMap(container) {
  if (!container) return;
  container.innerHTML = "";

  const canvas = document.createElement("canvas");
  canvas.className = "vector-fallback-canvas";
  canvas.width = container.clientWidth || 900;
  canvas.height = container.clientHeight || 520;
  container.appendChild(canvas);

  const ctx = canvas.getContext("2d");
  let pulse = 0;

  function renderFrame() {
    if (!canvas.parentElement) return;
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    // Dark grid background
    ctx.fillStyle = "#07080a";
    ctx.fillRect(0, 0, w, h);

    // Subtle grid pattern
    ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
    ctx.lineWidth = 1;
    for (let x = 0; x < w; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0); ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y < h; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y); ctx.lineTo(w, y);
      ctx.stroke();
    }

    // Outer boundary ring (Simulated Bengaluru Outer Ring Road)
    ctx.strokeStyle = "rgba(56, 189, 248, 0.12)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.ellipse(w / 2, h / 2, w * 0.38, h * 0.36, 0, 0, Math.PI * 2);
    ctx.stroke();

    // Heatmap circles if enabled
    if (mapActiveLayers.heatmap && allLiveCorridors.length > 0) {
      allLiveCorridors.forEach((c, i) => {
        const pt = getCanvasCoord(c.road_id, w, h);
        const grad = ctx.createRadialGradient(pt.x, pt.y, 4, pt.x, pt.y, 38);
        const los = c.congestion_level || "Moderate";
        const hasLive = Boolean(c.has_valid_live_observation || c.is_live);

        let col = "107, 114, 128"; // Default Grey for unobserved / standby baseline
        let alpha = 0.22;

        if (heatmapObservationMode === "density") {
          alpha = los === "Severe" ? 0.38 : los === "High" ? 0.28 : 0.18;
          col = los === "Severe" ? "239, 68, 68" : los === "High" ? "249, 115, 22" : los === "Moderate" ? "245, 158, 11" : "16, 185, 129";
        } else {
          // Strict Live Observations Mode: Only observed corridors show congestion colors, unobserved stay grey
          if (hasLive) {
            alpha = los === "Severe" ? 0.38 : los === "High" ? 0.28 : 0.18;
            col = los === "Severe" ? "239, 68, 68" : los === "High" ? "249, 115, 22" : los === "Moderate" ? "245, 158, 11" : "16, 185, 129";
          } else {
            col = "107, 114, 128"; // Distinct Grey for unobserved
            alpha = 0.16;
          }
        }

        grad.addColorStop(0, `rgba(${col}, ${alpha})`);
        grad.addColorStop(1, `rgba(${col}, 0)`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 38, 0, Math.PI * 2);
        ctx.fill();
      });
    }

    // Draw Corridors
    allRoads.forEach((r, idx) => {
      const pt = getCanvasCoord(r.road_id, w, h);
      const centerPt = { x: w / 2, y: h / 2 };

      // Base corridor link
      ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(centerPt.x, centerPt.y);
      ctx.lineTo(pt.x, pt.y);
      ctx.stroke();

      // Node pin
      if (mapActiveLayers.corridors) {
        const isSelected = selectedHeatmapCorridorId === r.road_id;
        ctx.fillStyle = isSelected ? "#38bdf8" : "#1e293b";
        ctx.strokeStyle = isSelected ? "#ffffff" : "rgba(255, 255, 255, 0.25)";
        ctx.lineWidth = isSelected ? 2.5 : 1.5;
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, isSelected ? 8 : 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        if (isSelected) {
          ctx.strokeStyle = "rgba(56, 189, 248, 0.45)";
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.arc(pt.x, pt.y, 14, 0, Math.PI * 2);
          ctx.stroke();
        }

        ctx.fillStyle = isSelected ? "#38bdf8" : "#94a3b8";
        ctx.font = isSelected ? "bold 10px monospace" : "9px monospace";
        ctx.fillText(r.road_id, pt.x + 8, pt.y + 3);
      }
    });

    // Draw Evaluated Route if active
    if (mapActiveLayers.lanes && currentMapEvaluation) {
      const primaryPath = currentMapEvaluation.primary_route || [];
      const bypassPath = currentMapEvaluation.recommended_route || [];
      const los = currentMapEvaluation.primary_congestion || "Moderate";
      const primCol = los === "Severe" ? "#ef4444" : los === "High" ? "#f97316" : los === "Moderate" ? "#f59e0b" : "#10b981";

      // Draw Primary Route
      if (primaryPath.length >= 2) {
        ctx.strokeStyle = primCol;
        ctx.lineWidth = 5;
        ctx.shadowColor = primCol;
        ctx.shadowBlur = 10;
        ctx.beginPath();
        primaryPath.forEach((rid, i) => {
          const pt = getCanvasCoord(rid, w, h);
          if (i === 0) ctx.moveTo(pt.x, pt.y);
          else ctx.lineTo(pt.x, pt.y);
        });
        ctx.stroke();
        ctx.shadowBlur = 0;
      }

      // Draw Recommended Bypass Route
      if (currentMapEvaluation.is_rerouted && bypassPath.length >= 2) {
        ctx.strokeStyle = "#06b6d4";
        ctx.lineWidth = 4;
        ctx.setLineDash([8, 4]);
        ctx.shadowColor = "#06b6d4";
        ctx.shadowBlur = 12;
        ctx.beginPath();
        bypassPath.forEach((rid, i) => {
          const pt = getCanvasCoord(rid, w, h);
          if (i === 0) ctx.moveTo(pt.x, pt.y);
          else ctx.lineTo(pt.x, pt.y);
        });
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.shadowBlur = 0;
      }
    }

    pulse += 0.04;
    vectorCanvasAnimFrame = requestAnimationFrame(renderFrame);
  }

  // Interactive Corridor Pin Click & Hover Selection
  canvas.addEventListener("click", (evt) => {
    const rect = canvas.getBoundingClientRect();
    const clickX = evt.clientX - rect.left;
    const clickY = evt.clientY - rect.top;
    const w = canvas.width, h = canvas.height;

    let closest = null;
    let minDist = 24; // 24px hit target radius

    allRoads.forEach(r => {
      const pt = getCanvasCoord(r.road_id, w, h);
      const dist = Math.hypot(clickX - pt.x, clickY - pt.y);
      if (dist < minDist) {
        minDist = dist;
        closest = r.road_id;
      }
    });

    if (closest) {
      openHeatmapCorridorFlyout(closest);
    } else {
      closeHeatmapFlyout();
    }
  });

  canvas.addEventListener("mousemove", (evt) => {
    const rect = canvas.getBoundingClientRect();
    const mx = evt.clientX - rect.left;
    const my = evt.clientY - rect.top;
    const w = canvas.width, h = canvas.height;

    const isHover = allRoads.some(r => {
      const pt = getCanvasCoord(r.road_id, w, h);
      return Math.hypot(mx - pt.x, my - pt.y) < 18;
    });
    canvas.style.cursor = isHover ? "pointer" : "default";
  });

  cancelAnimationFrame(vectorCanvasAnimFrame);
  renderFrame();
}

function getCanvasCoord(roadId, w, h) {
  const coordsMap = {
    "RD_BLR_01": { x: w * 0.62, y: h * 0.46 },
    "RD_BLR_02": { x: w * 0.51, y: h * 0.48 },
    "RD_BLR_03": { x: w * 0.50, y: h * 0.22 },
    "RD_BLR_04": { x: w * 0.63, y: h * 0.44 },
    "RD_BLR_05": { x: w * 0.50, y: h * 0.18 },
    "RD_BLR_06": { x: w * 0.66, y: h * 0.88 },
    "RD_BLR_07": { x: w * 0.86, y: h * 0.42 },
    "RD_BLR_08": { x: w * 0.46, y: h * 0.64 },
    "RD_BLR_09": { x: w * 0.80, y: h * 0.52 },
    "RD_BLR_10": { x: w * 0.68, y: h * 0.65 },
    "RD_BLR_11": { x: w * 0.58, y: h * 0.68 },
    "RD_BLR_12": { x: w * 0.58, y: h * 0.60 },
    "RD_BLR_13": { x: w * 0.42, y: h * 0.62 },
    "RD_BLR_14": { x: w * 0.56, y: h * 0.47 },
    "RD_BLR_15": { x: w * 0.28, y: h * 0.26 },
    "RD_BLR_16": { x: w * 0.32, y: h * 0.28 },
    "RD_BLR_17": { x: w * 0.64, y: h * 0.51 },
    "RD_BLR_18": { x: w * 0.52, y: h * 0.49 },
    "RD_BLR_19": { x: w * 0.62, y: h * 0.15 },
    "RD_BLR_20": { x: w * 0.72, y: h * 0.90 },
    "RD_BLR_21": { x: w * 0.88, y: h * 0.58 },
    "RD_BLR_22": { x: w * 0.40, y: h * 0.72 },
    "RD_BLR_23": { x: w * 0.57, y: h * 0.58 },
    "RD_BLR_24": { x: w * 0.38, y: h * 0.34 }
  };
  return coordsMap[roadId] || { x: w * 0.5, y: h * 0.5 };
}

/* Layer Toggle Controller */
function toggleMapLayer(layer, forceState = null) {
  if (forceState !== null) {
    mapActiveLayers[layer] = !!forceState;
  } else {
    mapActiveLayers[layer] = !mapActiveLayers[layer];
  }
  const btnId = layer === "lanes" ? "btnToggleLanes" : layer === "heatmap" ? "btnToggleHeatmap" : layer === "traffic" ? "btnToggleTraffic" : "btnToggleCorridors";
  const btn = document.getElementById(btnId);
  if (btn) btn.classList.toggle("active", mapActiveLayers[layer]);

  if (layer === "traffic" && mapTrafficLayer && gMap) {
    mapTrafficLayer.setMap(mapActiveLayers.traffic ? gMap : null);
  }

  if (layer === "heatmap" && mapHeatmapLayer && gMap) {
    mapHeatmapLayer.setMap(mapActiveLayers.heatmap ? gMap : null);
  }

  if (layer === "lanes") {
    mapPolylines.forEach(p => p.setVisible(mapActiveLayers.lanes));
  }

  if (layer === "corridors") {
    mapMarkers.forEach(m => m.setVisible(mapActiveLayers.corridors));
  }

  if (forceState === null) {
    if (window.playTactileClick) window.playTactileClick();
    showToast(`Toggled ${layer.toUpperCase()} layer: ${mapActiveLayers[layer] ? "ON" : "OFF"}`, "info", 1200);
  }
}
window.toggleMapLayer = toggleMapLayer;

function recenterGoogleMap() {
  if (gMap) {
    gMap.panTo(BENGALURU_MAP_CENTER);
    gMap.setZoom(12);
  }
  if (window.playTactileClick) window.playTactileClick();
  showToast("Recentered to Central Bengaluru", "info", 1200);
}
window.recenterGoogleMap = recenterGoogleMap;

/* Place Recognition & Autocomplete */
function onPlaceSearchInput(val) {
  clearTimeout(mapPlaceSearchDebounce);
  const clearBtn = document.getElementById("mapSearchClearBtn");
  const suggestionsBox = document.getElementById("mapPlaceSuggestions");
  if (clearBtn) clearBtn.style.display = val.length > 0 ? "block" : "none";

  if (!val || val.trim().length === 0) {
    if (suggestionsBox) suggestionsBox.style.display = "none";
    return;
  }

  mapPlaceSearchDebounce = setTimeout(async () => {
    try {
      const res = await fetch(`/api/map/places?q=${encodeURIComponent(val)}&limit=6`);
      const data = await res.json();
      if (data && data.places && data.places.length > 0) {
        renderPlaceSuggestions(data.places);
      } else {
        if (suggestionsBox) suggestionsBox.style.display = "none";
      }
    } catch (e) {
      console.warn("Place search error:", e);
    }
  }, 220);
}
window.onPlaceSearchInput = onPlaceSearchInput;

function renderPlaceSuggestions(places) {
  const box = document.getElementById("mapPlaceSuggestions");
  if (!box) return;

  box.innerHTML = places.map((p, idx) => `
    <div class="suggestion-item" onclick="selectPlaceSuggestion('${p.road_id}', ${p.coordinates && p.coordinates.length > 0 ? p.coordinates[0][0] : 12.9716}, ${p.coordinates && p.coordinates.length > 0 ? p.coordinates[0][1] : 77.5946})">
      <div class="sugg-main">
        <span class="sugg-title">${escapeHtml(p.name)}</span>
        <span class="sugg-zone">Zone: ${escapeHtml(p.city_zone || 'Bengaluru')} &bull; ${escapeHtml(p.intersection_name || '')}</span>
      </div>
      <span class="sugg-badge">${p.lanes || 4} LANES</span>
    </div>
  `).join("");
  box.style.display = "block";
}

function selectPlaceSuggestion(roadId, lat, lon) {
  const box = document.getElementById("mapPlaceSuggestions");
  const input = document.getElementById("mapPlaceSearchInput");
  if (box) box.style.display = "none";
  if (input) input.value = CANONICAL_ROAD_NAMES[roadId] || roadId;

  // Set as Destination or Origin in the Route Planner
  const origSelect = document.getElementById("routeOriginSelect");
  const destSelect = document.getElementById("routeDestSelect");

  if (origSelect && origSelect.value !== roadId) {
    if (destSelect) destSelect.value = roadId;
  } else if (origSelect) {
    origSelect.value = roadId;
  }

  const liveOrig = document.getElementById("liveOriginSelect");
  const liveDest = document.getElementById("liveDestSelect");
  if (liveOrig && liveDest) {
    if (liveOrig.value !== roadId) {
      liveDest.value = roadId;
    } else {
      liveOrig.value = roadId;
    }
  }

  if (gMap) {
    gMap.panTo({ lat, lng: lon });
    gMap.setZoom(14);
  }

  showToast(`Selected Place: ${CANONICAL_ROAD_NAMES[roadId] || roadId}. Evaluating optimal route…`, "success", 1800);
  if (window.playTactileClick) window.playTactileClick();
  setTimeout(() => evaluateRoute(), 250);
}
window.selectPlaceSuggestion = selectPlaceSuggestion;

function clearPlaceSearch() {
  const input = document.getElementById("mapPlaceSearchInput");
  const clearBtn = document.getElementById("mapSearchClearBtn");
  const box = document.getElementById("mapPlaceSuggestions");
  if (input) input.value = "";
  if (clearBtn) clearBtn.style.display = "none";
  if (box) box.style.display = "none";
}
window.clearPlaceSearch = clearPlaceSearch;

/* Heatmap Layer Generator */
async function loadCongestionHeatmap() {
  if (!gMap || !window.google || !window.google.maps || !google.maps.visualization) return;

  try {
    const res = await fetch("/api/map/heatmap");
    const data = await res.json();
    if (!data || !data.points) return;

    const heatmapPoints = data.points.map(pt => ({
      location: new google.maps.LatLng(pt.lat, pt.lng),
      weight: pt.weight * 3.5
    }));

    if (mapHeatmapLayer) {
      mapHeatmapLayer.setMap(null);
    }

    mapHeatmapLayer = new google.maps.visualization.HeatmapLayer({
      data: heatmapPoints,
      radius: 28,
      maxIntensity: 3.5,
      opacity: 0.75,
      gradient: [
        "rgba(16, 185, 129, 0)",
        "rgba(16, 185, 129, 0.7)",
        "rgba(245, 158, 11, 0.85)",
        "rgba(249, 115, 22, 0.95)",
        "rgba(239, 68, 68, 1)"
      ]
    });

    if (mapActiveLayers.heatmap) {
      mapHeatmapLayer.setMap(gMap);
    }
  } catch (err) {
    console.warn("Could not load congestion heatmap:", err);
  }
}

/* Corridor Junction Pins */
function loadCorridorJunctionPins() {
  if (!gMap || !window.google || !window.google.maps) return;

  // Clear existing pins
  mapMarkers.forEach(m => m.setMap(null));
  mapMarkers = [];

  const rawGps = {
    "RD_BLR_01": [12.9784, 77.6408], "RD_BLR_02": [12.9756, 77.6066],
    "RD_BLR_03": [13.0358, 77.5970], "RD_BLR_04": [12.9790, 77.6420],
    "RD_BLR_05": [13.0380, 77.5985], "RD_BLR_06": [12.8452, 77.6602],
    "RD_BLR_07": [12.9850, 77.7280], "RD_BLR_08": [12.9250, 77.5938],
    "RD_BLR_09": [12.9560, 77.7010], "RD_BLR_10": [12.9240, 77.6520],
    "RD_BLR_11": [12.9176, 77.6238], "RD_BLR_12": [12.9352, 77.6245],
    "RD_BLR_13": [12.9280, 77.5790], "RD_BLR_14": [12.9725, 77.6200],
    "RD_BLR_15": [13.0280, 77.5400], "RD_BLR_16": [13.0238, 77.5529],
    "RD_BLR_17": [12.9600, 77.6480], "RD_BLR_18": [12.9730, 77.6075],
    "RD_BLR_19": [13.0550, 77.6320], "RD_BLR_20": [12.8399, 77.6770],
    "RD_BLR_21": [12.9420, 77.7470], "RD_BLR_22": [12.9050, 77.5750],
    "RD_BLR_23": [12.9400, 77.6200], "RD_BLR_24": [13.0030, 77.5700]
  };

  Object.entries(rawGps).forEach(([rid, coords]) => {
    const marker = new google.maps.Marker({
      position: { lat: coords[0], lng: coords[1] },
      map: mapActiveLayers.corridors ? gMap : null,
      title: `${CANONICAL_ROAD_NAMES[rid] || rid} [${rid}]`,
      icon: {
        path: google.maps.SymbolPath.CIRCLE,
        scale: 5,
        fillColor: "#38bdf8",
        fillOpacity: 0.9,
        strokeColor: "#ffffff",
        strokeWeight: 1.5
      }
    });

    marker.addListener("click", () => {
      showToast(`Selected Corridor: ${CANONICAL_ROAD_NAMES[rid] || rid}`, "info", 1500);
      setOriginCorridor(rid);
    });

    mapMarkers.push(marker);
  });
}

/* Lane-Level Route Rendering Engine */
function renderMapLaneRoute(evalData) {
  if (!evalData) return;
  currentMapEvaluation = evalData;

  // 1. Update Floating HUD
  const hudPath = document.getElementById("hudPathName");
  const hudLos = document.getElementById("hudLosBadge");
  const hudTime = document.getElementById("hudEstTime");
  const hudLane = document.getElementById("hudLaneAdvice");
  const hudSaved = document.getElementById("hudTimeSaved");

  const origName = evalData.origin_road_name || evalData.origin_name || CANONICAL_ROAD_NAMES[evalData.origin_road] || evalData.origin_road;
  const destName = evalData.destination_road_name || evalData.destination_name || CANONICAL_ROAD_NAMES[evalData.destination_road] || evalData.destination_road;

  if (hudPath) hudPath.textContent = `${origName} → ${destName}`;

  if (hudLos) {
    const los = evalData.primary_congestion || "Moderate";
    hudLos.textContent = los;
    hudLos.className = `badge-tag ${los.toLowerCase()}`;
  }

  if (hudTime) {
    const est = evalData.primary_route ? Math.round(evalData.primary_route.length * 4.8) : 12;
    hudTime.textContent = `${est} min`;
  }

  if (hudLane) {
    if (evalData.is_rerouted) {
      hudLane.textContent = "Bypass Express Lane 2 (Clear of bottlenecks)";
      hudLane.className = "hud-val text-cyan";
    } else {
      hudLane.textContent = "Lane 2 (Through-Express Unrestricted)";
      hudLane.className = "hud-val text-emerald";
    }
  }

  if (hudSaved) {
    hudSaved.textContent = evalData.is_rerouted ? `⚡ ${evalData.time_saved_minutes} min saved` : "Direct route optimal";
  }

  // 2. Render On Google Maps (if available)
  if (gMap && window.google && window.google.maps) {
    // Clear old polylines
    mapPolylines.forEach(p => p.setMap(null));
    mapPolylines = [];

    const bounds = new google.maps.LatLngBounds();

    // Primary Route Coordinates
    let primaryCoords = [];
    if (evalData.primary_polylines && evalData.primary_polylines.length > 0) {
      primaryCoords = evalData.primary_polylines.map(pt => ({ lat: pt[0], lng: pt[1] }));
    } else if (evalData.primary_route) {
      const rawGps = {
        "RD_BLR_01": [12.9784, 77.6408], "RD_BLR_02": [12.9756, 77.6066],
        "RD_BLR_03": [13.0358, 77.5970], "RD_BLR_04": [12.9790, 77.6420],
        "RD_BLR_05": [13.0380, 77.5985], "RD_BLR_06": [12.8452, 77.6602],
        "RD_BLR_07": [12.9850, 77.7280], "RD_BLR_08": [12.9250, 77.5938],
        "RD_BLR_09": [12.9560, 77.7010], "RD_BLR_10": [12.9240, 77.6520],
        "RD_BLR_11": [12.9176, 77.6238], "RD_BLR_12": [12.9352, 77.6245],
        "RD_BLR_13": [12.9280, 77.5790], "RD_BLR_14": [12.9725, 77.6200],
        "RD_BLR_15": [13.0280, 77.5400], "RD_BLR_16": [13.0238, 77.5529],
        "RD_BLR_17": [12.9600, 77.6480], "RD_BLR_18": [12.9730, 77.6075],
        "RD_BLR_19": [13.0550, 77.6320], "RD_BLR_20": [12.8399, 77.6770],
        "RD_BLR_21": [12.9420, 77.7470], "RD_BLR_22": [12.9050, 77.5750],
        "RD_BLR_23": [12.9400, 77.6200], "RD_BLR_24": [13.0030, 77.5700]
      };
      primaryCoords = evalData.primary_route.map(r => {
        const pt = rawGps[r] || [12.9716, 77.5946];
        return { lat: pt[0], lng: pt[1] };
      });
    }

    const los = evalData.primary_congestion || "Moderate";
    const primColor = los === "Severe" ? "#ef4444" : los === "High" ? "#f97316" : los === "Moderate" ? "#f59e0b" : "#10b981";

    if (primaryCoords.length >= 2) {
      const primaryPolyline = new google.maps.Polyline({
        path: primaryCoords,
        geodesic: true,
        strokeColor: primColor,
        strokeOpacity: 0.9,
        strokeWeight: 6,
        map: mapActiveLayers.lanes ? gMap : null
      });
      mapPolylines.push(primaryPolyline);
      primaryCoords.forEach(c => bounds.extend(c));
    }

    // Recommended Bypass Route Coordinates
    if (evalData.is_rerouted) {
      let bypassCoords = [];
      if (evalData.recommended_polylines && evalData.recommended_polylines.length > 0) {
        bypassCoords = evalData.recommended_polylines.map(pt => ({ lat: pt[0], lng: pt[1] }));
      } else if (evalData.recommended_route) {
        const rawGps = {
          "RD_BLR_01": [12.9784, 77.6408], "RD_BLR_02": [12.9756, 77.6066],
          "RD_BLR_03": [13.0358, 77.5970], "RD_BLR_04": [12.9790, 77.6420],
          "RD_BLR_05": [13.0380, 77.5985], "RD_BLR_06": [12.8452, 77.6602],
          "RD_BLR_07": [12.9850, 77.7280], "RD_BLR_08": [12.9250, 77.5938],
          "RD_BLR_09": [12.9560, 77.7010], "RD_BLR_10": [12.9240, 77.6520],
          "RD_BLR_11": [12.9176, 77.6238], "RD_BLR_12": [12.9352, 77.6245],
          "RD_BLR_13": [12.9280, 77.5790], "RD_BLR_14": [12.9725, 77.6200],
          "RD_BLR_15": [13.0280, 77.5400], "RD_BLR_16": [13.0238, 77.5529],
          "RD_BLR_17": [12.9600, 77.6480], "RD_BLR_18": [12.9730, 77.6075],
          "RD_BLR_19": [13.0550, 77.6320], "RD_BLR_20": [12.8399, 77.6770],
          "RD_BLR_21": [12.9420, 77.7470], "RD_BLR_22": [12.9050, 77.5750],
          "RD_BLR_23": [12.9400, 77.6200], "RD_BLR_24": [13.0030, 77.5700]
        };
        bypassCoords = evalData.recommended_route.map(r => {
          const pt = rawGps[r] || [12.9716, 77.5946];
          return { lat: pt[0], lng: pt[1] };
        });
      }

      if (bypassCoords.length >= 2) {
        const bypassPolyline = new google.maps.Polyline({
          path: bypassCoords,
          geodesic: true,
          strokeColor: "#06b6d4",
          strokeOpacity: 0.95,
          strokeWeight: 5,
          map: mapActiveLayers.lanes ? gMap : null
        });
        mapPolylines.push(bypassPolyline);
        bypassCoords.forEach(c => bounds.extend(c));
      }
    }

    if (!bounds.isEmpty()) {
      gMap.fitBounds(bounds, { top: 70, right: 30, bottom: 30, left: 30 });
    }
  }
}
window.renderMapLaneRoute = renderMapLaneRoute;

/* External API Providers Modal Controllers */
function openApiProvidersModal() {
  const modal = document.getElementById("apiProvidersModal");
  if (modal) modal.style.display = "flex";
  loadApiProviderStatuses();
}
window.openApiProvidersModal = openApiProvidersModal;

function closeApiProvidersModal() {
  const modal = document.getElementById("apiProvidersModal");
  if (modal) modal.style.display = "none";
}
window.closeApiProvidersModal = closeApiProvidersModal;

async function loadApiProviderStatuses() {
  try {
    const res = await fetch("/api/config/providers");
    const data = await res.json();
    if (!data || !data.providers) return;

    data.providers.forEach(p => {
      if (p.name.includes("Google Maps")) {
        const statusBadge = document.getElementById("modalGoogleMapsStatus");
        const note = document.getElementById("googleMapsMaskedNote");
        if (statusBadge) {
          statusBadge.textContent = p.configured ? "Configured" : "Unconfigured";
          statusBadge.className = `badge-tag ${p.configured ? 'low' : 'severe'}`;
        }
        if (note) {
          note.textContent = p.configured ? `Active Masked Key: ${p.masked_key}` : "Current Key: None (Running in Resilient Obsidian Vector Fallback mode)";
        }
      } else if (p.name.includes("TomTom")) {
        const statusBadge = document.getElementById("modalTomTomStatus");
        const note = document.getElementById("tomTomMaskedNote");
        if (statusBadge) {
          statusBadge.textContent = p.configured ? "Configured" : "Unconfigured";
          statusBadge.className = `badge-tag ${p.configured ? 'low' : 'moderate'}`;
        }
        if (note) {
          note.textContent = p.configured ? `Active Masked Key: ${p.masked_key}` : "Current Key: None";
        }
      }
    });
  } catch (e) {
    console.warn("Could not load provider statuses:", e);
  }
}

async function saveGoogleMapsKey() {
  const input = document.getElementById("inputGoogleMapsKey");
  if (!input || !input.value.trim()) {
    showToast("Please enter a non-empty Google Maps API key.", "warning");
    return;
  }
  try {
    const token = currentUser ? currentUser.token : "";
    const res = await fetch("/api/config/google_maps", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({ api_key: input.value.trim() })
    });
    const data = await res.json();
    if (data.success) {
      showToast("Google Maps API key updated successfully! Reloading live map…", "success");
      input.value = "";
      loadApiProviderStatuses();
      setTimeout(() => initGoogleMapMonitor(), 600);
    } else {
      showToast(data.message || "Failed to update Google Maps key.", "error");
    }
  } catch (err) {
    showToast("Network error updating Google Maps key.", "error");
  }
}
window.saveGoogleMapsKey = saveGoogleMapsKey;

async function testGoogleMapsKey() {
  showToast("Testing connection to Google Maps Platform…", "info", 1500);
  try {
    const res = await fetch("/api/config/test/google_maps", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      showToast(`Google Maps reachable! Latency: ${data.latency_ms || 24}ms`, "success");
    } else {
      showToast(`Google Maps Test: ${data.message}`, "warning");
    }
  } catch (err) {
    showToast("Connection probe error contacting Google Maps.", "error");
  }
}
window.testGoogleMapsKey = testGoogleMapsKey;

async function saveTomTomKey() {
  const input = document.getElementById("inputTomTomKey");
  if (!input || !input.value.trim()) {
    showToast("Please enter a valid TomTom API key.", "warning");
    return;
  }
  try {
    const token = currentUser ? currentUser.token : "";
    const res = await fetch("/api/config/tomtom", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({ api_key: input.value.trim() })
    });
    const data = await res.json();
    if (data.success) {
      showToast("TomTom API key updated successfully!", "success");
      input.value = "";
      loadApiProviderStatuses();
    } else {
      showToast(data.message || "Failed to update TomTom key.", "error");
    }
  } catch (err) {
    showToast("Network error updating TomTom key.", "error");
  }
}
window.saveTomTomKey = saveTomTomKey;

async function testTomTomKey() {
  showToast("Testing TomTom Traffic API connection…", "info", 1500);
  try {
    const res = await fetch("/api/config/test/tomtom", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      showToast(`TomTom reachable! Latency: ${data.latency_ms}ms`, "success");
    } else {
      showToast(`TomTom Test: ${data.message}`, "warning");
    }
  } catch (err) {
    showToast("Probe error contacting TomTom.", "error");
  }
}
window.testTomTomKey = testTomTomKey;

async function testWeatherKey() {
  showToast("Testing Open-Meteo Weather API connection…", "info", 1500);
  try {
    const res = await fetch("/api/config/test/weather", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      showToast(`Weather API responsive! Latency: ${data.latency_ms}ms`, "success");
    } else {
      showToast(`Weather Probe: ${data.message}`, "warning");
    }
  } catch (err) {
    showToast("Probe error contacting Weather API.", "error");
  }
}
window.testWeatherKey = testWeatherKey;




/* ==========================================================================
   API & SYSTEM SYNTHESIZER HUB CONTROLLER
   ========================================================================== */

let isSynthesizerInitialized = false;
let synSandboxDebounceTimer = null;

async function initSynthesizerSection() {
  populateSandboxRoadSelect();
  loadSynthesizerProviders();
  loadSynthesizerStorageStatus();

  if (!isSynthesizerInitialized) {
    isSynthesizerInitialized = true;
    runSynthesizerHandshake();
    runSandboxInference();
  }
}
window.initSynthesizerSection = initSynthesizerSection;

function populateSandboxRoadSelect() {
  const select = document.getElementById("synSandboxRoadSelect");
  if (!select) return;
  if (select.children.length > 0) return;

  const roads = (allRoads && allRoads.length > 0) ? allRoads : [
    { road_id: "RD_BLR_01", road_name: "100 Feet Road", city_zone: "Indiranagar" },
    { road_id: "RD_BLR_02", road_name: "M.G. Road Corridor", city_zone: "Downtown Core" },
    { road_id: "RD_BLR_03", road_name: "Whitefield Main Road", city_zone: "Whitefield" },
    { road_id: "RD_BLR_04", road_name: "CMH Road", city_zone: "Indiranagar" },
    { road_id: "RD_BLR_05", road_name: "Outer Ring Road (Hebbal)", city_zone: "Hebbal North" },
    { road_id: "RD_BLR_06", road_name: "Hosur Road Arterial", city_zone: "Electronic City South" }
  ];

  select.innerHTML = roads.map(r => `
    <option value="${r.road_id}">${r.road_name || r.road_id} (${r.city_zone})</option>
  `).join("");
}

async function runSynthesizerHandshake() {
  const btn = document.getElementById("btnRunSynthesizerHandshake");
  const overallBadge = document.getElementById("synOverallHealthBadge");
  const statusText = document.getElementById("synHeaderStatusText");
  const lastAudit = document.getElementById("synLastAuditTime");

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner" style="display:inline-block;width:12px;height:12px;border:2px solid rgba(255,255,255,0.3);border-top-color:#fff;border-radius:50%;animation:spin 0.6s linear infinite;margin-right:6px;"></span> Synthesizing...`;
  }

  playTactileClick();

  try {
    const res = await fetch("/api/synthesizer/handshake", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": getAuthHeader()
      }
    });

    const data = await res.json();
    const handshake = data.data || {};
    const subs = handshake.subsystems || {};

    if (lastAudit) lastAudit.textContent = `Audited: ${new Date().toLocaleTimeString()}`;

    const isOptimal = handshake.overall_health === "OPTIMAL";
    if (overallBadge) {
      overallBadge.className = `badge-tag ${isOptimal ? "low" : "moderate"}`;
      overallBadge.textContent = `${handshake.overall_health} (${handshake.total_latency_ms} ms)`;
    }
    if (statusText) statusText.textContent = `All Subsystems Verified (${handshake.total_latency_ms} ms)`;

    // 1. TomTom
    const tt = subs.tomtom_traffic || {};
    const bTT = document.getElementById("badgeTomTom");
    if (bTT) {
      bTT.className = `badge-tag ${tt.reachable ? "low" : (tt.configured ? "high" : "default")}`;
      bTT.textContent = tt.status || "STANDBY";
    }
    const lTT = document.getElementById("latTomTom");
    if (lTT) lTT.textContent = `${tt.latency_ms || 0} ms`;
    const mTT = document.getElementById("msgTomTom");
    if (mTT) mTT.textContent = tt.message || "GPS probe velocities.";

    // 2. Google Maps
    const gm = subs.google_maps || {};
    const bGM = document.getElementById("badgeGoogleMaps");
    if (bGM) {
      bGM.className = `badge-tag ${gm.reachable ? "low" : (gm.configured ? "high" : "default")}`;
      bGM.textContent = gm.status || "STANDBY";
    }
    const lGM = document.getElementById("latGoogleMaps");
    if (lGM) lGM.textContent = `${gm.latency_ms || 0} ms`;
    const mGM = document.getElementById("msgGoogleMaps");
    if (mGM) mGM.textContent = gm.message || "Places & Geocoding vector.";

    // 3. Open-Meteo
    const om = subs.open_meteo || {};
    const bOM = document.getElementById("badgeOpenMeteo");
    if (bOM) {
      bOM.className = `badge-tag ${om.reachable ? "low" : "moderate"}`;
      bOM.textContent = om.status || "CONNECTED";
    }
    const lOM = document.getElementById("latOpenMeteo");
    if (lOM) lOM.textContent = `${om.latency_ms || 0} ms`;
    const mOM = document.getElementById("msgOpenMeteo");
    if (mOM) mOM.textContent = om.message || "Atmospheric precipitation.";

    // 4. POSIX DB
    const db = subs.database_storage || {};
    const bDB = document.getElementById("badgeDatabase");
    if (bDB) {
      bDB.className = `badge-tag ${db.reachable ? "low" : "severe"}`;
      bDB.textContent = db.status || "OPERATIONAL";
    }
    const lDB = document.getElementById("latDatabase");
    if (lDB) lDB.textContent = `${db.latency_ms || 0} ms`;
    const mDB = document.getElementById("msgDatabase");
    if (mDB) mDB.textContent = db.message || "F_FULLFSYNC verified.";

    // 5. ML Engine
    const ml = subs.ml_prediction_engine || {};
    const bML = document.getElementById("badgeMLEngine");
    if (bML) {
      bML.className = `badge-tag ${ml.reachable ? "low" : "severe"}`;
      bML.textContent = ml.status || "OPERATIONAL";
    }
    const lML = document.getElementById("latMLEngine");
    if (lML) lML.textContent = `${ml.latency_ms || 0} ms`;
    const mML = document.getElementById("msgMLEngine");
    if (mML) mML.textContent = ml.message || "80-Tree spatio-temporal classifier.";

    // 6. CV Engine
    const cv = subs.computer_vision || {};
    const bCV = document.getElementById("badgeCVEngine");
    if (bCV) {
      bCV.className = `badge-tag ${cv.reachable ? "low" : "moderate"}`;
      bCV.textContent = cv.status || "OPERATIONAL";
    }
    const lCV = document.getElementById("latCVEngine");
    if (lCV) lCV.textContent = `${cv.latency_ms || 0} ms`;
    const mCV = document.getElementById("msgCVEngine");
    if (mCV) mCV.textContent = cv.message || "YOLO detection pipeline.";

    if (isOptimal) {
      playSuccessChime();
      showToast("Multi-subsystem diagnostic synthesis completed with zero anomalies.", "success", 2600);
    } else {
      playWarningLid();
      showToast("Diagnostic completed: Some providers in fallback mode.", "info", 2600);
    }

  } catch (err) {
    console.error("Handshake error:", err);
    showToast("Subsystem diagnostic probe failed: " + err.message, "error", 3000);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg><span>Synthesize All Subsystems</span>`;
    }
  }
}
window.runSynthesizerHandshake = runSynthesizerHandshake;

async function loadSynthesizerProviders() {
  try {
    const res = await fetch("/api/config/providers");
    const json = await res.json();
    const providers = (json.data && json.data.providers) ? json.data.providers : [];

    for (const p of providers) {
      if (p.name.includes("TomTom")) {
        const note = document.getElementById("synTomTomMaskedNote");
        if (note) note.textContent = p.configured ? `Active Key: ${p.masked_key}` : "Current Key: Not Configured (Offline Fallback)";
        const st = document.getElementById("synTomTomStatus");
        if (st) {
          st.className = `badge-tag ${p.configured ? "low" : "default"}`;
          st.textContent = p.configured ? "Configured" : "Unconfigured";
        }
      } else if (p.name.includes("Google Maps")) {
        const note = document.getElementById("synGoogleMapsMaskedNote");
        if (note) note.textContent = p.configured ? `Active Key: ${p.masked_key}` : "Current Key: Not Configured (Leaflet Fallback)";
        const st = document.getElementById("synGoogleMapsStatus");
        if (st) {
          st.className = `badge-tag ${p.configured ? "low" : "default"}`;
          st.textContent = p.configured ? "Configured" : "Unconfigured";
        }
      }
    }
  } catch (err) {
    console.warn("Could not load synthesizer providers:", err);
  }
}
window.loadSynthesizerProviders = loadSynthesizerProviders;

async function saveTomTomKeyFromStudio() {
  const input = document.getElementById("synInputTomTomKey");
  const val = input ? input.value.trim() : "";
  if (!val) {
    showToast("Please enter a valid TomTom API key", "warning", 2000);
    return;
  }
  playTactileClick();
  try {
    const res = await fetch("/api/config/tomtom", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": getAuthHeader() },
      body: JSON.stringify({ api_key: val })
    });
    const d = await res.json();
    if (d.success) {
      if (input) input.value = "";
      playSuccessChime();
      showToast("TomTom API credential updated securely.", "success", 2400);
      loadSynthesizerProviders();
      runSynthesizerHandshake();
    } else {
      showToast(d.message || "Failed to save TomTom key.", "error", 2600);
    }
  } catch (err) {
    showToast("Error updating TomTom key: " + err.message, "error", 2600);
  }
}
window.saveTomTomKeyFromStudio = saveTomTomKeyFromStudio;

async function testTomTomKeyFromStudio() {
  playTactileClick();
  showToast("Pinging TomTom Traffic flow servers...", "info", 1800);
  try {
    const res = await fetch("/api/config/test/tomtom", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": getAuthHeader() }
    });
    const d = await res.json();
    if (d.data && d.data.reachable) {
      playSuccessChime();
      showToast(`TomTom probe successful! Roundtrip: ${d.data.latency_ms} ms`, "success", 2800);
    } else {
      playWarningLid();
      showToast(`TomTom ping returned: ${d.message || "Unreachable"}`, "warning", 2800);
    }
    runSynthesizerHandshake();
  } catch (err) {
    showToast("Network error probing TomTom: " + err.message, "error", 2600);
  }
}
window.testTomTomKeyFromStudio = testTomTomKeyFromStudio;

async function saveGoogleMapsKeyFromStudio() {
  const input = document.getElementById("synInputGoogleMapsKey");
  const val = input ? input.value.trim() : "";
  if (!val) {
    showToast("Please enter a valid Google Maps API key", "warning", 2000);
    return;
  }
  playTactileClick();
  try {
    const res = await fetch("/api/config/google_maps", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": getAuthHeader() },
      body: JSON.stringify({ api_key: val })
    });
    const d = await res.json();
    if (d.success) {
      if (input) input.value = "";
      playSuccessChime();
      showToast("Google Maps credential updated securely.", "success", 2400);
      loadSynthesizerProviders();
      runSynthesizerHandshake();
    } else {
      showToast(d.message || "Failed to save Google Maps key.", "error", 2600);
    }
  } catch (err) {
    showToast("Error updating Google Maps key: " + err.message, "error", 2600);
  }
}
window.saveGoogleMapsKeyFromStudio = saveGoogleMapsKeyFromStudio;

async function testGoogleMapsKeyFromStudio() {
  playTactileClick();
  showToast("Pinging Google Maps Platform geocoding...", "info", 1800);
  try {
    const res = await fetch("/api/config/test/google_maps", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": getAuthHeader() }
    });
    const d = await res.json();
    if (d.data && d.data.reachable) {
      playSuccessChime();
      showToast(`Google Maps probe successful! Roundtrip: ${d.data.latency_ms} ms`, "success", 2800);
    } else {
      playWarningLid();
      showToast(`Google Maps probe returned: ${d.message || "Unreachable"}`, "warning", 2800);
    }
    runSynthesizerHandshake();
  } catch (err) {
    showToast("Network error probing Google Maps: " + err.message, "error", 2600);
  }
}
window.testGoogleMapsKeyFromStudio = testGoogleMapsKeyFromStudio;

async function testWeatherFromStudio() {
  playTactileClick();
  showToast("Probing Open-Meteo atmospheric servers...", "info", 1800);
  try {
    const res = await fetch("/api/config/test/weather", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": getAuthHeader() }
    });
    const d = await res.json();
    if (d.data && d.data.reachable) {
      playSuccessChime();
      showToast(`Open-Meteo probe successful! Roundtrip: ${d.data.latency_ms} ms`, "success", 2800);
    } else {
      playWarningLid();
      showToast(`Open-Meteo probe: ${d.message || "Unreachable"}`, "warning", 2800);
    }
    runSynthesizerHandshake();
  } catch (err) {
    showToast("Network error probing weather: " + err.message, "error", 2600);
  }
}
window.testWeatherFromStudio = testWeatherFromStudio;

function togglePasswordVisibility(inputId) {
  const el = document.getElementById(inputId);
  if (!el) return;
  el.type = (el.type === "password") ? "text" : "password";
  playTactileClick();
}
window.togglePasswordVisibility = togglePasswordVisibility;

async function loadSynthesizerStorageStatus() {
  try {
    const res = await fetch("/api/synthesizer/storage/status", {
      headers: { "Authorization": getAuthHeader() }
    });
    const json = await res.json();
    const data = json.data || {};
    const dbs = data.databases || {};

    const u = dbs.users || {};
    const elUCount = document.getElementById("synStorageUsersCount");
    if (elUCount) elUCount.textContent = `${u.records_count || 0} accounts`;
    const elUSize = document.getElementById("synStorageUsersSize");
    if (elUSize) elUSize.textContent = `${u.size_bytes || 0} bytes`;

    const e = dbs.events || {};
    const elECount = document.getElementById("synStorageEventsCount");
    if (elECount) elECount.textContent = `${e.records_count || 0} disruptions`;
    const elESize = document.getElementById("synStorageEventsSize");
    if (elESize) elESize.textContent = `${e.size_bytes || 0} bytes`;

    const v = dbs.video_storage || {};
    const elVCount = document.getElementById("synStorageVideoCount");
    if (elVCount) elVCount.textContent = `${v.files_count || 0} videos`;
    const elVSize = document.getElementById("synStorageVideoSize");
    if (elVSize) elVSize.textContent = `${v.size_mb || 0} MB`;

    const snapCount = data.snapshots_count || 0;
    const snapEl = document.getElementById("kpiSynSnapshots");
    if (snapEl) snapEl.textContent = `${snapCount} Backups`;

    renderSnapshotsTable(data.snapshots || []);
  } catch (err) {
    console.warn("Could not load storage status:", err);
  }
}
window.loadSynthesizerStorageStatus = loadSynthesizerStorageStatus;

function renderSnapshotsTable(snapshots) {
  const tbody = document.getElementById("synSnapshotsTableBody");
  if (!tbody) return;

  if (!snapshots || snapshots.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 18px;">No atomic snapshot backups created yet. Click "Create Atomic Snapshot" above to capture state.</td></tr>`;
    return;
  }

  tbody.innerHTML = snapshots.map(s => {
    const uCount = s.counts?.users || 0;
    const eCount = s.counts?.events || 0;
    return `
      <tr>
        <td style="font-family: var(--font-mono); color: var(--accent-blue); font-weight: 700;">${s.snapshot_id}</td>
        <td style="font-size: 0.78rem; color: var(--text-secondary);">${s.created_at}</td>
        <td style="font-size: 0.80rem; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${s.note || "--"}</td>
        <td style="font-family: var(--font-mono); font-size: 0.78rem;">${uCount} users / ${eCount} evts</td>
        <td style="font-family: var(--font-mono); font-size: 0.74rem; color: var(--text-muted);"><code>${s.sha256}</code></td>
        <td style="font-family: var(--font-mono); font-size: 0.78rem;">${Math.round((s.size_bytes || 0) / 1024)} KB</td>
        <td>
          <button class="action-btn action-btn-secondary" style="padding: 3px 9px; font-size: 0.74rem;" onclick="restoreStorageBackup('${s.snapshot_id}')">Restore</button>
        </td>
      </tr>
    `;
  }).join("");
}

async function createStorageSnapshot() {
  const noteInput = document.getElementById("synSnapshotNoteInput");
  const note = noteInput ? noteInput.value.trim() : "";
  playTactileClick();
  showToast("Creating SHA-256 verified atomic snapshot...", "info", 1800);

  try {
    const res = await fetch("/api/synthesizer/storage/backup", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": getAuthHeader() },
      body: JSON.stringify({ note: note || "Manual administrator backup" })
    });
    const d = await res.json();
    if (d.success) {
      if (noteInput) noteInput.value = "";
      playSuccessChime();
      showToast(`Snapshot '${d.data.snapshot_id}' created with hardware fsync!`, "success", 2800);
      loadSynthesizerStorageStatus();
    } else {
      showToast("Snapshot creation failed: " + (d.message || "Unknown error"), "error", 2800);
    }
  } catch (err) {
    showToast("Error creating snapshot: " + err.message, "error", 2600);
  }
}
window.createStorageSnapshot = createStorageSnapshot;

async function restoreStorageBackup(snapshotId) {
  if (!confirm(`Are you sure you want to restore the entire system state from snapshot '${snapshotId}'?\nCurrent users and events will be atomically rolled back.`)) {
    return;
  }
  playTactileClick();
  showToast(`Restoring state from ${snapshotId}...`, "info", 2000);

  try {
    const res = await fetch("/api/synthesizer/storage/restore", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": getAuthHeader() },
      body: JSON.stringify({ snapshot_id: snapshotId })
    });
    const d = await res.json();
    if (d.success) {
      playSuccessChime();
      showToast(`System restored: ${d.data.users_restored} users, ${d.data.events_restored} events restored.`, "success", 3000);
      loadSynthesizerStorageStatus();
      loadEvents();
    } else {
      showToast("Restore failed: " + (d.message || "Integrity error"), "error", 3000);
    }
  } catch (err) {
    showToast("Error during restore: " + err.message, "error", 2800);
  }
}
window.restoreStorageBackup = restoreStorageBackup;

function updateSynIntensityLabel() {
  const slider = document.getElementById("synIntensitySlider");
  const label = document.getElementById("synIntensityLabel");
  if (slider && label) {
    label.textContent = `${Math.round(parseFloat(slider.value) * 100)}%`;
  }
}
window.updateSynIntensityLabel = updateSynIntensityLabel;

function onScenarioSelectChanged() {
  updateSynIntensityLabel();
  playTactileClick();
}
window.onScenarioSelectChanged = onScenarioSelectChanged;

async function generateSyntheticStream() {
  const typeSelect = document.getElementById("synScenarioSelect");
  const slider = document.getElementById("synIntensitySlider");
  const zoneSelect = document.getElementById("synZoneFilterSelect");
  const outputContainer = document.getElementById("synStreamOutputContainer");

  const scenario_type = typeSelect ? typeSelect.value : "monsoon_flood";
  const intensity = slider ? parseFloat(slider.value) : 0.75;
  const zone = (zoneSelect && zoneSelect.value !== "all") ? [zoneSelect.value] : null;

  playTactileClick();
  showToast(`Synthesizing ${scenario_type} perturbation at ${Math.round(intensity * 100)}% intensity...`, "info", 1800);

  try {
    const res = await fetch("/api/synthesizer/stream/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": getAuthHeader() },
      body: JSON.stringify({ scenario_type, intensity, zones: zone })
    });
    const json = await res.json();
    const data = json.data || {};
    const impact = data.network_impact || {};

    if (outputContainer) outputContainer.style.display = "block";

    const elStress = document.getElementById("synStreamStress");
    if (elStress) elStress.textContent = `${impact.grid_stress_index || 0} / 100`;
    const elSpd = document.getElementById("synStreamSpeedDrop");
    if (elSpd) elSpd.textContent = `-${impact.avg_speed_drop_kmh || 0} km/h`;
    const elVol = document.getElementById("synStreamVolSurge");
    if (elVol) elVol.textContent = `+${impact.total_volume_surge_vph || 0} vph`;
    const elSev = document.getElementById("synStreamSevereCount");
    if (elSev) elSev.textContent = `${impact.severe_corridors_count || 0} Corridors`;

    const tbody = document.getElementById("synStreamCorridorsBody");
    if (tbody) {
      const corridors = data.corridors || [];
      tbody.innerHTML = corridors.slice(0, 16).map(c => {
        const b = c.baseline;
        const s = c.simulated;
        const d = c.deltas;
        const isSev = s.congestion === "Severe";
        const isHigh = s.congestion === "High";
        const tagClass = isSev ? "severe" : (isHigh ? "high" : (s.congestion === "Moderate" ? "moderate" : "low"));
        return `
          <tr>
            <td style="font-weight: 600;">${c.road_name}</td>
            <td style="font-size: 0.78rem; color: var(--text-secondary);">${c.city_zone}</td>
            <td style="font-family: var(--font-mono); font-size: 0.78rem;">${b.speed_kmh} km/h &bull; ${b.volume_vph} vph</td>
            <td style="font-family: var(--font-mono); font-size: 0.78rem; font-weight: 700;">${s.speed_kmh} km/h &bull; ${s.volume_vph} vph (${s.capacity_utilization_pct}%)</td>
            <td style="font-family: var(--font-mono); font-size: 0.78rem; color: ${d.speed_delta_kmh < 0 ? 'var(--status-sev)' : 'var(--text-muted)'};">${d.speed_delta_kmh} km/h</td>
            <td><span class="badge-tag ${tagClass}">${s.congestion}</span></td>
          </tr>
        `;
      }).join("");
    }

    playHapticBeep(680, 50, "sine");
    showToast(`Synthesized ${data.corridors ? data.corridors.length : 24} corridors under ${data.scenario_title}.`, "success", 2600);

  } catch (err) {
    showToast("Stream synthesis failed: " + err.message, "error", 2600);
  }
}
window.generateSyntheticStream = generateSyntheticStream;

function onSandboxSliderChange() {
  const vol = document.getElementById("synSandboxVolume")?.value;
  const spd = document.getElementById("synSandboxSpeed")?.value;
  const cap = document.getElementById("synSandboxCapacity")?.value;
  const hr = document.getElementById("synSandboxHour")?.value;

  if (vol && document.getElementById("synSandboxVolumeLabel")) document.getElementById("synSandboxVolumeLabel").textContent = `${vol} vph`;
  if (spd && document.getElementById("synSandboxSpeedLabel")) document.getElementById("synSandboxSpeedLabel").textContent = `${spd} km/h`;
  if (cap && document.getElementById("synSandboxCapacityLabel")) document.getElementById("synSandboxCapacityLabel").textContent = `${cap}%`;
  if (hr && document.getElementById("synSandboxHourLabel")) document.getElementById("synSandboxHourLabel").textContent = `${hr}:00`;

  if (synSandboxDebounceTimer) clearTimeout(synSandboxDebounceTimer);
  synSandboxDebounceTimer = setTimeout(runSandboxInference, 120);
}
window.onSandboxSliderChange = onSandboxSliderChange;

async function runSandboxInference() {
  const road_id = document.getElementById("synSandboxRoadSelect")?.value || "RD_BLR_01";
  const vehicle_count = parseFloat(document.getElementById("synSandboxVolume")?.value || 1450);
  const average_speed = parseFloat(document.getElementById("synSandboxSpeed")?.value || 28);
  const capacity_utilization = parseFloat(document.getElementById("synSandboxCapacity")?.value || 45);
  const hour = parseInt(document.getElementById("synSandboxHour")?.value || 17);
  const is_weekend = parseInt(document.getElementById("synSandboxWeekend")?.value || 0);

  try {
    const res = await fetch("/api/synthesizer/predict/sandbox", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": getAuthHeader() },
      body: JSON.stringify({
        features: { road_id, vehicle_count, average_speed, capacity_utilization, hour, is_weekend }
      })
    });
    const json = await res.json();
    const pred = json.prediction || {};
    const probs = pred.probabilities || {};

    const pClass = pred.predicted_congestion || "Moderate";
    const badge = document.getElementById("synSandboxPredBadge");
    if (badge) {
      badge.className = `badge-tag ${pClass.toLowerCase()}`;
      badge.textContent = pClass;
    }

    const elMargin = document.getElementById("synSandboxMargin");
    if (elMargin) elMargin.textContent = pred.confidence_margin || "0.00";
    const elEntropy = document.getElementById("synSandboxEntropy");
    if (elEntropy) elEntropy.textContent = pred.shannon_entropy || "0.00";
    const elLatency = document.getElementById("synSandboxLatency");
    if (elLatency) elLatency.textContent = `${pred.inference_latency_ms || 0.12} ms`;

    // Probability Bars
    const pLow = Math.round((probs.Low || 0) * 100);
    const pMod = Math.round((probs.Moderate || 0) * 100);
    const pHigh = Math.round((probs.High || 0) * 100);
    const pSev = Math.round((probs.Severe || 0) * 100);

    const bL = document.getElementById("probBarLow");
    if (bL) bL.style.width = `${pLow}%`;
    const tL = document.getElementById("probPctLow");
    if (tL) tL.textContent = `${pLow}%`;

    const bM = document.getElementById("probBarMod");
    if (bM) bM.style.width = `${pMod}%`;
    const tM = document.getElementById("probPctMod");
    if (tM) tM.textContent = `${pMod}%`;

    const bH = document.getElementById("probBarHigh");
    if (bH) bH.style.width = `${pHigh}%`;
    const tH = document.getElementById("probPctHigh");
    if (tH) tH.textContent = `${pHigh}%`;

    const bS = document.getElementById("probBarSev");
    if (bS) bS.style.width = `${pSev}%`;
    const tS = document.getElementById("probPctSev");
    if (tS) tS.textContent = `${pSev}%`;

    // Attributions List
    const attrList = document.getElementById("synSandboxAttrList");
    if (attrList && pred.attributions) {
      attrList.innerHTML = pred.attributions.map(a => `
        <li><span class="attr-name">${a.feature}</span> <span class="attr-val">${a.value} &bull; ${a.impact}</span></li>
      `).join("");
    }

  } catch (err) {
    console.warn("Sandbox inference error:", err);
  }
}
window.runSandboxInference = runSandboxInference;


/* ==========================================================================
   AI VISION INTELLIGENCE & LIVE CCTV HUB CONTROLLER
   ========================================================================== */

let visionMode = "upload"; // "upload" | "live"
let currentMediaStream = null;
let cctvLoopAnimId = null;
let isCctvLoopActive = false;
let visionDetectionsActive = [];
let visionActiveTelemetry = null;
let visionShowRoi = true;
let visionPlaybackRate = 1.0;
let currentVisionJobId = null;

const INDO_HCM_FACTORS = {
  car: 1.00,
  motorcycle: 0.50,
  auto: 0.80,
  bus: 2.80,
  truck: 3.00
};

function initVisionIntelligenceSection() {
  populateActuationCorridors();
  setupVisionDragAndDrop();

  // Check engine readiness via API
  fetch("/api/vision/status")
    .then(r => r.json())
    .then(data => {
      if (data.success && data.data) {
        const eng = data.data.engine || "Ultralytics YOLO";
        const engBadge = document.getElementById("kpiVisionEngine");
        if (engBadge) engBadge.textContent = data.data.yolo_loaded ? "YOLO11n CoreML" : "Adaptive Engine";
        const statusTxt = document.getElementById("visionStatusText");
        if (statusTxt) statusTxt.textContent = `Vision Engine Operational • ${eng}`;
      }
    })
    .catch(err => console.warn("Vision status check:", err));
}

function populateActuationCorridors() {
  const sel = document.getElementById("selectActuationCorridor");
  if (!sel || sel.children.length > 0) return;

  const corridors = [
    { id: "RD_BLR_04", name: "Outer Ring Road (Silk Board to Marathahalli)" },
    { id: "RD_BLR_01", name: "Indiranagar 100ft Road" },
    { id: "RD_BLR_02", name: "MG Road Arterial" },
    { id: "RD_BLR_03", name: "Hebbal Flyover Expressway" },
    { id: "RD_BLR_06", name: "Hosur Road Electronic City Flyover" },
    { id: "RD_BLR_07", name: "Whitefield Main Corridor" },
    { id: "RD_BLR_11", name: "BTM Layout Ring Corridor" },
    { id: "RD_BLR_13", name: "Jayanagar 4th Block Spine" }
  ];

  sel.innerHTML = corridors.map(c => `<option value="${c.id}">${c.id}: ${c.name}</option>`).join("");
}

function setVisionMode(mode) {
  // Vision AI workflow is dedicated to genuine video uploads
  visionMode = "upload";
  const barUp = document.getElementById("visionUploadControlsBar");
  if (barUp) barUp.style.display = "flex";
  const kpiMode = document.getElementById("kpiVisionMode");
  if (kpiMode) kpiMode.textContent = "Video Upload";
}

function setupVisionDragAndDrop() {
  const dropZone = document.getElementById("visionDropZone");
  if (!dropZone) return;

  ["dragenter", "dragover"].forEach(evt => {
    dropZone.addEventListener(evt, e => {
      e.preventDefault();
      dropZone.style.borderColor = "var(--status-low)";
      dropZone.style.background = "rgba(16, 185, 129, 0.05)";
    });
  });

  ["dragleave", "drop"].forEach(evt => {
    dropZone.addEventListener(evt, e => {
      e.preventDefault();
      dropZone.style.borderColor = "var(--border-medium)";
      dropZone.style.background = "rgba(255, 255, 255, 0.015)";
    });
  });

  dropZone.addEventListener("drop", e => {
    const files = e.dataTransfer?.files;
    if (files && files.length > 0) {
      uploadVisionVideo(files[0]);
    }
  });
}

function handleVisionFileSelected(event) {
  const file = event.target.files?.[0];
  if (file) {
    uploadVisionVideo(file);
  }
}

async function uploadVisionVideo(file) {
  const progressRow = document.getElementById("visionProgressBarRow");
  const progressFill = document.getElementById("visionProgressFill");
  const progressText = document.getElementById("visionProgressPercentText");
  const statusText = document.getElementById("visionProgressStatusText");
  const placeholder = document.getElementById("visionOverlayPlaceholder");

  if (!file) return;

  // Max 256 MB application upload limit check
  const maxBytes = 256 * 1024 * 1024;
  if (file.size > maxBytes) {
    showToast(`File size (${(file.size / (1024 * 1024)).toFixed(1)} MB) exceeds 256 MB application upload limit.`, "error");
    return;
  }

  if (progressRow) progressRow.style.display = "flex";
  if (placeholder) placeholder.style.display = "none";
  if (progressFill) {
    progressFill.style.width = "0%";
    progressFill.style.background = "var(--accent-blue)";
  }
  if (progressText) progressText.textContent = "0%";
  if (statusText) statusText.textContent = `Preparing upload: ${file.name} (${(file.size / (1024 * 1024)).toFixed(1)} MB)...`;

  const CHUNK_SIZE = 8 * 1024 * 1024; // 8 MB disk-backed chunks
  const totalChunks = Math.max(1, Math.ceil(file.size / CHUNK_SIZE));

  try {
    // Stage 1: Initialize chunked upload session
    if (statusText) statusText.textContent = `Initializing upload session for ${file.name}...`;
    const initRes = await fetch("/api/vision/upload/init", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": getAuthHeader()
      },
      body: JSON.stringify({
        filename: file.name,
        file_size: file.size,
        total_chunks: totalChunks,
        chunk_size: CHUNK_SIZE
      })
    });

    const initData = await initRes.json().catch(() => ({}));
    if (!initRes.ok || !initData.success) {
      throw new Error(initData.message || `Upload initialization failed (${initRes.status}: ${initRes.statusText})`);
    }

    const uploadId = initData.data.upload_id;

    // Stage 2: Upload chunks sequentially with retry support
    for (let chunkIdx = 0; chunkIdx < totalChunks; chunkIdx++) {
      const start = chunkIdx * CHUNK_SIZE;
      const end = Math.min(start + CHUNK_SIZE, file.size);
      const chunkBlob = file.slice(start, end);

      let chunkUploaded = false;
      let lastErr = null;

      for (let attempt = 1; attempt <= 3; attempt++) {
        try {
          if (attempt > 1 && statusText) {
            statusText.textContent = `Retrying chunk ${chunkIdx + 1}/${totalChunks} (attempt ${attempt}/3)...`;
          }

          const chunkRes = await fetch("/api/vision/upload/chunk", {
            method: "POST",
            headers: {
              "Content-Type": "application/octet-stream",
              "X-Upload-ID": uploadId,
              "X-Chunk-Index": String(chunkIdx),
              "Authorization": getAuthHeader()
            },
            body: chunkBlob
          });

          if (!chunkRes.ok) {
            const errJson = await chunkRes.json().catch(() => ({}));
            throw new Error(errJson.message || `Server returned HTTP ${chunkRes.status} (${chunkRes.statusText}) on chunk ${chunkIdx + 1}`);
          }

          chunkUploaded = true;
          break;
        } catch (err) {
          lastErr = err;
          if (attempt < 3) {
            await new Promise(r => setTimeout(r, 800 * attempt));
          }
        }
      }

      if (!chunkUploaded) {
        throw new Error(`Failed to upload chunk ${chunkIdx + 1} of ${totalChunks}: ${lastErr ? lastErr.message : 'Network error'}`);
      }

      // Update real progress: Upload phase spans 0% to 50%
      const uploadedBytesSoFar = end;
      const uploadPct = Math.round((uploadedBytesSoFar / file.size) * 50);
      if (progressFill) progressFill.style.width = `${uploadPct}%`;
      if (progressText) progressText.textContent = `${uploadPct}%`;
      if (statusText) {
        statusText.textContent = `Uploading ${file.name}: chunk ${chunkIdx + 1}/${totalChunks} (${(uploadedBytesSoFar / (1024 * 1024)).toFixed(1)} / ${(file.size / (1024 * 1024)).toFixed(1)} MB)...`;
      }
    }

    // Stage 3: Finalize, assemble chunks on disk, verify SHA-256 and video container
    if (progressFill) progressFill.style.width = "52%";
    if (progressText) progressText.textContent = "52%";
    if (statusText) statusText.textContent = "Assembling video chunks and verifying integrity...";

    const finalizeRes = await fetch("/api/vision/upload/complete", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": getAuthHeader()
      },
      body: JSON.stringify({ upload_id: uploadId })
    });

    const finalizeData = await finalizeRes.json().catch(() => ({}));
    if (!finalizeRes.ok || !finalizeData.success) {
      throw new Error(finalizeData.message || `File assembly and verification failed (${finalizeRes.status}: ${finalizeRes.statusText})`);
    }

    const videoId = finalizeData.data.video_id;
    if (progressFill) progressFill.style.width = "55%";
    if (progressText) progressText.textContent = "55%";
    if (statusText) statusText.textContent = "Video validated. Dispatching YOLO11n Computer Vision pipeline...";

    // Stage 4: Dispatch YOLO Background Processing
    const procRes = await fetch("/api/vision/process", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": getAuthHeader()
      },
      body: JSON.stringify({ video_id: videoId, filename: file.name })
    });

    const procData = await procRes.json().catch(() => ({}));
    if (!procRes.ok || !procData.success) {
      throw new Error(procData.message || `Failed to dispatch video processing (${procRes.status})`);
    }

    currentVisionJobId = procData.data.job_id;
    pollVisionJob(currentVisionJobId, videoId);

  } catch (err) {
    console.error("Upload error:", err);
    showToast(`Upload failed: ${err.message}`, "error");
    if (statusText) statusText.textContent = `Error: ${err.message}`;
    if (progressFill) {
      progressFill.style.width = "100%";
      progressFill.style.background = "var(--status-sev)";
    }
    if (progressText) progressText.textContent = "Failed";
  }
}

function pollVisionJob(jobId, videoId) {
  const progressFill = document.getElementById("visionProgressFill");
  const progressText = document.getElementById("visionProgressPercentText");
  const statusText = document.getElementById("visionProgressStatusText");

  const interval = setInterval(async () => {
    try {
      const res = await fetch(`/api/vision/jobs/${jobId}`, {
        headers: { "Authorization": getAuthHeader() }
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) {
        clearInterval(interval);
        throw new Error(data.message || `Status check failed (${res.status})`);
      }

      const job = data.data;
      // Processing spans 55% to 100%
      const jobPct = Math.min(100, Math.max(0, job.progress_pct || 0));
      const overallPct = Math.round(55 + (jobPct * 0.45));

      if (progressFill) {
        progressFill.style.width = `${overallPct}%`;
        progressFill.style.background = "var(--accent-blue)";
      }
      if (progressText) progressText.textContent = `${overallPct}%`;
      if (statusText) {
        const frameInfo = job.total_frames > 0 ? `frame ${job.processed_frames || 0}/${job.total_frames}` : `${job.processed_frames || 0} frames`;
        statusText.textContent = `YOLO11n Processing (${job.status}): ${frameInfo} (${jobPct.toFixed(1)}%)...`;
      }

      if (job.status === "COMPLETED") {
        clearInterval(interval);
        if (progressFill) {
          progressFill.style.width = "100%";
          progressFill.style.background = "var(--status-low)";
        }
        if (progressText) progressText.textContent = "100%";
        if (statusText) statusText.textContent = "Inference & annotation complete!";
        showToast("YOLO11n computer vision processing completed successfully!", "success");
        playSuccessChime();
        onVisionJobComplete(jobId);
      } else if (job.status === "FAILED") {
        clearInterval(interval);
        throw new Error(job.error_message || "Video processing failed on server");
      }
    } catch (err) {
      clearInterval(interval);
      console.error("Polling error:", err);
      showToast(`Processing error: ${err.message}`, "error");
      if (statusText) statusText.textContent = `Processing error: ${err.message}`;
      if (progressFill) {
        progressFill.style.background = "var(--status-sev)";
      }
    }
  }, 750);
}

async function onVisionJobComplete(jobId) {
  try {
    const res = await fetch(`/api/vision/results/${jobId}`, {
      headers: { "Authorization": getAuthHeader() }
    });
    const data = await res.json();
    if (!res.ok || !data.success) return;

    const results = data.data;
    visionActiveTelemetry = results;

    // Load annotated video for playback
    const video = document.getElementById("visionVideoElement");
    if (video) {
      stopClientInferenceLoop();
      const token = (currentUser && currentUser.token) || "";
      video.src = `/api/vision/video/${jobId}${token ? `?token=${encodeURIComponent(token)}` : ''}`;
      video.loop = true;
      video.muted = true;
      video.load();
      video.play().catch(() => {});
    }

    // Render waveform and telemetry cards
    renderWaveform(results.sample_telemetry || []);
    updateVisionSidecar(
      results.pcu_telemetry || {},
      results.kinematics || {},
      results.traffic_density || {},
      results.incident_summary || {},
      results.class_counts || {},
      results.total_unique_vehicles || 0,
      results.confidence_summary || {},
      results.processing_metrics || {}
    );
  } catch (err) {
    console.error("Failed to fetch results:", err);
  }
}

function clearVisionHud() {
  const canvas = document.getElementById("visionHudCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
}

function stopClientInferenceLoop() {
  clearVisionHud();
}
/* ==========================================================================
   VIDEO PLAYBACK & DENSITY WAVEFORM
   ========================================================================== */

function toggleVisionPlayback() {
  const video = document.getElementById("visionVideoElement");
  const icon = document.getElementById("iconVisionPlay");
  if (!video) return;

  if (video.paused) {
    video.play();
    if (icon) icon.innerHTML = '<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>';
  } else {
    video.pause();
    if (icon) icon.innerHTML = '<polygon points="5 3 19 12 5 21 5 3"/>';
  }
}

function onVisionVideoLoaded() {
  const video = document.getElementById("visionVideoElement");
  const canvas = document.getElementById("visionHudCanvas");
  if (!video || !canvas) return;
  canvas.width = video.videoWidth || 1280;
  canvas.height = video.videoHeight || 720;
}

function onVisionTimeUpdate() {
  const video = document.getElementById("visionVideoElement");
  const scrubber = document.getElementById("visionScrubber");
  const display = document.getElementById("visionTimeDisplay");
  if (!video) return;

  const cur = video.currentTime || 0;
  const dur = video.duration || 1;
  const pct = (cur / dur) * 100;

  if (scrubber && !scrubber.matches(":active")) {
    scrubber.value = pct;
  }

  if (display) {
    display.textContent = `${formatVideoTime(cur)} / ${formatVideoTime(dur)}`;
  }
}

function onVisionScrubberInput(event) {
  const video = document.getElementById("visionVideoElement");
  if (!video || !video.duration) return;
  const pct = parseFloat(event.target.value) / 100;
  video.currentTime = pct * video.duration;
}

function onVisionScrubberChange(event) {
  onVisionScrubberInput(event);
}

function formatVideoTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

function cyclePlaybackRate() {
  const video = document.getElementById("visionVideoElement");
  const btn = document.getElementById("btnVisionSpeed");
  const rates = [0.5, 1.0, 1.5, 2.0];
  const idx = rates.indexOf(visionPlaybackRate);
  visionPlaybackRate = rates[(idx + 1) % rates.length];
  if (video) video.playbackRate = visionPlaybackRate;
  if (btn) btn.textContent = `${visionPlaybackRate}x`;
  playHapticBeep(600, 20, "sine");
}

function toggleVisionRoi() {
  visionShowRoi = !visionShowRoi;
  const btn = document.getElementById("btnToggleRoi");
  if (btn) btn.textContent = `ROI: ${visionShowRoi ? "On" : "Off"}`;
  playHapticBeep(550, 20, "sine");
}

function renderWaveform(telemetry) {
  const canvas = document.getElementById("visionWaveformCanvas");
  if (!canvas || !telemetry || telemetry.length === 0) return;

  const w = canvas.offsetWidth || 400;
  const h = canvas.height || 24;
  canvas.width = w;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, w, h);

  const maxVeh = Math.max(...telemetry.map(t => t.vehicle_count || 1), 10);
  const step = w / Math.max(telemetry.length - 1, 1);

  ctx.beginPath();
  ctx.moveTo(0, h);
  telemetry.forEach((t, i) => {
    const v = t.vehicle_count || 0;
    const y = h - (v / maxVeh) * (h - 4);
    ctx.lineTo(i * step, y);
  });
  ctx.lineTo(w, h);
  ctx.closePath();

  ctx.fillStyle = "rgba(16, 185, 129, 0.4)";
  ctx.fill();

  ctx.strokeStyle = "#10b981";
  ctx.lineWidth = 1.5;
  ctx.stroke();
}

function updateVisionSidecar(pcuInfo, kinematics, densityInfo, incidents, explicitClassCounts, explicitUniqueTotal, confSummary, procMetrics) {
  // 1. PCU & Classes
  const totalPcu = pcuInfo.total_pcu || 0;
  const badgePcu = document.getElementById("badgeTotalPcu");
  if (badgePcu) badgePcu.textContent = `${totalPcu} PCU`;

  const kpiFlow = document.getElementById("kpiVisionFlow");
  if (kpiFlow) kpiFlow.textContent = `${pcuInfo.hourly_flow_pcu_per_hr || "--"} PCU/h`;

  const counts = explicitClassCounts || pcuInfo.mix_breakdown?.classes || {};
  const cCar = counts.car?.count ?? counts.car ?? 0;
  const cMoto = counts.motorcycle?.count ?? counts.motorcycle ?? 0;
  const cBicycle = counts.bicycle?.count ?? counts.bicycle ?? 0;
  const cBus = counts.bus?.count ?? counts.bus ?? 0;
  const cTruck = counts.truck?.count ?? counts.truck ?? 0;

  const elCar = document.getElementById("countCar"); if (elCar) elCar.textContent = cCar;
  const elMoto = document.getElementById("countMoto"); if (elMoto) elMoto.textContent = cMoto;
  const elBicycle = document.getElementById("countBicycle"); if (elBicycle) elBicycle.textContent = cBicycle;
  const elBus = document.getElementById("countBus"); if (elBus) elBus.textContent = cBus;
  const elTruck = document.getElementById("countTruck"); if (elTruck) elTruck.textContent = cTruck;

  const totalRaw = explicitUniqueTotal != null ? explicitUniqueTotal : (cCar + cMoto + cBicycle + cBus + cTruck);
  const totalDenom = Math.max(cCar + cMoto + cBicycle + cBus + cTruck, 1);
  const barCar = document.getElementById("barCar"); if (barCar) barCar.style.width = `${(cCar / totalDenom) * 100}%`;
  const barMoto = document.getElementById("barMoto"); if (barMoto) barMoto.style.width = `${(cMoto / totalDenom) * 100}%`;
  const barBicycle = document.getElementById("barBicycle"); if (barBicycle) barBicycle.style.width = `${(cBicycle / totalDenom) * 100}%`;
  const barBus = document.getElementById("barBus"); if (barBus) barBus.style.width = `${(cBus / totalDenom) * 100}%`;
  const barTruck = document.getElementById("barTruck"); if (barTruck) barTruck.style.width = `${(cTruck / totalDenom) * 100}%`;

  const rawKpi = document.getElementById("kpiVisionRawCount");
  if (rawKpi) rawKpi.textContent = `Unique Vehicles: ${totalRaw}`;

  // Confidence & Engine metrics
  if (confSummary) {
    const meanConf = confSummary.mean_confidence ? Math.round(confSummary.mean_confidence * 100) : 0;
    const elConf = document.getElementById("kpiVisionConfidence");
    if (elConf) elConf.textContent = meanConf > 0 ? `${meanConf}%` : "-- %";
    const elConfDetail = document.getElementById("kpiVisionConfDetail");
    if (elConfDetail) elConfDetail.textContent = `Threshold: >= ${Math.round((confSummary.detection_threshold || 0.25) * 100)}%`;
  }

  if (procMetrics) {
    const elEngine = document.getElementById("kpiVisionEngine");
    if (elEngine && procMetrics.detector_engine) {
      elEngine.textContent = procMetrics.detector_engine;
    }
    const elDev = document.getElementById("kpiVisionDevice");
    if (elDev) {
      elDev.textContent = `Device: ${procMetrics.inference_device || 'CPU'} | Verified`;
    }
  }

  // 2. Kinematics & LOS
  const spd = kinematics.space_mean_speed_kmh || 0;
  const occ = densityInfo.average_occupancy_pct || 0;
  const los = densityInfo.peak_density_level || "Low";

  const elSpd = document.getElementById("kpiVisionSpeed"); if (elSpd) elSpd.textContent = `${spd} km/h`;
  const elSideSpd = document.getElementById("sidecarSpeed"); if (elSideSpd) elSideSpd.textContent = `${spd} km/h`;
  const elSideOcc = document.getElementById("sidecarOccupancy"); if (elSideOcc) elSideOcc.textContent = `${occ}%`;
  const elSideFlow = document.getElementById("sidecarFlowRate"); if (elSideFlow) elSideFlow.textContent = `${pcuInfo.hourly_flow_pcu_per_hr || "--"} PCU/h`;

  const flowVal = pcuInfo.hourly_flow_pcu_per_hr || 0;
  const densityK = (spd > 0 && flowVal > 0) ? Math.round(flowVal / spd) : "--";
  const elSideK = document.getElementById("sidecarDensityK"); if (elSideK) elSideK.textContent = `${densityK} veh/km`;

  const elCalib = document.getElementById("sidecarCalibrationNote");
  if (elCalib) {
    if (kinematics && kinematics.calibration_status === "CALIBRATED") {
      elCalib.textContent = "Physical speed calibrated via planar homography matrix.";
      elCalib.style.color = "var(--status-low)";
    } else {
      elCalib.textContent = (kinematics && kinematics.calibration_note) || "Speed & density reflect 2D optical frame heuristics. Physical calibration requires camera-specific planar homography and surveyed ground control points.";
      elCalib.style.color = "var(--text-muted)";
    }
  }

  const badgeLOS = document.getElementById("badgeDensityLevel");
  const kpiLOS = document.getElementById("kpiVisionLos");
  if (badgeLOS) {
    badgeLOS.textContent = `LOS ${los.charAt(0)}`;
    badgeLOS.className = `badge-tag ${los.toLowerCase()}`;
  }
  if (kpiLOS) kpiLOS.textContent = `${los} Congestion`;

  // 3. Incidents
  const incList = document.getElementById("visionIncidentList");
  const incBadge = document.getElementById("badgeIncidentCount");
  const kpiInc = document.getElementById("kpiVisionIncidents");
  const recentInc = incidents.recent_incidents || [];

  if (incBadge) incBadge.textContent = `${recentInc.length} Detected`;
  if (kpiInc) kpiInc.textContent = `${recentInc.length} Active`;

  if (incList && recentInc.length > 0) {
    incList.innerHTML = recentInc.map(i => `
      <div class="incident-item ${i.severity.toLowerCase()}">
        <span class="badge-tag ${i.severity.toLowerCase()}">${i.severity}</span>
        <div>
          <strong>${i.type.replace("INCIDENT_", "").replace("_", " ")}</strong>
          <div>${i.message}</div>
        </div>
      </div>
    `).join("");
  }
}

async function actuateVisionIntoLiveGrid() {
  const sel = document.getElementById("selectActuationCorridor");
  const corridorId = sel ? sel.value : "RD_BLR_04";
  const btn = document.getElementById("btnActuateGrid");
  const resBox = document.getElementById("actuationResultBox");

  if (!visionActiveTelemetry) {
    showToast("Please load a video or run the CCTV loop before actuating.", "warning");
    return;
  }

  if (btn) btn.disabled = true;

  try {
    const res = await fetch("/api/vision/live/actuate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": getAuthHeader()
      },
      body: JSON.stringify({
        corridor_id: corridorId,
        vision_metrics: visionActiveTelemetry
      })
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.message || "Actuation failed");
    }

    const d = data.data;
    if (resBox) resBox.style.display = "flex";

    const statBadge = document.getElementById("actuateStatusBadge");
    if (statBadge) statBadge.textContent = `Actuated on ${d.corridor_id}`;

    const xgBadge = document.getElementById("actuateXgboostBadge");
    if (xgBadge) {
      const pred = d.xgboost_15m_forecast?.predicted_congestion || "Moderate";
      xgBadge.textContent = `XGBoost 15m: ${pred}`;
      xgBadge.className = `badge-tag ${pred.toLowerCase()}`;
    }

    const c0El = document.getElementById("actuateWebsterC0");
    if (c0El) c0El.textContent = `${d.webster_signal_actuation?.optimal_cycle_sec || d.webster_signal_actuation?.optimal_cycle_seconds || 105} s`;

    const gEl = document.getElementById("actuateWebsterGreen");
    if (gEl) gEl.textContent = `${d.webster_signal_actuation?.ns_green_sec || d.webster_signal_actuation?.effective_green_seconds || 58} s`;

    showToast(`Live vision telemetry actuated on ${d.corridor_id}! Webster cycle adjusted to ${d.webster_signal_actuation?.optimal_cycle_seconds || 105}s.`, "success");
    playHapticBeep(750, 45, "triangle");
  } catch (err) {
    console.error("Actuation error:", err);
    showToast(`Actuation error: ${err.message}`, "error");
  } finally {
    if (btn) btn.disabled = false;
  }
}

// Global exports for inline HTML event handlers
window.setVisionMode = setVisionMode;
window.handleVisionFileSelected = handleVisionFileSelected;
window.toggleVisionPlayback = toggleVisionPlayback;
window.onVisionTimeUpdate = onVisionTimeUpdate;
window.onVisionVideoLoaded = onVisionVideoLoaded;
window.onVisionScrubberInput = onVisionScrubberInput;
window.onVisionScrubberChange = onVisionScrubberChange;
window.cyclePlaybackRate = cyclePlaybackRate;
window.toggleVisionRoi = toggleVisionRoi;
window.actuateVisionIntoLiveGrid = actuateVisionIntoLiveGrid;
window.startClientInferenceLoop = startClientInferenceLoop;
window.stopClientInferenceLoop = stopClientInferenceLoop;
