const els = {
  loginPanel: document.querySelector("#loginPanel"),
  adminPanel: document.querySelector("#adminPanel"),
  loginForm: document.querySelector("#loginForm"),
  password: document.querySelector("#password"),
  loginStatus: document.querySelector("#loginStatus"),
  logout: document.querySelector("#logout"),
  importForm: document.querySelector("#importForm"),
  metadataForm: document.querySelector("#metadataForm"),
  csvFile: document.querySelector("#csvFile"),
  metadataFile: document.querySelector("#metadataFile"),
  importStatus: document.querySelector("#importStatus"),
  metadataStatus: document.querySelector("#metadataStatus"),
  games: document.querySelector("#games"),
  resultCount: document.querySelector("#resultCount"),
  activeFilters: document.querySelector("#activeFilters")
};

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `API request failed: ${response.status}`);
  }
  return data;
}

async function checkAuth() {
  const data = await api("/api/admin/status", { method: "POST" });
  setAuthenticated(data.authenticated);
  if (data.authenticated) {
    await loadMetadataStatus();
    await loadGames();
  }
}

function setAuthenticated(authenticated) {
  els.loginPanel.hidden = authenticated;
  els.adminPanel.hidden = !authenticated;
  els.logout.hidden = !authenticated;
}

async function login() {
  els.loginStatus.textContent = "Checking password...";
  const data = await api("/api/admin/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password: els.password.value })
  });
  setAuthenticated(data.authenticated);
  els.password.value = "";
  els.loginStatus.textContent = "";
  await loadMetadataStatus();
  await loadGames();
}

async function logout() {
  await api("/api/admin/logout", { method: "POST" });
  setAuthenticated(false);
  els.loginStatus.textContent = "Logged out.";
}

async function uploadMetadataCsv() {
  const file = els.metadataFile.files[0];
  if (!file) {
    els.metadataStatus.textContent = "Choose the BGG metadata CSV first.";
    return;
  }

  els.metadataStatus.textContent = "Saving metadata CSV...";
  const formData = new FormData();
  formData.append("file", file);

  const data = await api("/api/metadata/csv", {
    method: "POST",
    body: formData
  });

  els.metadataStatus.textContent = `Metadata ready: ${data.records} records from ${data.source}.`;
}

async function importCsv() {
  const file = els.csvFile.files[0];
  if (!file) {
    els.importStatus.textContent = "Choose a CSV file first.";
    return;
  }

  els.importStatus.textContent = "Importing owned games...";
  const formData = new FormData();
  formData.append("file", file);

  const data = await api("/api/import/csv", {
    method: "POST",
    body: formData
  });

  const unmatched = data.unmatched.length ? ` ${data.unmatched.length} unmatched.` : "";
  const metadataNote = data.metadataSource ? ` Metadata: ${data.metadataSource}.` : " No metadata CSV found; unmatched rows used CSV-only details.";
  els.importStatus.textContent = `Replaced catalog with ${data.imported} owned games. ${data.matchedFromMetadata} matched from metadata CSV.${unmatched}${metadataNote}`;
  await loadGames();
}

async function loadMetadataStatus() {
  const data = await api("/api/metadata/status");
  els.metadataStatus.textContent = data.available
    ? `Metadata ready: ${data.records} records from ${data.source}.`
    : "Upload metadata first, then import your owned games.";
}

async function loadGames() {
  const data = await api("/api/games");
  renderGames(data.games);
  els.resultCount.textContent = `${data.count} ${data.count === 1 ? "game" : "games"}`;
  els.activeFilters.textContent = "Full catalog.";
}

function renderGames(games) {
  els.games.innerHTML = "";

  if (!games.length) {
    const row = document.createElement("tr");
    row.innerHTML = `<td class="empty" colspan="5">No games in the catalog.</td>`;
    els.games.append(row);
    return;
  }

  for (const game of games) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td class="name">${escapeHtml(game.name)}</td>
      <td>${game.minPlayers}-${game.maxPlayers}</td>
      <td><div class="tags">${game.genres.map((genre) => `<span class="tag">${escapeHtml(genre)}</span>`).join("")}</div></td>
      <td><span class="complexity">${game.complexity ?? "N/A"}</span> ${escapeHtml(game.complexityLabel)}</td>
      <td>${game.sourceUrl ? `<a href="${game.sourceUrl}" target="_blank" rel="noreferrer">BGG</a>` : ""}</td>
    `;
    els.games.append(row);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

els.loginForm.addEventListener("submit", (event) => {
  event.preventDefault();
  login().catch((error) => {
    els.loginStatus.textContent = error.message;
  });
});

els.logout.addEventListener("click", () => {
  logout().catch((error) => {
    els.loginStatus.textContent = error.message;
  });
});

els.importForm.addEventListener("submit", (event) => {
  event.preventDefault();
  importCsv().catch((error) => {
    els.importStatus.textContent = error.message;
  });
});

els.metadataForm.addEventListener("submit", (event) => {
  event.preventDefault();
  uploadMetadataCsv().catch((error) => {
    els.metadataStatus.textContent = error.message;
  });
});

checkAuth().catch((error) => {
  setAuthenticated(false);
  els.loginStatus.textContent = error.message;
});
