const state = {
  games: [],
  genres: [],
  selectedGenres: new Set(),
  spinTimer: null
};

const REEL_TITLE_LIMIT = 42;
const WINNER_TITLE_LIMIT = 58;

const complexityOptions = [
  { value: "", label: "Any complexity" },
  { value: "0-2", label: "Light (0-2)" },
  { value: "2-3", label: "Medium (2-3)" },
  { value: "3-4", label: "Heavy (3-4)" },
  { value: "4-5", label: "Very heavy (4-5)" }
];

const els = {
  form: document.querySelector("#randomizerFilters"),
  playerLimit: document.querySelector("#playerLimit"),
  complexityRange: document.querySelector("#complexityRange"),
  randomize: document.querySelector("#randomize"),
  randomizeHandle: document.querySelector("#randomizeHandle"),
  reset: document.querySelector("#clearRandomizer"),
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
  initializeCombos();
  renderCandidates();
}

function initializeCombos() {
  createFilterCombo({
    name: "playerLimit",
    input: els.playerLimit,
    options: playerOptions(),
    emptyLabel: "Any count",
    onChange: renderCandidates
  });

  createFilterCombo({
    name: "complexityRange",
    input: els.complexityRange,
    options: complexityOptions,
    emptyLabel: "Any complexity",
    onChange: renderCandidates
  });

  createFilterCombo({
    name: "genres",
    multi: true,
    options: state.genres.map((genre) => ({ value: genre, label: genre })),
    emptyLabel: "Any genre",
    selectedValues: state.selectedGenres,
    onChange: () => {
      renderGenreSummary();
      renderCandidates();
    }
  });
}

function playerOptions() {
  const options = [{ value: "", label: "Any count" }];
  for (let count = 1; count <= 20; count += 1) {
    options.push({ value: String(count), label: `${count} ${count === 1 ? "player" : "players"}` });
  }
  return options;
}

function createFilterCombo({ name, input, options, emptyLabel, onChange, multi = false, selectedValues = null }) {
  let combo = document.querySelector(`[data-filter-combo="${name}"]`);
  const freshCombo = combo.cloneNode(true);
  combo.replaceWith(freshCombo);
  combo = freshCombo;
  const toggle = combo.querySelector(".combo-toggle");
  const panel = combo.querySelector(".combo-panel");
  const search = combo.querySelector(".combo-search");
  const optionsList = combo.querySelector(".combo-options");
  if (name === "genres") {
    els.genreSummary = toggle;
    els.genreOptions = optionsList;
  }
  const isGenre = name === "genres";
  let filterText = "";

  function selectedLabel() {
    if (multi) return genreSummaryText(emptyLabel);
    const selected = options.find((option) => option.value === input.value);
    return selected && selected.value ? selected.label : emptyLabel;
  }

  function render() {
    const normalizedFilter = filterText.trim().toLowerCase();
    const visibleOptions = options.filter((option) => option.label.toLowerCase().includes(normalizedFilter));
    optionsList.innerHTML = "";

    if (isGenre) {
      const actions = document.createElement("div");
      actions.className = "combo-actions";
      const clear = document.createElement("button");
      clear.type = "button";
      clear.className = "combo-clear";
      clear.textContent = "Clear all";
      clear.disabled = !selectedValues.size;
      clear.addEventListener("click", () => {
        selectedValues.clear();
        filterText = "";
        search.value = "";
        toggle.textContent = selectedLabel();
        render();
        onChange();
      });
      actions.append(clear);
      optionsList.append(actions);
    }

    if (!visibleOptions.length) {
      const empty = document.createElement("p");
      empty.className = "filter-empty";
      empty.textContent = options.length ? "No matches." : "No genre metadata imported yet.";
      optionsList.append(empty);
      return;
    }

    for (const option of visibleOptions) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "combo-option";
      button.dataset.value = option.value;
      const isSelected = multi ? selectedValues.has(option.value) : option.value === input.value;
      button.setAttribute("aria-pressed", String(isSelected));
      button.textContent = multi && isSelected ? `${option.label} ✓` : option.label;
      button.addEventListener("click", () => {
        if (multi) {
          if (selectedValues.has(option.value)) {
            selectedValues.delete(option.value);
          } else {
            selectedValues.add(option.value);
          }
          toggle.textContent = selectedLabel();
          render();
          onChange();
          return;
        }

        input.value = option.value;
        toggle.textContent = selectedLabel();
        closeCombo(combo);
        onChange();
      });
      optionsList.append(button);
    }
  }

  toggle.textContent = selectedLabel();
  toggle.addEventListener("click", () => {
    if (panel.hidden) {
      openCombo(combo);
      filterText = "";
      search.value = "";
      render();
      search.focus();
    } else {
      closeCombo(combo);
    }
  });

  search.addEventListener("input", () => {
    filterText = search.value;
    render();
  });

  render();
}

function genreSummaryText(emptyLabel = "Any genre") {
  if (!state.selectedGenres.size) return emptyLabel;
  if (state.selectedGenres.size === 1) return [...state.selectedGenres][0];
  return `${state.selectedGenres.size} genres selected`;
}

function renderGenreSummary() {
  els.genreSummary.textContent = genreSummaryText();
}

function openCombo(combo) {
  closeAllCombos(combo);
  combo.querySelector(".combo-panel").hidden = false;
  const toggle = combo.querySelector(".combo-toggle");
  const search = combo.querySelector(".combo-search");
  toggle.hidden = true;
  toggle.setAttribute("aria-expanded", "true");
  search.hidden = false;
}

function closeCombo(combo) {
  combo.querySelector(".combo-panel").hidden = true;
  const toggle = combo.querySelector(".combo-toggle");
  const search = combo.querySelector(".combo-search");
  toggle.hidden = false;
  toggle.setAttribute("aria-expanded", "false");
  search.hidden = true;
}

function closeAllCombos(except = null) {
  for (const combo of document.querySelectorAll(".filter-combo")) {
    if (combo !== except) closeCombo(combo);
  }
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
  els.randomizeHandle.disabled = true;
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
      els.randomizeHandle.disabled = false;
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
  els.randomizeHandle.disabled = false;
  els.slotReel.classList.remove("spinning");
  els.slotReel.innerHTML = `<div class="slot-item">Ready to spin</div>`;
  els.winnerCard.hidden = true;
}

function resetFilters() {
  els.playerLimit.value = "";
  els.complexityRange.value = "";
  state.selectedGenres.clear();
  initializeCombos();
  closeAllCombos();
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

document.addEventListener("click", (event) => {
  if (!event.target.closest(".filter-combo")) {
    closeAllCombos();
  }
});

els.randomize.addEventListener("click", spin);
els.randomizeHandle.addEventListener("click", spin);
els.reset.addEventListener("click", resetFilters);

loadRandomizer().catch((error) => {
  els.status.textContent = error.message;
});
