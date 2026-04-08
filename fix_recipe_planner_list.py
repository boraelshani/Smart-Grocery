import re

with open('templates/recipe_planner.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Make sure we add a container for additional products
# Below the ingredientsList, we need a new div `<div id="additionalProductsSection" class="mt-4 d-none">...</div>`

old_html_list = r'''      <div id="ingredientsList">
        <!-- Javascript will inject ingredient cards here -->
      </div>
      
      <div id="recipePreparationBlock" class="mt-5 p-4 bg-white" style="border-radius: 24px; border: 1px solid #f1f5f9; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.02);">'''

new_html_list = r'''      <div id="ingredientsList">
        <!-- Javascript will inject ingredient cards here -->
      </div>

      <div id="additionalProductsSection" class="mt-4 p-4 bg-white d-none" style="border-radius: 24px; border: 1px solid #f1f5f9; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.02);">
        <h4 class="fw-bold mb-3" style="color: #1a202c;"><i class="bi bi-plus-circle text-secondary me-2"></i>Additional Ingredients</h4>
        <p class="text-muted small mb-3">These recipe items were not found directly in our catalog. You might need to pick them up separately.</p>
        <div id="additionalProductsList" class="d-flex flex-wrap gap-2">
          <!-- JS will inject badges here -->
        </div>
      </div>
      
      <div id="recipePreparationBlock" class="mt-5 p-4 bg-white" style="border-radius: 24px; border: 1px solid #f1f5f9; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.02);">'''

text = text.replace(old_html_list, new_html_list)

# Now refactor renderResults
old_js = r'''        ingredientsList.innerHTML = '';
        matchedProductsData = [];

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

        data.results.forEach(item => {
            const card = document.createElement('div');
            card.className = 'ingredient-card';

            const originalName = escapeHtml(item.original);
            const isMatched = !!item.matched_product;
            
            let bodyHTML = '';
            
            if (isMatched) {
                const prod = item.matched_product;
                matchedProductsData.push(prod);
                
                const storeBadgeClass = prod.store === 'Billa' ? 'bg-warning text-dark' : 'text-white';
                const storeBadgeStyle = prod.store !== 'Billa' ? 'background: linear-gradient(135deg, #7c3aed, #6366f1);' : '';
                const imageUrl = prod.image_url && prod.image_url.startsWith('http') ? prod.image_url : '/static/img/placeholder.png';
                
                bodyHTML = `
                    <div class="ingredient-header">
                        <span class="d-flex align-items-center" style="color: #475569;"><i class="bi bi-magic me-2 fs-5" style="color: #7c3aed;"></i>${originalName}</span>
                        <span class="badge ${storeBadgeClass} rounded-pill shadow-sm badge-store" style="${storeBadgeStyle}"><i class="bi bi-shop me-1"></i>${escapeHtml(prod.store)}</span>
                    </div>
                    <div class="ingredient-body">
                        <img src="${imageUrl}" class="matched-product-img" alt="Product Image">
                        <div class="flex-grow-1">
                            <h5 class="mb-1 fw-bold" style="color: #1a202c;">${escapeHtml(prod.name)}</h5>
                            <p class="text-muted mb-0"><i class="bi bi-tag text-secondary me-1"></i>${escapeHtml(prod.brand || 'No Brand')}</p>
                        </div>
                        <div class="text-end">
                            <h4 class="fw-bold text-success m-0">€${parseFloat(prod.price_val || prod.price || 0).toFixed(2)}</h4>
                        </div>
                    </div>
                `;
            } else {
                  card.classList.add('unmatched-card', 'opacity-75'); // slightly faded but not crossed out
                  bodyHTML = `
                      <div class="ingredient-header">
                          <span class="d-flex align-items-center" style="color: #475569; font-weight: 500;"><i class="bi bi-bookmark text-secondary me-2 fs-5"></i>${originalName}</span>
                          <span class="badge rounded-pill" style="background: #f1f5f9; color: #64748b; border: 1px solid #e2e8f0; font-weight: 600;"><i class="bi bi-info-circle me-1"></i>Not in Catalog</span>
                      </div>
                      <div class="ingredient-body justify-content-center py-3">
                           <div class="text-center text-muted">
                               <span class="fw-medium" style="font-size: 0.9rem;">This item is required for the recipe, but is not currently available in our system.</span>
                    </div>
                `;
            }

            card.innerHTML = bodyHTML;
            ingredientsList.appendChild(card);
        });'''

new_js = r'''        ingredientsList.innerHTML = '';
        const addSection = document.getElementById('additionalProductsSection');
        const addList = document.getElementById('additionalProductsList');
        if(addList) addList.innerHTML = '';
        if(addSection) addSection.classList.add('d-none');
        matchedProductsData = [];

        let hasUnmatched = false;

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

        data.results.forEach(item => {
            const originalName = escapeHtml(item.original);
            const isMatched = !!item.matched_product;
            
            if (isMatched) {
                const prod = item.matched_product;
                matchedProductsData.push(prod);
                
                const card = document.createElement('div');
                card.className = 'ingredient-card';
                card.style.cursor = 'pointer';
                const storeBadgeClass = prod.store === 'Billa' ? 'bg-warning text-dark' : 'text-white';
                const storeBadgeStyle = prod.store !== 'Billa' ? 'background: linear-gradient(135deg, #7c3aed, #6366f1);' : '';
                const imageUrl = prod.image_url && prod.image_url.startsWith('http') ? prod.image_url : '/static/img/placeholder.png';
                
                card.innerHTML = `
                    <a href="/product/${prod._id || prod.id}" style="text-decoration: none; color: inherit; display: block;">
                        <div class="ingredient-header">
                            <span class="d-flex align-items-center" style="color: #475569;"><i class="bi bi-magic me-2 fs-5" style="color: #7c3aed;"></i>${originalName}</span>
                            <span class="badge ${storeBadgeClass} rounded-pill shadow-sm badge-store" style="${storeBadgeStyle}"><i class="bi bi-shop me-1"></i>${escapeHtml(prod.store)}</span>
                        </div>
                        <div class="ingredient-body">
                            <img src="${imageUrl}" class="matched-product-img" alt="Product Image">
                            <div class="flex-grow-1">
                                <h5 class="mb-1 fw-bold" style="color: #1a202c;">${escapeHtml(prod.name)}</h5>
                                <p class="text-muted mb-0"><i class="bi bi-tag text-secondary me-1"></i>${escapeHtml(prod.brand || 'No Brand')}</p>
                            </div>
                            <div class="text-end">
                                <h4 class="fw-bold text-success m-0">€${parseFloat(prod.price_val || prod.price || 0).toFixed(2)}</h4>
                            </div>
                        </div>
                    </a>
                `;
                ingredientsList.appendChild(card);
            } else {
                hasUnmatched = true;
                if(addList) {
                    addList.innerHTML += `<span class="badge bg-light text-dark border p-2 shadow-sm" style="font-size: 0.9rem;"><i class="bi bi-cart-x me-1 text-danger"></i> ${originalName}</span>`;
                }
            }
        });
        
        if (hasUnmatched && addSection) {
            addSection.classList.remove('d-none');
        }'''

text = text.replace(old_js, new_js)

with open('templates/recipe_planner.html', 'w', encoding='utf-8') as f:
    f.write(text)
