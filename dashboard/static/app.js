const incidentList = document.getElementById("incident-list");
const simulateButton = document.getElementById("simulate-button");
const acknowledgeButton = document.getElementById("acknowledge-button");
const alertPanel = document.getElementById("alert-panel");
const safetyCard = document.getElementById("safety-card");
const toast = document.getElementById("toast");
let toastTimer;

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("is-visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("is-visible"), 3600);
}

function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Time unavailable";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function formatClock(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "--:--:--"
    : new Intl.DateTimeFormat(undefined, {
        hour: "numeric",
        minute: "2-digit",
        second: "2-digit",
      }).format(date);
}

function eventIcon(isFall) {
  if (isFall) {
    return '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 8v5m0 3h.01M10.3 4.9 2.8 18a1.8 1.8 0 0 0 1.6 2.7h15.2a1.8 1.8 0 0 0 1.6-2.7L13.7 4.9a2 2 0 0 0-3.4 0Z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  }
  return '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3.5 20 7v5.4c0 4.7-3.4 8.3-8 9.4-4.6-1.1-8-4.7-8-9.4V7l8-3.5Z" stroke="currentColor" stroke-width="1.7"/><path d="m8.5 12 2.2 2.2 4.8-4.8" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';
}

function renderIncidents(incidents) {
  document.getElementById("history-count").textContent =
    `${incidents.length} ${incidents.length === 1 ? "event" : "events"}`;
  document.getElementById("demo-note").hidden =
    !incidents.some((incident) => incident.demo);

  if (!incidents.length) {
    incidentList.innerHTML = '<div class="empty-state">No incidents to show yet.</div>';
    return;
  }

  incidentList.replaceChildren();
  for (const incident of incidents) {
    const isFall = incident.event_type === "Fall detected";
    const row = document.createElement("div");
    row.className = "incident-row";

    const icon = document.createElement("span");
    icon.className = `incident-icon${isFall ? " is-fall" : ""}`;
    icon.innerHTML = eventIcon(isFall);

    const main = document.createElement("span");
    main.className = "incident-main";
    const name = document.createElement("span");
    name.className = "incident-name";
    name.textContent = incident.event_type;
    if (incident.demo) {
      const demoTag = document.createElement("span");
      demoTag.className = "incident-demo";
      demoTag.textContent = "DEMO";
      name.append(demoTag);
    }
    const time = document.createElement("span");
    time.className = "incident-time";
    time.textContent = formatTime(incident.timestamp);
    main.append(name, time);

    const status = document.createElement("span");
    const statusText = incident.status === "active"
      ? "Needs attention"
      : incident.status === "escalated" ? "Demo escalation"
      : incident.status === "acknowledged" ? "Acknowledged"
      : incident.status === "resolved" ? "Resolved"
      : "Recorded";
    status.className = `incident-status${(incident.status === "active" || incident.status === "escalated") ? " is-active" : incident.status === "acknowledged" ? " is-acknowledged" : ""}`;
    status.textContent = statusText;
    row.append(icon, main, status);
    incidentList.append(row);
  }
}

function renderState(state) {
  const cameraOnline = state.camera_status === "online";
  const monitoringActive = state.monitoring_status === "active";
  document.getElementById("camera-status").textContent = cameraOnline ? "Online" : "Offline";
  document.getElementById("camera-indicator").style.background = cameraOnline ? "#2da47b" : "#c9373b";
  document.getElementById("monitor-status").textContent = monitoringActive ? "Active" : "Not connected";
  document.getElementById("camera-detail").textContent = cameraOnline ? `${state.people_visible ?? 0} person(s) visible · Raspberry Pi` : "Waiting for detector heartbeat";
  document.getElementById("monitor-detail").textContent = monitoringActive ? "Fall detection process running" : "Start detector on this laptop";
  document.getElementById("connection-indicator").style.background = monitoringActive ? "#2ca47e" : "#c28b29";
  document.getElementById("monitor-indicator").style.background = monitoringActive ? "#2da47b" : "#c28b29";
  document.getElementById("data-mode").textContent = state.demo_mode ? "DEMO DATA" : "PROTOTYPE · LIVE INPUT";
  document.getElementById("last-updated").textContent = formatClock(state.server_time);
  document.getElementById("current-date").textContent = new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  }).format(new Date(state.server_time));

  const alert = state.active_alert;
  alertPanel.hidden = !alert;
  alertPanel.classList.toggle("is-acknowledged", Boolean(alert && alert.status === "acknowledged"));
  safetyCard.classList.toggle("is-alert", Boolean(alert && (alert.status === "active" || alert.status === "escalated")));
  safetyCard.classList.toggle("is-acknowledged", Boolean(alert && alert.status === "acknowledged"));
  if (!alert) {
    document.getElementById("safety-status").textContent = monitoringActive ? "No active alerts" : "Not connected";
    document.getElementById("safety-detail").textContent = monitoringActive ? "No fall alerts currently recorded" : "Start the detector to enable monitoring";
  } else if (alert.status !== "acknowledged") {
    document.getElementById("safety-status").textContent = "Fall reported";
    document.getElementById("safety-detail").textContent = "Caregiver attention needed";
  } else {
    document.getElementById("safety-status").textContent = "Alert acknowledged";
    document.getElementById("safety-detail").textContent = "Fall report remains on record";
  }

  if (alert) {
    document.getElementById("alert-kicker").textContent =
      alert.status === "acknowledged" ? "CAREGIVER ACKNOWLEDGED" : alert.status === "escalated" ? "DEMO ESCALATION" : "POSSIBLE FALL";
    document.getElementById("alert-title").textContent =
      alert.status === "acknowledged" ? "Alert acknowledged" : alert.status === "escalated" ? "Caregiver attention needed" : "Possible fall detected";
    document.getElementById("alert-description").textContent =
      alert.status === "acknowledged" ? "An acknowledgement was recorded. Please still check on the person."
      : `${alert.person_id ? `Person ${alert.person_id}: ` : ""}${alert.reason || "Possible fall"}. ${alert.status === "escalated" ? "Simulated caregiver alert only. No call or text sent." : "Checking for a voice response..."}`;
    document.getElementById("alert-time").textContent = formatTime(alert.timestamp);
    acknowledgeButton.disabled = alert.status === "acknowledged";
  }
  renderIncidents(state.incidents);
}

async function request(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
  return result;
}

async function refreshState() {
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error(`Dashboard state unavailable (${response.status})`);
    renderState(await response.json());
  } catch (error) {
    showToast(`Could not refresh dashboard: ${error.message}`);
  }
}

simulateButton.addEventListener("click", async () => {
  simulateButton.disabled = true;
  try {
    const result = await request("/api/events", {
      event_type: "fall_detected",
      source: "demo",
    });
    renderState(result.state);
    showToast("Demo fall alert created. No call or notification was sent.");
  } catch (error) {
    showToast(`Could not simulate fall: ${error.message}`);
  } finally {
    simulateButton.disabled = false;
  }
});

acknowledgeButton.addEventListener("click", async () => {
  acknowledgeButton.disabled = true;
  try {
    const result = await request("/api/alerts/acknowledge", {});
    renderState(result.state);
    showToast("Alert acknowledged and added to the incident history.");
  } catch (error) {
    acknowledgeButton.disabled = false;
    showToast(`Could not acknowledge alert: ${error.message}`);
  }
});

document.getElementById("current-date").textContent =
  new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric" }).format(new Date());
refreshState();
setInterval(refreshState, 3000);
