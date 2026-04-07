import re

with open('templates/recipe_planner.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Make the replace resilient
old_func = r'''    window.toggleSearch = function(mode) {
        const rForm = document.getElementById('recipeForm');
        const bForm = document.getElementById('budgetForm');
        const bBtn = document.getElementById('tabBudget');
        const rBtn = document.getElementById('tabRecipe');

        if (mode === 'budget') {
            rForm.classList.add('d-none');
            bForm.classList.remove('d-none');
            rBtn.className = 'btn btn-light text-dark rounded-pill px-4 fw-bold border-0 bg-transparent';
            bBtn.className = 'btn btn-primary rounded-pill px-4 fw-bold text-white border-0';
        } else {
            bForm.classList.add('d-none');
            rForm.classList.remove('d-none');
            bBtn.className = 'btn btn-light text-dark rounded-pill px-4 fw-bold border-0 bg-transparent';
            rBtn.className = 'btn btn-primary rounded-pill px-4 fw-bold text-white border-0';
        }
    };'''

new_func = r'''    window.toggleSearch = function(mode) {
        const rForm = document.getElementById('recipeForm');
        const bForm = document.getElementById('budgetForm');
        const bBtn = document.getElementById('tabBudget');
        const rBtn = document.getElementById('tabRecipe');
        const bkBtn = document.getElementById('tabBook');
        const resultsContainer = document.getElementById('resultsContainer');
        const savedRecipesSection = document.getElementById('savedRecipesSection') || document.getElementById('grandBookSection');

        rBtn.className = 'btn btn-light text-dark rounded-pill px-4 fw-bold border-0 bg-transparent';
        bBtn.className = 'btn btn-light text-dark rounded-pill px-4 fw-bold border-0 bg-transparent';
        if(bkBtn) bkBtn.className = 'btn btn-light text-dark rounded-pill px-4 fw-bold border-0 bg-transparent';

        if (mode === 'budget') {
            rForm.classList.add('d-none');
            bForm.classList.remove('d-none');
            if (savedRecipesSection) savedRecipesSection.classList.add('d-none');
            bBtn.className = 'btn btn-primary rounded-pill px-4 fw-bold text-white border-0';
        } else if (mode === 'book') {
            rForm.classList.add('d-none');
            bForm.classList.add('d-none');
            if (resultsContainer) resultsContainer.classList.add('d-none');
            if (savedRecipesSection) savedRecipesSection.classList.remove('d-none');
            if(bkBtn) bkBtn.className = 'btn btn-primary rounded-pill px-4 fw-bold text-white border-0';
        } else {
            bForm.classList.add('d-none');
            rForm.classList.remove('d-none');
            if (resultsContainer) resultsContainer.classList.add('d-none');
            if (savedRecipesSection) savedRecipesSection.classList.add('d-none');
            rBtn.className = 'btn btn-primary rounded-pill px-4 fw-bold text-white border-0';
        }
    };'''

text_fixed = re.sub(r'    window\.toggleSearch = function\(mode\) \{.*?    \};', new_func, text, flags=re.DOTALL)

with open('templates/recipe_planner.html', 'w', encoding='utf-8') as f:
    f.write(text_fixed)
