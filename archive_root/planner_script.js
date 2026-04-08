
document.addEventListener('DOMContentLoaded', () => {
    const recipeForm = document.getElementById('recipeForm');
    const budgetForm = document.getElementById('budgetForm');
    const recipeInput = document.getElementById('recipeInput');
    const budgetInput = document.getElementById('budgetInput');
    const generateBtn = document.getElementById('generateBtn');
    const budgetBtn = document.getElementById('budgetBtn');
    const loadingState = document.getElementById('loadingState');
    const resultsContainer = document.getElementById('resultsContainer');
    const budgetIdeasSection = document.getElementById('budgetIdeasSection');  
    const budgetIdeasContainer = document.getElementById('budgetIdeasContainer');
    const ingredientsList = document.getElementById('ingredientsList');
    
    // State to hold valid matched products to add to standard list
    let matchedProductsData = [];

    window.toggleSearch = function(mode) {
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
    };

    if (budgetForm) {
        budgetForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const budgetVal = budgetInput.value.trim();
            if (!budgetVal) return;

            budgetBtn.disabled = true;
            budgetInput.disabled = true;
            resultsContainer.classList.add('d-none');
            if (budgetIdeasSection) budgetIdeasSection.classList.add('d-none');
            loadingState.classList.remove('d-none');
            const savedRecipesSection = document.getElementById('savedRecipesSection');
            if (savedRecipesSection) savedRecipesSection.classList.add('d-none');

            document.querySelector('#loadingState h3').textContent = "Finding meals for your budget...";
            document.querySelector('#loadingState p').textContent = "Consulting our culinary AI for cheap ideas.";

            try {
                const res = await fetch('/api/recipe/budget', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ budget: budgetVal })
                });
                const data = await res.json();
                
                loadingState.classList.add('d-none');
                
                if (data.success) {
                    budgetIdeasSection.classList.remove('d-none');
                    budgetIdeasContainer.innerHTML = '';
                    
                    data.meals.forEach(meal => {
                        budgetIdeasContainer.innerHTML += `
                            <div class="col">
                                <div class="card h-100 border-0 shadow-sm" style="border-radius: 20px; transition: transform 0.2s;">
                                    <div class="card-body p-4 text-center">
                                        <h5 class="fw-bold text-premium-dark mb-3">${meal}</h5>
                                        <button class="btn w-100 btn-outline-primary rounded-pill fw-bold" onclick="selectBudgetMeal('${escapeHtml(meal)}')">
                                            <i class="bi bi-stars me-1"></i> Cost This Meal
                                        </button>
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                } else {
                    if (typeof showNotification === 'function') showNotification('Failed to get budget ideas.', 'danger');
                }
            } catch(e) {
                console.error(e);
                loadingState.classList.add('d-none');
            } finally {
                budgetBtn.disabled = false;
                budgetInput.disabled = false;
                budgetInput.value = '';
                document.querySelector('#loadingState h3').textContent = "Building your recipe...";
                document.querySelector('#loadingState p').textContent = "Matching ingredients to the cheapest real-world products.";
            }
        });
    }

    window.selectBudgetMeal = function(mealName) {
        toggleSearch('recipe');
        recipeInput.value = mealName;
        if (budgetIdeasSection) budgetIdeasSection.classList.add('d-none');
        // trigger form submission automatically
        recipeForm.dispatchEvent(new Event('submit'));
    };

    recipeForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const recipeName = recipeInput.value.trim();
        if (!recipeName) return;

        // UI Reset
        generateBtn.disabled = true;
        recipeInput.disabled = true;
        resultsContainer.classList.add('d-none');
        loadingState.classList.remove('d-none');
        const savedRecipesSection = document.getElementById('savedRecipesSection');
        if (savedRecipesSection) savedRecipesSection.classList.add('d-none');
        matchedProductsData = [];

        try {
            const response = await fetch('/api/recipe/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ recipe: recipeName })
            });

            const data = await response.json();
            
            if (data.success) {
                renderResults(data);
                loadUserLists(); // Pre-load shopping lists for the modal
            } else {
                if (typeof showNotification === 'function') {
                    showNotification('Error: ' + (data.error || 'Failed to generate recipe.'), 'danger');
                } else {
                    alert('Error: ' + (data.error || 'Failed to generate recipe.'));
                }
            }
        } catch (error) {
            console.error(error);
            if (typeof showNotification === 'function') {
                showNotification('An unexpected error occurred. Check browser console.', 'danger');
            } else {
                alert('An unexpected error occurred. Check browser console.');
            }
        } finally {
            generateBtn.disabled = false;
            recipeInput.disabled = false;
            loadingState.classList.add('d-none');
            if(matchedProductsData.length > 0) {
                resultsContainer.classList.remove('d-none');
            }
        }
    });

    function renderResults(data) {
        currentFullRecipeData = data; // Cache globally
        document.getElementById('recipeTitle').textContent = `Ingredients for "${data.recipe}"`;
        document.getElementById('itemCountBadge').textContent = `${data.total_items} items`;
        
        document.getElementById('summaryMatchedCount').textContent = data.matched_items;
        document.getElementById('summaryUnmatchedCount').textContent = data.total_items - data.matched_items;
        document.getElementById('summaryTotal').textContent = `€${parseFloat(data.total_price || 0).toFixed(2)}`;
        
        document.getElementById('confirmItemCount').textContent = data.matched_items;

        ingredientsList.innerHTML = '';
        matchedProductsData = [];

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
                            <h4 class="fw-bold text-success m-0">€${parseFloat(prod.price_val || 0).toFixed(2)}</h4>
                        </div>
                    </div>
                `;
            } else {
                card.classList.add('unmatched-card');
                bodyHTML = `
                    <div class="ingredient-header">
                        <span class="d-flex align-items-center text-muted"><i class="bi bi-dash-circle text-secondary me-2 fs-5"></i><del>${originalName}</del></span>
                        <span class="badge rounded-pill badge-store" style="background: #f8fafc; color: #94a3b8; border: 1px solid #e2e8f0;"><i class="bi bi-ban me-1"></i>Not in stock</span>
                    </div>
                    <div class="ingredient-body justify-content-center py-4">
                         <div class="text-center text-muted">
                             <i class="bi bi-info-circle fs-4 d-block mb-2 text-secondary"></i>
                             <span class="fw-medium">No direct match found in database for this ingredient.</span>
                         </div>
                    </div>
                `;
            }

            card.innerHTML = bodyHTML;
            ingredientsList.appendChild(card);
        });
    }

    async function loadUserLists() {
        const select = document.getElementById('targetListSelect');
        select.innerHTML = '<option value="" disabled selected>Loading your lists...</option>';
        try {
            const response = await fetch('/api/get-lists');
            const data = await response.json();
            if (data.lists && data.lists.length > 0) {
                select.innerHTML = '<option value="" disabled selected>Select a list</option>';
                data.lists.forEach(list => {
                    const listId = list.id || list.listId || list._id;
                    select.innerHTML += `<option value="${listId}">${escapeHtml(list.name)}</option>`;
                });
            } else {
                select.innerHTML = '<option value="" disabled selected>No lists found. Please create one first.</option>';
            }
        } catch(e) {
            console.error('Failed to fetch lists:', e);
            select.innerHTML = '<option value="" disabled selected>Error loading lists.</option>';
        }
    }

    document.getElementById('confirmAddToListBtn').addEventListener('click', async (e) => {
        const listId = document.getElementById('targetListSelect').value;
        if (!listId) {
            if (typeof showNotification === 'function') showNotification('Please select a list first.', 'warning');
            else alert('Please select a list first.');
            return;
        }
        
        if (matchedProductsData.length === 0) {
             if (typeof showNotification === 'function') showNotification('No matched products to add.', 'danger');
             else alert('No matched products to add.');
             return;
        }

        const btn = e.target;
        const originalText = btn.innerHTML;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Adding...';
        btn.disabled = true;

        try {
            // Add items one by one or via bulk API if available. Let's do sequentially to reuse existing add endpoint logic safely.
            // Map the format standard expected by our list ADD endpoint
            let successCount = 0;
            
            for (const prod of matchedProductsData) {
                const payload = {
                    list_id: listId,
                    item: {
                        id: prod._id,
                        name: prod.name,
                        price: prod.price_val ? parseFloat(prod.price_val).toFixed(2) : '0.00',
                        store: prod.store || 'Unknown',
                        image_url: prod.image_url || '/static/img/placeholder.png'
                    }
                };

                const response = await fetch(`/api/list/add-item`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                
                if(response.ok) successCount++;
            }
            
            // Hide modal and show success toast
            const modal = bootstrap.Modal.getInstance(document.getElementById('listSelectModal'));
            modal.hide();
            
            if (typeof showNotification === 'function') {
                showNotification(`Successfully added ${successCount} items to your shopping list!`, 'success');
            } else {
                alert(`Successfully added ${successCount} items to your shopping list!`);
            }

        } catch (error) {
            console.error(error);
            if (typeof showNotification === 'function') showNotification('An error occurred while adding items to your list.', 'danger');
            else alert('An error occurred while adding items to your list.');
        } finally {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    });

    function escapeHtml(unsafe) {
        if (!unsafe) return '';
        return (unsafe + '').replace(/[&<"'>]/g, function (m) {
            return {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#039;'
            }[m];
        });
    }
    // Bind current recipe data to window for easy access
    let currentFullRecipeData = null;

    // Overwrite the renderResults slightly or just intercept it via fetch
    const originalFetch = window.fetch;

    window.saveCurrentRecipe = async function() {
        if (!currentFullRecipeData) {
            alert('Generate a recipe first!');
            return;
        }

        const btn = document.getElementById('saveRecipeBtn');
        const origHtml = btn.innerHTML;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';
        btn.disabled = true;

        try {
            const res = await fetch('/api/recipe/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(currentFullRecipeData)
            });
            const data = await res.json();
            if (data.success) {
                // simple reload to show the new recipe at bottom/top
                window.location.reload();
            } else {
                alert(data.error);
            }
        } catch (e) {
            console.error(e);
            alert('Failed to save recipe');
        } finally {
            btn.innerHTML = origHtml;
            btn.disabled = false;
        }
    };

    window.deleteSavedRecipe = async function(recipeId) {
        if (!confirm('Are you sure you want to delete this recipe?')) return;
        try {
            const res = await fetch('/api/recipe/delete/' + recipeId, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                document.getElementById('saved-recipe-' + recipeId).remove();
            } else {
                alert(data.error);
            }
        } catch (e) {
            console.error(e);
            alert('Failed to delete recipe');
        }
    };

    window.loadSavedRecipe = function(recipeData) {
        document.getElementById('recipeInput').value = recipeData.title;
        let mappedData = {
            recipe: recipeData.title,
            total_items: recipeData.total_items,
            matched_items: recipeData.matched_items,
            total_price: recipeData.total_price,
            results: recipeData.ingredients
        };        const savedRecipesSection = document.getElementById('savedRecipesSection');
        if (savedRecipesSection) savedRecipesSection.classList.add('d-none');        currentFullRecipeData = mappedData;
        if(window._renderResultsHook) window._renderResultsHook(mappedData);
    };    // Provide global access to renderResults
    window._renderResultsHook = function(data) {
        document.getElementById('loadingState').classList.add('d-none');
        document.getElementById('resultsContainer').classList.remove('d-none');
        renderResults(data);
        loadUserLists();
    };
});
