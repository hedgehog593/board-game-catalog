const els = {
  loginPanel: document.querySelector("#loginPanel"),
  adminPanel: document.querySelector("#adminPanel"),
  loginForm: document.querySelector("#loginForm"),
  password: document.querySelector("#password"),
  loginStatus: document.querySelector("#loginStatus"),
  logout: document.querySelector("#logout"),
  importForm: document.querySelector("#importForm"),
  csvFile: document.querySelector("#csvFile"),
  importStatus: document.querySelector("#importStatus"),
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
  await loadGames();
}

async function logout() {
  await api("/api/admin/logout", { method: "POST" });
  setAuthenticated(false);
  els.loginStatus.textContent = "Logged out.";
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
  els.importStatus.textContent = `Replaced catalog with ${data.imported} owned games. ${data.matchedOnBgg} matched from BGG.${unmatched}`;
  await loadGames();
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

checkAuth().catch((error) => {
  setAuthenticated(false);
  els.loginStatus.textContent = error.message;
});
