const state = {
  games: [],
  genres: [],
  selectedGenres: new Set(),
  spinTimer: null
};

const REEL_TITLE_LIMIT = 42;
const WINNER_TITLE_LIMIT = 58;

const els = {
  form: document.querySelector("#randomizerFilters"),
  playerLimit: document.querySelector("#playerLimit"),
  complexityRange: document.querySelector("#complexityRange"),
  randomize: document.querySelector("#randomize"),
  reset: document.querySelector("#clearRandomizer"),
  genreDropdown: document.querySelector("#genreDropdown"),
  genreSummary: document.querySelector("#genreSummary"),
  genreOptions: document.querySelector("#genreOptions"),
  slotReel: document.querySelector("#slotReel"),
  winnerCard: document.querySelector("#winnerCard"),
  winnerName: document.querySelector("#winnerName"),
  winnerPlayers: document.querySelector("#winnerPlayers"),
  winnerGenres: document.querySelector("#winnerGenres"),
  winnerComplexity: document.querySelector("#winnerComplexity"),
  winnerSource: document.querySelector("#winnerSource"),
  candidateCount: document.querySelector("#candidateCount"),
  status: document.querySelector("#randomizerStatus")
};

async function api(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json();
}

async function loadRandomizer() {
  const [genresData, gamesData] = await Promise.all([
    api("/api/genres"),
    api("/api/games")
  ]);

  state.genres = genresData.genres;
  state.games = gamesData.games;
  renderPlayerLimitOptions();
  renderGenreOptions();
  renderCandidates();
}

function renderPlayerLimitOptions() {
  for (let count = 1; count <= 20; count += 1) {
    const option = document.createElement("option");
    option.value = String(count);
    option.textContent = `${count} ${count === 1 ? "player" : "players"}`;
    els.playerLimit.append(option);
  }
}

function renderGenreOptions() {
  els.genreOptions.innerHTML = "";
  if (!state.genres.length) {
    els.genreOptions.innerHTML = `<p class="filter-empty">No genre metadata imported yet.</p>`;
    renderGenreSummary();
    return;
  }

  for (const genre of state.genres) {
    const label = document.createElement("label");
    label.className = "genre-choice";
    label.innerHTML = `
      <input type="checkbox" value="${escapeHtml(genre)}">
      <span>${escapeHtml(genre)}</span>
    `;
    const checkbox = label.querySelector("input");
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        state.selectedGenres.add(genre);
      } else {
        state.selectedGenres.delete(genre);
      }
      renderGenreSummary();
      renderCandidates();
    });
    els.genreOptions.append(label);
  }
  renderGenreSummary();
}

function renderGenreSummary() {
  if (!state.selectedGenres.size) {
    els.genreSummary.textContent = "Any genre";
    return;
  }

  if (state.selectedGenres.size === 1) {
    els.genreSummary.textContent = [...state.selectedGenres][0];
    return;
  }

  els.genreSummary.textContent = `${state.selectedGenres.size} genres selected`;
}

function matchingGames() {
  const playerLimit = Number(els.playerLimit.value || 0);
  const [minComplexity, maxComplexity] = complexityBounds();

  return state.games.filter((game) => {
    const playerMatch = !playerLimit || game.maxPlayers <= playerLimit;
    const genreMatch = !state.selectedGenres.size || game.genres.some((genre) => state.selectedGenres.has(genre));
    const complexity = Number(game.complexity);
    const complexityMatch =
      minComplexity === null ||
      (Number.isFinite(complexity) && complexity >= minComplexity && complexity <= maxComplexity);
    return playerMatch && genreMatch && complexityMatch;
  });
}

function complexityBounds() {
  if (!els.complexityRange.value) return [null, null];
  return els.complexityRange.value.split("-").map(Number);
}

function renderCandidates() {
  const games = matchingGames();
  els.candidateCount.textContent = `${games.length} ${games.length === 1 ? "game" : "games"}`;
  els.status.textContent = games.length ? "Ready to spin from the filtered list." : "No games match those filters.";
}

function spin() {
  const games = matchingGames();
  if (!games.length) {
    clearWinner();
    els.status.textContent = "Adjust the filters to include at least one game.";
    return;
  }

  const winner = games[Math.floor(Math.random() * games.length)];
  let ticks = 0;
  const maxTicks = 28 + Math.floor(Math.random() * 10);

  els.randomize.disabled = true;
  els.winnerCard.hidden = true;
  els.slotReel.classList.add("spinning");
  els.status.textContent = "Spinning through your shelf.";
  window.clearInterval(state.spinTimer);

  state.spinTimer = window.setInterval(() => {
    const current = ticks >= maxTicks ? winner : games[Math.floor(Math.random() * games.length)];
    renderReelItem(current);
    ticks += 1;

    if (ticks > maxTicks) {
      window.clearInterval(state.spinTimer);
      state.spinTimer = null;
      els.slotReel.classList.remove("spinning");
      els.randomize.disabled = false;
      showWinner(winner);
    }
  }, 85);
}

function renderReelItem(game) {
  const title = truncateTitle(game.name, REEL_TITLE_LIMIT);
  els.slotReel.innerHTML = `
    <div class="slot-item">
      <strong title="${escapeHtml(game.name)}">${escapeHtml(title)}</strong>
      <span>${game.minPlayers}-${game.maxPlayers} players</span>
    </div>
  `;
}

function showWinner(game) {
  renderReelItem(game);
  els.winnerName.textContent = truncateTitle(game.name, WINNER_TITLE_LIMIT);
  els.winnerName.title = game.name;
  els.winnerPlayers.textContent = `${game.minPlayers}-${game.maxPlayers}`;
  els.winnerGenres.textContent = game.genres.length ? game.genres.join(", ") : "N/A";
  els.winnerComplexity.textContent = `${game.complexity ?? "N/A"} ${game.complexityLabel}`;
  els.winnerSource.hidden = !game.sourceUrl;
  if (game.sourceUrl) {
    els.winnerSource.href = game.sourceUrl;
  }
  els.winnerCard.hidden = false;
  els.status.textContent = `${game.name} is the pick.`;
}

function clearWinner() {
  window.clearInterval(state.spinTimer);
  state.spinTimer = null;
  els.randomize.disabled = false;
  els.slotReel.classList.remove("spinning");
  els.slotReel.innerHTML = `<div class="slot-item">Ready to spin</div>`;
  els.winnerCard.hidden = true;
}

function resetFilters() {
  els.form.reset();
  for (const checkbox of els.genreOptions.querySelectorAll("input")) {
    checkbox.checked = false;
  }
  state.selectedGenres.clear();
  renderGenreSummary();
  clearWinner();
  renderCandidates();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function truncateTitle(value, maxLength) {
  const title = String(value);
  if (title.length <= maxLength) return title;
  return `${title.slice(0, maxLength - 3).trim()}...`;
}

els.playerLimit.addEventListener("change", renderCandidates);
els.complexityRange.addEventListener("change", renderCandidates);
els.randomize.addEventListener("click", spin);
els.reset.addEventListener("click", resetFilters);

loadRandomizer().catch((error) => {
  els.status.textContent = error.message;
});
