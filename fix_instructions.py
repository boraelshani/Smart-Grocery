import re

with open('templates/recipe_planner.html', 'r', encoding='utf-8') as f:
    text = f.read()

new_html = r'''
      <div id="ingredientsList">
        <!-- Javascript will inject ingredient cards here -->
      </div>
      
      <div id="recipePreparationBlock" class="mt-5 p-4 bg-white" style="border-radius: 24px; border: 1px solid #f1f5f9; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.02);">
        <h3 class="fw-bold m-0 mb-4" style="color: #1a202c;"><i class="bi bi-journal-text text-primary me-2"></i>Preparation Steps</h3>
        <div id="instructionsList" class="ps-3" style="border-left: 3px solid #e2e8f0; font-size: 1.1rem; line-height: 1.6; color: #475569;">
          <!-- JS will inject steps here -->
        </div>
      </div>
'''

target_html = r'''      <div id="ingredientsList">
        <!-- Javascript will inject ingredient cards here -->
      </div>'''

text = text.replace(target_html, new_html)

js_logic = r'''        matchedProductsData = [];

        data.results.forEach(item => {'''

js_inject = r'''        matchedProductsData = [];

        const prepBlock = document.getElementById('recipePreparationBlock');
        const instList = document.getElementById('instructionsList');
        if (prepBlock && instList) {
            instList.innerHTML = '';
            if (data.instructions && data.instructions.length > 0) {
                prepBlock.classList.remove('d-none');
                data.instructions.forEach((step, idx) => {
                    instList.innerHTML += `<div class="mb-3"><strong class="text-primary me-2">${idx+1}.</strong><span style="color: #475569;">${escapeHtml(step)}</span></div>`;
                });
            } else {
                prepBlock.classList.add('d-none');
            }
        }

        data.results.forEach(item => {'''

text = text.replace(js_logic, js_inject)

with open('templates/recipe_planner.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("Done")