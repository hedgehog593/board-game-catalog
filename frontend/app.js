const state = {
  games: [],
  genres: []
};

const els = {
  form: document.querySelector("#filters"),
  players: document.querySelector("#players"),
  genre: document.querySelector("#genre"),
  maxComplexity: document.querySelector("#maxComplexity"),
  reset: document.querySelector("#reset"),
  games: document.querySelector("#games"),
  resultCount: document.querySelector("#resultCount"),
  activeFilters: document.querySelector("#activeFilters")
};

async function api(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json();
}

function filtersQuery() {
  const params = new URLSearchParams();
  if (els.players.value) params.set("players", els.players.value);
  if (els.genre.value) params.set("genre", els.genre.value);
  if (els.maxComplexity.value) params.set("maxComplexity", els.maxComplexity.value);
  return params.toString();
}

async function loadGenres() {
  const data = await api("/api/genres");
  state.genres = data.genres;
  els.genre.innerHTML = `<option value="">Any genre</option>`;
  for (const genre of state.genres) {
    const option = document.createElement("option");
    option.value = genre;
    option.textContent = genre;
    els.genre.append(option);
  }
}

async function loadGames() {
  const query = filtersQuery();
  const data = await api(`/api/games${query ? `?${query}` : ""}`);
  state.games = data.games;
  renderGames();
  renderSummary();
}

function renderGames() {
  els.games.innerHTML = "";

  if (!state.games.length) {
    const row = document.createElement("tr");
    row.innerHTML = `<td class="empty" colspan="5">No games match those filters.</td>`;
    els.games.append(row);
    return;
  }

  for (const game of state.games) {
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

function renderSummary() {
  const count = state.games.length;
  els.resultCount.textContent = `${count} ${count === 1 ? "game" : "games"}`;

  const parts = [];
  if (els.players.value) parts.push(`${els.players.value} players`);
  if (els.genre.value) parts.push(els.genre.value);
  if (els.maxComplexity.value) parts.push(`complexity <= ${els.maxComplexity.value}`);

  els.activeFilters.textContent = parts.length ? `Filtered by ${parts.join(", ")}.` : "Showing the full catalog.";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

els.form.addEventListener("submit", (event) => {
  event.preventDefault();
  loadGames().catch(showError);
});

els.reset.addEventListener("click", () => {
  els.form.reset();
  loadGames().catch(showError);
});

function showError(error) {
  els.games.innerHTML = `<tr><td class="empty" colspan="5">${escapeHtml(error.message)}</td></tr>`;
}

loadGenres()
  .then(loadGames)
  .catch(showError);
