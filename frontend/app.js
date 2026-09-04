const state = {
  games: [],
  genres: []
};

const complexityOptions = [
  { value: "", label: "Any weight" },
  { value: "2", label: "Light" },
  { value: "3", label: "Medium or lighter" },
  { value: "4", label: "Heavy or lighter" }
];

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
  initializeCombos();
}

function initializeCombos() {
  createFilterCombo({
    name: "players",
    input: els.players,
    options: playerOptions(),
    emptyLabel: "Any count",
    onChange: () => loadGames().catch(showError)
  });

  createFilterCombo({
    name: "genre",
    input: els.genre,
    options: [{ value: "", label: "Any genre" }, ...state.genres.map((genre) => ({ value: genre, label: genre }))],
    emptyLabel: "Any genre",
    onChange: () => loadGames().catch(showError)
  });

  createFilterCombo({
    name: "maxComplexity",
    input: els.maxComplexity,
    options: complexityOptions,
    emptyLabel: "Any weight",
    onChange: () => loadGames().catch(showError)
  });
}

function playerOptions() {
  const options = [{ value: "", label: "Any count" }];
  for (let count = 1; count <= 20; count += 1) {
    options.push({ value: String(count), label: `${count} ${count === 1 ? "player" : "players"}` });
  }
  return options;
}

function createFilterCombo({ name, input, options, emptyLabel, onChange }) {
  let combo = document.querySelector(`[data-filter-combo="${name}"]`);
  const freshCombo = combo.cloneNode(true);
  combo.replaceWith(freshCombo);
  combo = freshCombo;
  const toggle = combo.querySelector(".combo-toggle");
  const panel = combo.querySelector(".combo-panel");
  const search = combo.querySelector(".combo-search");
  const optionsList = combo.querySelector(".combo-options");
  const isGenre = name === "genre";
  let filterText = "";

  function selectedLabel() {
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
      clear.disabled = !input.value;
      clear.addEventListener("click", () => {
        input.value = "";
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
      empty.textContent = "No matches.";
      optionsList.append(empty);
      return;
    }

    for (const option of visibleOptions) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "combo-option";
      button.dataset.value = option.value;
      button.setAttribute("aria-pressed", String(option.value === input.value));
      button.textContent = option.label;
      button.addEventListener("click", () => {
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
  els.players.value = "";
  els.genre.value = "";
  els.maxComplexity.value = "";
  initializeCombos();
  closeAllCombos();
  loadGames().catch(showError);
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".filter-combo")) {
    closeAllCombos();
  }
});

function showError(error) {
  els.games.innerHTML = `<tr><td class="empty" colspan="5">${escapeHtml(error.message)}</td></tr>`;
}

loadGenres()
  .then(loadGames)
  .catch(showError);
