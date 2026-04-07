import re

with open('templates/recipe_planner.html', 'r', encoding='utf-8') as f:
    text = f.read()

old_layout = r'''    <div class="d-inline-flex bg-white rounded-pill p-1 mb-4 shadow-sm">
      <button type="button" class="btn btn-primary rounded-pill px-4 fw-bold" id="tabRecipe" onclick="toggleSearch('recipe')">By Recipe</button>
      <button type="button" class="btn btn-light text-dark rounded-pill px-4 fw-bold border-0 bg-transparent" id="tabBudget" onclick="toggleSearch('budget')">By Budget</button>
        <button type="button" class="btn btn-light text-dark rounded-pill px-4 fw-bold border-0 bg-transparent" id="tabBook" onclick="toggleSearch('book')">My Recipe Book</button>
      <input type="text" id="recipeInput"
             placeholder="e.g. Spaghetti Carbonara, Chicken Tikka Masala..." required
             autocomplete="off">
      <button type="submit" id="generateBtn">
        <i class="bi bi-search"></i> Generate
      </button>
    </form>

    <form id="budgetForm" class="search-box w-100 mx-auto position-relative d-none">
      <input type="text" id="budgetInput"
             placeholder="Enter your budget (e.g., $10 or 15€)..." required
             autocomplete="off">
      <button type="submit" id="budgetBtn" class="bg-warning text-dark border-0">
        <i class="bi bi-lightbulb-fill"></i> Get Ideas
      </button>
    </form>'''

new_layout = r'''    <form id="recipeForm" class="search-box w-100 mx-auto position-relative mb-4">
      <input type="text" id="recipeInput"
             placeholder="e.g. Spaghetti Carbonara, Chicken Tikka Masala..." required
             autocomplete="off">
      <button type="submit" id="generateBtn">
        <i class="bi bi-search"></i> Generate
      </button>
    </form>

    <form id="budgetForm" class="search-box w-100 mx-auto position-relative mb-4 d-none">
      <input type="text" id="budgetInput"
             placeholder="Enter your budget (e.g., $10 or 15€)..." required
             autocomplete="off">
      <button type="submit" id="budgetBtn" class="bg-warning text-dark border-0">
        <i class="bi bi-lightbulb-fill"></i> Get Ideas
      </button>
    </form>

    <div class="d-inline-flex bg-white rounded-pill p-1 mb-4 shadow-sm">
      <button type="button" class="btn btn-primary rounded-pill px-4 fw-bold" id="tabRecipe" onclick="toggleSearch('recipe')">By Recipe</button>
      <button type="button" class="btn btn-light text-dark rounded-pill px-4 fw-bold border-0 bg-transparent" id="tabBudget" onclick="toggleSearch('budget')">By Budget</button>
      <button type="button" class="btn btn-light text-dark rounded-pill px-4 fw-bold border-0 bg-transparent" id="tabBook" onclick="toggleSearch('book')">My Recipe Book</button>
    </div>'''

text = text.replace(old_layout, new_layout)

with open('templates/recipe_planner.html', 'w', encoding='utf-8') as f:
    f.write(text)
