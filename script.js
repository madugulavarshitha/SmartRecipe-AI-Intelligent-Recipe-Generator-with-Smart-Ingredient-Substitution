/**
 * Ingredient chip input.
 * Lets the user type an ingredient and press Enter/Comma to turn it into a chip.
 * Keeps a hidden input in sync as a comma-separated string for form submission.
 */
function initIngredientChips(containerId, inputId, hiddenId) {
  const container = document.getElementById(containerId);
  const input = document.getElementById(inputId);
  const hidden = document.getElementById(hiddenId);

  if (!container || !input || !hidden) return;

  let ingredients = [];

  // Pre-fill from hidden field if the form is being re-rendered after an error
  if (hidden.value) {
    ingredients = hidden.value.split(",").map(s => s.trim()).filter(Boolean);
    renderChips();
  }

  function renderChips() {
    container.innerHTML = "";
    ingredients.forEach((ing, idx) => {
      const chip = document.createElement("div");
      chip.className = "chip";
      chip.innerHTML = `🥕 ${escapeHtml(ing)} <button type="button" data-idx="${idx}" aria-label="Remove">✕</button>`;
      container.appendChild(chip);
    });
    hidden.value = ingredients.join(", ");
  }

  function addIngredient(value) {
    const clean = value.trim();
    if (!clean) return;
    if (ingredients.some(i => i.toLowerCase() === clean.toLowerCase())) return;
    ingredients.push(clean);
    renderChips();
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addIngredient(input.value);
      input.value = "";
    } else if (e.key === "Backspace" && input.value === "" && ingredients.length > 0) {
      ingredients.pop();
      renderChips();
    }
  });

  input.addEventListener("blur", function () {
    if (input.value.trim()) {
      addIngredient(input.value);
      input.value = "";
    }
  });

  container.addEventListener("click", function (e) {
    if (e.target.tagName === "BUTTON") {
      const idx = parseInt(e.target.getAttribute("data-idx"), 10);
      ingredients.splice(idx, 1);
      renderChips();
    }
  });
}

/**
 * Recipe detail "page" tabs — Ingredients / Substitutions / Steps / AI Analysis.
 * Each tab is a full section styled to feel like its own page.
 */
function initRecipeTabs() {
  const buttons = document.querySelectorAll(".tab-btn");
  const pages = document.querySelectorAll(".tab-page");
  if (!buttons.length || !pages.length) return;

  buttons.forEach(btn => {
    btn.addEventListener("click", function () {
      const target = btn.getAttribute("data-tab");

      buttons.forEach(b => b.classList.remove("active"));
      pages.forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      document.getElementById(target).classList.add("active");
    });
  });
}
