
document.addEventListener('DOMContentLoaded', () => {
    const rawRecipes = [];
    let displayRecipes = [...rawRecipes];
    let currentIndex = 0;

    const leftPage = document.getElementById('bookLeftPage');
    const rightPage = document.getElementById('bookRightPage');
    const searchInput = document.getElementById('recipeBookSearch');
    const prevBtn = document.getElementById('bookPrevBtn');
    const nextBtn = document.getElementById('bookNextBtn');
    const emptyState = document.getElementById('bookEmptyState');
    const bookShadow = document.querySelector('.grand-book-shadow');

    function escapeHtml(str) {
        if (!str) return '';
        return str.toString()
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function renderBook() {
        if (displayRecipes.length === 0) {
            if(bookShadow) bookShadow.style.display = 'none';
            if(emptyState) emptyState.style.display = 'block';
            const indicator = document.getElementById('bookPageIndicator');
            if(indicator) indicator.textContent = '';

            if(leftPage) leftPage.innerHTML = '';
            if(rightPage) rightPage.innerHTML = '';
            return;
        }
        
        if(bookShadow) bookShadow.style.display = 'block';
        const indicator = document.getElementById('bookPageIndicator');
        if(indicator) indicator.textContent = `Recipe ${currentIndex + 1} of ${displayRecipes.length}`;

        if(emptyState) emptyState.style.display = 'none';

        const recipe = displayRecipes[currentIndex];
        
        let ingredientsHtml = '';
        if (recipe.ingredients && recipe.ingredients.length > 0) {
            ingredientsHtml = recipe.ingredients.map(item => {
                const name = escapeHtml(item.original || item.name || "Item");
                const matched = !!item.product;
                if (matched) {
                    const price = parseFloat(item.product.price_val || item.product.price || 0).toFixed(2);
                    return `
                        <div class="d-flex justify-content-between py-1 border-bottom border-light">
                            <span><i class="bi bi-check-circle-fill me-2" style="color:#10b981;"></i>${name}</span>
                            <span class="fw-bold">€${price}</span>
                        </div>
                    `;
                } else {
                    return `
                        <div class="d-flex justify-content-between py-1 border-bottom border-light opacity-75">
                            <span class="text-decoration-line-through text-muted"><i class="bi bi-x-circle me-2 text-danger"></i>${name}</span>
                            <span class="text-muted">Out of stock</span>
                        </div>
                    `;
                }
            }).join('');
        } else {
            ingredientsHtml = '<p class="text-muted">No ingredients.</p>';
        }

        const totalItems = recipe.ingredients ? recipe.ingredients.length : 0;
        const totalCost = parseFloat(recipe.total_price || 0).toFixed(2);
        const title = escapeHtml(recipe.title || "Untitled Recipe");
        const rId = recipe._id ? (recipe._id.$oid || recipe._id) : "";

        if(leftPage) leftPage.innerHTML = `
            <div class="d-flex justify-content-between align-items-start mb-3">
                <h3 class="book-title-font fw-bold m-0" style="color: #1e293b; line-height: 1.2; padding-right: 15px;">${title}</h3>
                <button class="btn btn-sm btn-outline-danger border-0 rounded-circle" onclick="removeBookRecipe('${rId}')" title="Delete Recipe">
                    <i class="bi bi-trash fs-5"></i>
                </button>
            </div>
            
            <p class="text-muted small fw-bold mb-3"><i class="bi bi-calendar3 me-1"></i> Saved Recipe</p>
            
            <div class="row g-2 mb-3">
               <div class="col-6">
                  <div class="bg-white p-2 rounded-3 shadow-sm text-center border">
                      <span class="d-block small text-muted">Items</span>
                      <span class="fs-5 fw-bold">${totalItems}</span>
                  </div>
               </div>
               <div class="col-6">
                  <div class="bg-white p-2 rounded-3 shadow-sm text-center border">
                      <span class="d-block small text-muted">Cost</span>
                      <span class="fs-5 fw-bold text-success">€${totalCost}</span>
                  </div>
               </div>
            </div>

            <h6 class="fw-bold mb-2" style="color:#4f46e5;"><i class="bi bi-basket-fill me-2"></i>Shopping List</h6>
            <div class="mb-4 small">
                ${ingredientsHtml}
            </div>

            <div class="mt-auto text-center">
                <button class="btn btn-primary rounded-pill px-4 py-2 shadow-sm" onclick="setupActivePlanner()" style="background: linear-gradient(135deg, #7c3aed, #6366f1); border: 0;">
                    <i class="bi bi-arrow-repeat me-1"></i> Load to Planner
                </button>
            </div>
            
            <div class="page-num">Pg. ${(currentIndex * 2) + 1}</div>
        `;

        let instructionsHtml = '';
        if (recipe.instructions && recipe.instructions.length > 0) {
            instructionsHtml = recipe.instructions.map((step, i) => `
                <div class="d-flex mb-2">
                    <div class="fs-5 fw-bold me-2 text-danger book-title-font">${i + 1}.</div>
                    <div class="pt-1 text-secondary small" style="line-height: 1.5;">${escapeHtml(step)}</div>
                </div>
            `).join('');
        } else {
            instructionsHtml = `
                <div class="text-center text-muted mt-4 opacity-50">
                   <i class="bi bi-fire fs-2 d-block mb-2"></i>
                   <p>No instructions saved.</p>
                </div>
            `;
        }

        if(rightPage) rightPage.innerHTML = `
            <div class="mb-3 pb-2" style="border-bottom: 2px dashed #fecdd3;">
                <h5 class="fw-bold m-0" style="color: #e11d48;"><i class="bi bi-journal-text me-2"></i>Preparation</h5>
            </div>
            <div>
                ${instructionsHtml}
            </div>
            <div class="page-num">Pg. ${(currentIndex * 2) + 2}</div>
        `;

        if(prevBtn) prevBtn.style.visibility = currentIndex === 0 ? 'hidden' : 'visible';
        if(nextBtn) nextBtn.style.visibility = currentIndex === displayRecipes.length - 1 ? 'hidden' : 'visible';
    }

    if(prevBtn) prevBtn.addEventListener('click', () => {
        if (currentIndex > 0) {
            currentIndex--;
            renderBook();
        }
    });

    if(nextBtn) nextBtn.addEventListener('click', () => {
        if (currentIndex < displayRecipes.length - 1) {
            currentIndex++;
            renderBook();
        }
    });

    if(searchInput) searchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        displayRecipes = rawRecipes.filter(r => r.title && r.title.toLowerCase().includes(query));
        currentIndex = 0;
        renderBook();
    });

    window.removeBookRecipe = async function(id) {
        if(confirm('Are you sure you want to remove this recipe from your book?')) {
            try {
                const res = await fetch('/api/recipe/delete/' + id, { method: 'DELETE' });
                const data = await res.json();
                if (data.success) {
                    const indexToRemove = rawRecipes.findIndex(r => {
                        const rId = r._id?.$oid || r._id;
                        return rId === id;
                    });
                    if (indexToRemove !== -1) rawRecipes.splice(indexToRemove, 1);
                    
                    const displayIndex = displayRecipes.findIndex(r => {
                        const rId = r._id?.$oid || r._id;
                        return rId === id;
                    });
                    if (displayIndex !== -1) displayRecipes.splice(displayIndex, 1);

                    if (currentIndex >= displayRecipes.length) currentIndex = Math.max(0, displayRecipes.length - 1);
                    renderBook();
                } else {
                    alert(data.error);
                }
            } catch (e) {
                console.error(e);
                alert('Failed to delete recipe.');
            }
        }
    };

    window.setupActivePlanner = function() {
        const recipe = displayRecipes[currentIndex];
        if(!recipe) return;
        // Assuming global 'loadSavedRecipe' exists in recipe_planner.html
        if (typeof window.loadSavedRecipe === 'function') {
            window.loadSavedRecipe(recipe);
        } else {
            console.log('Cannot find loadSavedRecipe, implementing fallback.');
            // Attempt fallback to populate main form
            const input = document.getElementById('recipeInput');
            if (input) input.value = recipe.title;
            // Scroll up to main area
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    };

    renderBook();
});
