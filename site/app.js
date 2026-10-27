const search = document.querySelector("#skill-search");
const cards = [...document.querySelectorAll(".skill-card")];
const categories = [...document.querySelectorAll("[data-category-filter]")];
let activeCategory = "all";

function filterSkills() {
  const words = search.value.trim().toLowerCase().split(/\s+/);
  let visible = 0;
  for (const card of cards) {
    const matchesCategory = activeCategory === "all" || card.dataset.category === activeCategory;
    card.hidden = !matchesCategory || !words.every((word) => card.textContent.toLowerCase().includes(word));
    if (!card.hidden) visible += 1;
  }
  document.querySelector("#skill-count").textContent = `${visible} ${visible === 1 ? "skill" : "skills"}`;
  document.querySelector("#empty-state").hidden = visible !== 0;
  for (const button of categories) {
    button.setAttribute("aria-pressed", String(button.dataset.categoryFilter === activeCategory));
  }
}

search.addEventListener("input", filterSkills);
for (const button of categories) {
  button.addEventListener("click", () => { activeCategory = button.dataset.categoryFilter; filterSkills(); });
}
document.querySelector("#reset-filters").addEventListener("click", () => {
  search.value = "";
  activeCategory = "all";
  filterSkills();
  search.focus();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "/" && !event.ctrlKey && !event.metaKey && !event.altKey && !event.target.closest("input, textarea, [contenteditable]")) {
    event.preventDefault();
    search.focus();
  }
});

const agentButtons = [...document.querySelectorAll("[data-agent]")];
function selectAgent(agent) {
  for (const button of agentButtons) button.setAttribute("aria-pressed", String(button.dataset.agent === agent));
  for (const panel of document.querySelectorAll("[data-install]")) panel.hidden = panel.dataset.install !== agent;
}
for (const button of agentButtons) button.addEventListener("click", () => selectAgent(button.dataset.agent));
for (const button of document.querySelectorAll("[data-copy]")) {
  button.hidden = false;
  button.addEventListener("click", async () => {
    const code = document.getElementById(button.dataset.copy);
    const status = document.querySelector("#copy-status");
    try {
      await navigator.clipboard.writeText(code.textContent);
      button.textContent = "Copied!";
      status.textContent = "Installation commands copied.";
    } catch {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(code);
      selection.removeAllRanges();
      selection.addRange(range);
      status.textContent = "Clipboard unavailable. Commands selected; copy them manually.";
    }
    setTimeout(() => { button.textContent = "Copy"; }, 2000);
  });
}
for (const id of ["category-filters", "search-controls", "agent-picker"]) document.getElementById(id).hidden = false;
selectAgent("claude");
filterSkills();
