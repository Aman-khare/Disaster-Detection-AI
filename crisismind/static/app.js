/* ═══════════════════════════════════════════════════════════════
   Disaster Detection AI — Wizard-Flow Controller
   Step 1: Location → Step 2: Fetch Data → Step 3: Analyze & Report
   ═══════════════════════════════════════════════════════════════ */

const state = {
  currentStep: 1,
  geoCoords: null,       // { lat, lon }
  locationName: "",
  weatherData: null,
  livePayload: null,     // fully-built payload for /api/analyze
  latestReport: null,
};

/* ── Boot ── */
document.addEventListener("DOMContentLoaded", () => {
  bindStep1();
  bindReportActions();
});

/* ═══════ STEP 1 — Location Input ═══════ */

function bindStep1() {
  const searchBtn = document.getElementById("search-btn");
  const gpsBtn = document.getElementById("gps-btn");
  const input = document.getElementById("location-query");

  searchBtn?.addEventListener("click", () => {
    const query = input.value.trim();
    if (!query) {
      showFeedback("Please type a location name.", "error");
      return;
    }
    startGeocodeByName(query);
  });

  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      searchBtn?.click();
    }
  });

  gpsBtn?.addEventListener("click", () => {
    startGeocodeByGPS();
  });

  document.querySelectorAll(".preset-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const query = chip.dataset.query;
      input.value = query;
      startGeocodeByName(query);
    });
  });
}

async function startGeocodeByName(query) {
  showFeedback(`Geocoding "${query}"…`, "info");
  disableStep1(true);

  try {
    const resp = await fetch(`/api/geocode?q=${encodeURIComponent(query)}`);
    const geo = await resp.json();
    if (!geo.found) {
      showFeedback(`Could not find "${query}". Try a more specific name.`, "error");
      disableStep1(false);
      return;
    }
    state.geoCoords = { lat: geo.lat, lon: geo.lon };
    state.locationName = geo.display_name;
    showFeedback(`Found: ${geo.display_name} (${geo.lat.toFixed(4)}°, ${geo.lon.toFixed(4)}°)`, "success");

    // Move to step 2 after a brief pause so user sees the confirmation
    setTimeout(() => goToStep2(), 600);
  } catch (err) {
    console.error(err);
    showFeedback("Geocoding failed. Check your connection.", "error");
    disableStep1(false);
  }
}

function startGeocodeByGPS() {
  if (!navigator.geolocation) {
    showFeedback("Geolocation is not supported by this browser.", "error");
    return;
  }
  showFeedback("Requesting GPS permission…", "info");
  disableStep1(true);

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      state.geoCoords = { lat: pos.coords.latitude, lon: pos.coords.longitude };
      showFeedback(
        `GPS located: ${pos.coords.latitude.toFixed(4)}°, ${pos.coords.longitude.toFixed(4)}°`,
        "success"
      );
      setTimeout(() => goToStep2(), 600);
    },
    (err) => {
      const messages = {
        1: "Location permission denied.",
        2: "Position unavailable.",
        3: "Location request timed out.",
      };
      showFeedback(messages[err.code] || "Could not get location.", "error");
      disableStep1(false);
    },
    { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
  );
}

function showFeedback(msg, tone) {
  const el = document.getElementById("location-feedback");
  el.textContent = msg;
  el.className = `location-feedback ${tone}`;
}

function disableStep1(disabled) {
  document.getElementById("search-btn").disabled = disabled;
  document.getElementById("gps-btn").disabled = disabled;
  document.getElementById("location-query").disabled = disabled;
  document.querySelectorAll(".preset-chip").forEach((c) => (c.disabled = disabled));
}

/* ═══════ STEP 2 — Fetch Live Data ═══════ */

function goToStep2() {
  setStep(2);
  updateTopbar("Fetching live data…");
  runDataFetch();
}

async function runDataFetch() {
  const { lat, lon } = state.geoCoords;

  // Task 1: Geocode (already done, mark complete)
  markTask("task-geocode", "done", `✅ Location resolved (${lat.toFixed(2)}°, ${lon.toFixed(2)}°)`);

  // Task 2: Fetch weather
  markTask("task-weather", "active", "⏳ Fetching live weather from Open-Meteo…");

  let weatherResponse;
  try {
    const resp = await fetch(`/api/live-weather?lat=${lat}&lon=${lon}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    weatherResponse = await resp.json();
    state.weatherData = weatherResponse;
    state.locationName = weatherResponse.location_name || state.locationName;
    markTask("task-weather", "done", `✅ Weather received — ${weatherResponse.weather.temperature_c}°C, ${weatherResponse.weather.wind_kph} kph wind, ${weatherResponse.weather.rainfall_mm} mm rain`);
  } catch (err) {
    markTask("task-weather", "error", `❌ Weather fetch failed: ${err.message}`);
    updateTopbar("Data fetch failed");
    return;
  }

  // Task 3: Signals
  markTask("task-signals", "active", "⏳ Estimating social & news signals…");
  await sleep(400); // Small delay for visual sequencing
  const signals = weatherResponse.signals || {};
  markTask("task-signals", "done", `✅ Social signal: ${signals.social_signal_level}/100 | News: ${signals.news_signal_level}/100`);

  // Task 4: Classify disaster
  markTask("task-classify", "active", "⏳ Auto-detecting disaster type…");
  await sleep(400);
  const disasterType = weatherResponse.disaster_type || "flood";
  markTask("task-classify", "done", `✅ Detected: ${disasterType.charAt(0).toUpperCase() + disasterType.slice(1)}`);

  // Update subtitle
  document.getElementById("fetch-title").textContent = `Live data ready for ${state.locationName}`;
  document.getElementById("fetch-subtitle").textContent = "All data sources connected. Starting analysis…";

  // Show summary
  const summary = document.getElementById("fetch-summary");
  const w = weatherResponse.weather;
  summary.innerHTML = `
    <div><span class="label">Location:</span> ${state.locationName}</div>
    <div><span class="label">Coordinates:</span> ${lat.toFixed(4)}°, ${lon.toFixed(4)}°</div>
    <div><span class="label">Temperature:</span> ${w.temperature_c}°C (feels like ${w.apparent_temperature_c}°C)</div>
    <div><span class="label">Wind:</span> ${w.wind_kph} kph (gusts ${w.wind_gusts_kph} kph)</div>
    <div><span class="label">Rainfall:</span> ${w.rainfall_mm} mm | <span class="label">Humidity:</span> ${w.humidity_percent}%</div>
    <div><span class="label">AQI:</span> ${w.air_quality_index} | <span class="label">River Level:</span> ${w.river_level} m</div>
    <div><span class="label">Disaster Type:</span> ${disasterType.toUpperCase()}</div>
  `;
  summary.classList.remove("hidden");

  // Build the payload
  state.livePayload = buildPayload(weatherResponse, signals, disasterType);

  // Move to step 3 after a moment
  updateTopbar("Data ready — starting analysis");
  setTimeout(() => goToStep3(), 1200);
}

function buildPayload(weatherResp, signals, disasterType) {
  const w = weatherResp.weather;
  return {
    scenario_id: "live-location",
    location_name: state.locationName,
    disaster_type: disasterType,
    current_location: { x: 50, y: 50 },
    rainfall_mm: w.rainfall_mm ?? 0,
    wind_kph: w.wind_kph ?? 0,
    temperature_c: w.temperature_c ?? 25,
    river_level: w.river_level ?? 1.0,
    air_quality_index: w.air_quality_index ?? 50,
    social_signal_level: signals.social_signal_level ?? 30,
    news_signal_level: signals.news_signal_level ?? 20,
    population_density: signals.population_density ?? 40,
    vulnerable_population_percent: signals.vulnerable_population_percent ?? 15,
  };
}

function markTask(id, status, text) {
  const el = document.getElementById(id);
  el.className = `fetch-task ${status}`;
  const iconEl = el.querySelector(".task-icon");
  const textEl = el.querySelector(".task-text");
  if (status === "done") iconEl.className = "task-icon";
  else if (status === "active") iconEl.className = "task-icon spinner";
  else if (status === "error") iconEl.className = "task-icon";
  textEl.textContent = text;
}

/* ═══════ STEP 3 — Analysis & Report ═══════ */

function goToStep3() {
  setStep(3);
  updateTopbar("Running multi-agent analysis…");
  document.getElementById("report-title").textContent = "Running multi-agent crisis analysis…";
  document.getElementById("report-subtitle").textContent = "Seven autonomous agents are analyzing the situation.";

  // Clear all report section contents so stale data never persists
  clearReportSections();
  runAnalysis();
}

function clearReportSections() {
  // Hide sections while loading
  ["risk-banner", "metrics-grid", "map-card", "intel-columns", "report-actions"].forEach((id) => {
    document.getElementById(id).style.display = "none";
  });
  // Clear inner content to prevent stale data
  [
    "risk-status-text", "risk-headline", "risk-summary",
    "metrics-grid", "map-stage",
    "situation-content", "safe-zone-content", "route-content",
    "guidance-content", "trace-content",
  ].forEach((id) => {
    document.getElementById(id).innerHTML = "";
  });
}

async function runAnalysis() {
  try {
    const resp = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.livePayload),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    state.latestReport = data.report;

    document.getElementById("report-title").textContent = `Crisis report for ${state.locationName}`;
    document.getElementById("report-subtitle").textContent = "Analysis complete. Full intelligence report is ready.";

    renderReport(data.report);
    updateTopbar(
      `${data.report.risk_assessment.status} — ${data.report.risk_assessment.probability_score}% probability`
    );
  } catch (err) {
    console.error(err);
    document.getElementById("report-title").textContent = "Analysis failed";
    document.getElementById("report-subtitle").textContent = err.message;
    updateTopbar("Analysis failed");
  }
}

/* ═══════ Rendering ═══════ */

function renderReport(report) {
  renderRiskBanner(report);
  renderMetrics(report.dashboard_metrics);
  renderMap(report);
  renderSituation(report.situation_analysis);
  renderSafeZones(report.safe_zones);
  renderRoutes(report.evacuation_routes);
  renderGuidance(
    report.precautionary_measures,
    report.recommended_actions,
    report.resource_allocation_suggestions,
    report.emergency_contacts,
    report.emergency_supply_checklist
  );
  renderTrace(report.agent_trace);

  // Force-show all report sections with explicit display values
  showReportSections();
}

function showReportSections() {
  document.getElementById("risk-banner").style.display = "block";
  document.getElementById("metrics-grid").style.display = "grid";
  document.getElementById("map-card").style.display = "block";
  document.getElementById("intel-columns").style.display = "grid";
  document.getElementById("report-actions").style.display = "flex";

  // Scroll down slightly so the user can see the full report appeared
  setTimeout(() => {
    const banner = document.getElementById("risk-banner");
    if (banner) banner.scrollIntoView({ behavior: "smooth", block: "start" });
  }, 100);
}

function renderRiskBanner(report) {
  const banner = document.getElementById("risk-banner");
  const score = report.risk_assessment.risk_score;
  const accent = score >= 85 ? "var(--critical)" : score >= 70 ? "var(--severe)" : score >= 55 ? "var(--elevated)" : "var(--teal)";
  banner.style.borderColor = accent;
  banner.style.boxShadow = `inset 0 0 0 1px ${accent}, 0 0 30px rgba(0,0,0,0.2)`;
  document.getElementById("risk-status-text").textContent = report.risk_assessment.status;
  document.getElementById("risk-status-text").style.color = accent;
  document.getElementById("risk-headline").textContent =
    `${report.request.location_name} | ${report.risk_assessment.disaster_type} risk at ${score}/100`;
  document.getElementById("risk-summary").textContent = report.executive_summary;
}

function renderMetrics(metrics) {
  const cards = [
    { title: "Population At Risk", value: metrics.population_at_risk.toLocaleString(), desc: "People in modelled impact radius" },
    { title: "Damage Index", value: `${metrics.predicted_damage_index}%`, desc: "Composite infrastructure stress" },
    { title: "Ambulances", value: metrics.ambulances_ready, desc: "Available for dispatch" },
    { title: "Rescue Teams", value: metrics.rescue_teams_ready, desc: "Staged for deployment" },
    { title: "Shelters", value: metrics.shelters_ready, desc: "With immediate capacity" },
    { title: "Status", value: "Live", desc: metrics.response_status },
  ];
  document.getElementById("metrics-grid").innerHTML = cards
    .map(
      (c) => `
      <article class="metric-card">
        <h3>${c.title}</h3>
        <strong>${c.value}</strong>
        <p>${c.desc}</p>
      </article>`
    )
    .join("");
}

function renderSituation(sit) {
  document.getElementById("situation-content").innerHTML = `
    <div class="copy-block"><h4>Incident Summary</h4><p>${sit.incident_summary}</p></div>
    <div class="copy-block"><h4>Threat Assessment</h4><p>${sit.threat_assessment}</p><p>${sit.current_incident_status}</p></div>
    <div class="copy-block"><h4>Operational Snapshot</h4>
      <ul class="clean-list">
        <li>Affected regions: ${sit.affected_regions.join(", ")}</li>
        <li>Hospitals at risk: ${sit.hospitals_at_risk}</li>
        <li>Schools at risk: ${sit.schools_at_risk}</li>
        <li>Roads blocked: ${sit.roads_blocked}</li>
      </ul>
      <p>${sit.weather_and_hazard_conditions}</p>
    </div>`;
}

function renderSafeZones(zones) {
  document.getElementById("safe-zone-content").innerHTML = zones
    .map(
      (z) => `
      <article class="safe-zone-card">
        <h4>${z.name}</h4>
        <div class="safe-zone-meta">
          <span class="pill teal">${z.safety_score} safety</span>
          <span class="pill">${z.distance_km} km</span>
          <span class="pill">${z.available_capacity}/${z.capacity} cap</span>
        </div>
        <p>${z.address}</p><p>${z.contact}</p>
        <ul class="clean-list">${z.notes.map((n) => `<li>${n}</li>`).join("")}</ul>
      </article>`
    )
    .join("");
}

function renderRoutes(routes) {
  document.getElementById("route-content").innerHTML = routes
    .map(
      (r, i) => `
      <article class="route-card">
        <h4>${i === 0 ? "Primary Route" : `Alternate ${i}`}</h4>
        <p>${r.safe_zone_name}</p>
        <div class="route-meta">
          <span class="pill teal">${r.travel_time_min} min</span>
          <span class="pill">${r.distance_km} km</span>
          <span class="pill red">${r.safety_score} safety</span>
        </div>
        <ul class="clean-list">${r.notes.map((n) => `<li>${n}</li>`).join("")}</ul>
      </article>`
    )
    .join("");
}

function renderGuidance(guidance, recs, resSugg, contacts, checklist) {
  document.getElementById("guidance-content").innerHTML = `
    <div class="copy-block"><h4>Immediate Actions</h4>
      <ul class="clean-list">${guidance.immediate_actions.map((a) => `<li>${a}</li>`).join("")}</ul></div>
    <div class="copy-block"><h4>Before / During / After</h4>
      <p><strong>Before:</strong> ${guidance.before_disaster.join(" ")}</p>
      <p><strong>During:</strong> ${guidance.during_disaster.join(" ")}</p>
      <p><strong>After:</strong> ${guidance.after_disaster.join(" ")}</p></div>
    <div class="copy-block"><h4>AI Recommendations</h4>
      <ul class="clean-list">
        ${recs.map((r) => `<li>${r}</li>`).join("")}
        ${resSugg.map((r) => `<li>${r}</li>`).join("")}
      </ul></div>
    <div class="copy-block"><h4>Emergency Contacts</h4>
      <div class="contact-grid">
        ${Object.entries(contacts).map(([k, v]) => `<div class="answer-card"><h4>${k}</h4><p>${v}</p></div>`).join("")}
      </div></div>
    <div class="copy-block"><h4>Supply Checklist</h4>
      <ul class="clean-list">${checklist.map((c) => `<li>${c}</li>`).join("")}</ul></div>
    <div class="copy-block"><h4>Citizen Q&A</h4>
      <div class="stack">
        ${guidance.answer_cards.map((c) => `<div class="answer-card"><h4>${c.question}</h4><p>${c.answer}</p></div>`).join("")}
      </div></div>`;
}

function renderTrace(trace) {
  document.getElementById("trace-content").innerHTML = trace
    .map(
      (t) => `
      <div class="trace-item">
        <div>
          <h4>${t.agent}</h4>
          <p>${t.summary}</p>
          <small>${t.tools_used.join(" | ")}</small>
        </div>
        <div class="trace-latency">${t.latency_ms} ms</div>
      </div>`
    )
    .join("");
}

function renderMap(report) {
  const width = 820;
  const height = 420;
  const sx = width / 100;
  const sy = height / 100;
  const regions = report.map_layers.regions || [];
  const roads = report.map_layers.roads || [];
  const cur = report.map_layers.current_location;
  const zones = report.safe_zones || [];
  const hazards = report.hazard_zones || [];
  const routes = report.evacuation_routes || [];

  const regionSvg = regions
    .map(
      (r) => `
      <rect x="${r.bounds.x * sx}" y="${r.bounds.y * sy}" width="${r.bounds.width * sx}" height="${r.bounds.height * sy}" rx="14" fill="rgba(238,244,239,0.92)" stroke="rgba(16,42,54,0.18)" />
      <text x="${(r.bounds.x + 2) * sx}" y="${(r.bounds.y + r.bounds.height - 2) * sy}" fill="#29434e" font-size="12" font-family="Inter,sans-serif">${r.name}</text>`
    )
    .join("");

  const roadSvg = roads
    .map((r) => {
      const [a, b] = r.path;
      return `<line x1="${a.x * sx}" y1="${a.y * sy}" x2="${b.x * sx}" y2="${b.y * sy}" stroke="rgba(12,37,48,0.45)" stroke-width="5" stroke-linecap="round" stroke-dasharray="10 8" />`;
    })
    .join("");

  const hazardSvg = hazards
    .map(
      (h) => `
      <circle cx="${h.center.x * sx}" cy="${h.center.y * sy}" r="${h.radius * sx}" fill="rgba(217,74,61,0.20)" stroke="rgba(217,74,61,0.78)" stroke-width="2" />
      <text x="${(h.center.x - 4) * sx}" y="${h.center.y * sy}" fill="#8d231b" font-size="11" font-family="Inter,sans-serif">${h.name}</text>`
    )
    .join("");

  const routeSvg = routes
    .map((r, i) => {
      const pts = r.path.map((p) => `${p.x * sx},${p.y * sy}`).join(" ");
      const colors = ["#14b8a6", "#eab308", "#8ad7d1"];
      return `<polyline points="${pts}" fill="none" stroke="${colors[i] || "#14b8a6"}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />`;
    })
    .join("");

  const zoneSvg = zones
    .map(
      (z) => `
      <rect x="${z.location.x * sx - 7}" y="${z.location.y * sy - 7}" width="14" height="14" rx="4" fill="#a3e635" stroke="#0f7173" stroke-width="2" />
      <text x="${(z.location.x + 1.8) * sx}" y="${z.location.y * sy + 5}" fill="#0f7173" font-size="12" font-family="Inter,sans-serif">${z.name}</text>`
    )
    .join("");

  const curSvg = `
    <circle cx="${cur.x * sx}" cy="${cur.y * sy}" r="7" fill="#0a0e17" stroke="#ffffff" stroke-width="2" />
    <circle cx="${cur.x * sx}" cy="${cur.y * sy}" r="18" fill="none" stroke="rgba(255,255,255,0.35)" stroke-width="1.2" />
    <text x="${(cur.x + 2) * sx}" y="${cur.y * sy - 10}" fill="#ffffff" font-size="12" font-family="Inter,sans-serif">Current location</text>`;

  document.getElementById("map-stage").innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" aria-label="Disaster Detection live map">
      <defs>
        <linearGradient id="mapBg" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="#f8f6ef" />
          <stop offset="100%" stop-color="#dce8dd" />
        </linearGradient>
      </defs>
      <rect width="${width}" height="${height}" rx="24" fill="url(#mapBg)" />
      ${regionSvg}${roadSvg}${hazardSvg}${routeSvg}${zoneSvg}${curSvg}
    </svg>`;
}

/* ═══════ Report Actions ═══════ */

function bindReportActions() {
  document.getElementById("pdf-btn")?.addEventListener("click", downloadPdf);
  document.getElementById("restart-btn")?.addEventListener("click", restart);
}

async function downloadPdf() {
  if (!state.livePayload) return;
  const btn = document.getElementById("pdf-btn");
  btn.disabled = true;
  btn.textContent = "⏳ Generating PDF…";
  try {
    const resp = await fetch("/api/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.livePayload),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "disaster-detection-report.pdf";
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    console.error(err);
    alert("PDF generation failed: " + err.message);
  }
  btn.disabled = false;
  btn.textContent = "📄 Download PDF Report";
}

function restart() {
  state.currentStep = 1;
  state.geoCoords = null;
  state.weatherData = null;
  state.livePayload = null;
  state.latestReport = null;
  state.locationName = "";

  document.getElementById("location-query").value = "";
  document.getElementById("location-feedback").className = "location-feedback hidden";
  disableStep1(false);

  // Reset step 2
  ["task-geocode", "task-weather", "task-signals", "task-classify"].forEach((id) => {
    markTask(id, "", "");
  });
  document.getElementById("fetch-summary").classList.add("hidden");
  document.getElementById("fetch-summary").innerHTML = "";

  // Hide and clear report sections so no stale data persists
  clearReportSections();

  // Reset report header text
  document.getElementById("report-title").textContent = "Running multi-agent crisis analysis…";
  document.getElementById("report-subtitle").textContent = "Seven autonomous agents are analyzing the situation.";

  setStep(1);
  updateTopbar("Waiting for location…");
}

/* ═══════ Step Navigation ═══════ */

function setStep(step) {
  state.currentStep = step;

  // Toggle visibility
  [1, 2, 3].forEach((s) => {
    const el = document.getElementById(`step-${s}`);
    if (s === step) {
      el.classList.add("step-visible");
    } else {
      el.classList.remove("step-visible");
    }
  });

  // Update progress bar
  const pcts = { 1: 0, 2: 40, 3: 100 };
  document.getElementById("progress-fill").style.width = `${pcts[step]}%`;

  // Update step indicators
  [1, 2, 3].forEach((s) => {
    const ind = document.getElementById(`step-ind-${s}`);
    ind.className = "step-ind";
    if (s < step) ind.classList.add("done");
    if (s === step) ind.classList.add("active");
  });

  // Scroll to top
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function updateTopbar(text) {
  document.getElementById("topbar-status").textContent = text;
}

/* ═══════ Utils ═══════ */

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}
