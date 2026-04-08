import re

with open('templates/book.html', 'r', encoding='utf-8') as f:
    text = f.read()

old_logic = r'''          let ingredientsHtml = '';
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
          }'''

new_logic = r'''          let ingredientsHtml = '';
          let unmatchedHtml = '';
          if (recipe.ingredients && recipe.ingredients.length > 0) {
              const matchedItems = recipe.ingredients.filter(item => !!item.product);
              const unmatchedItems = recipe.ingredients.filter(item => !item.product);
              
              if (matchedItems.length > 0) {
                  ingredientsHtml = matchedItems.map(item => {
                      const name = escapeHtml(item.original || item.name || "Item");
                      const price = parseFloat(item.product.price_val || item.product.price || 0).toFixed(2);
                      return `
                          <div class="d-flex justify-content-between py-1 border-bottom border-light">
                              <span><i class="bi bi-check-circle-fill me-2" style="color:#10b981;"></i><a href="/product/${item.product._id || item.product.id}?store=${encodeURIComponent(item.product.store || 'Unknown')}" class="text-decoration-none text-dark">${name}</a></span>
                              <span class="fw-bold">€${price}</span>
                          </div>
                      `;
                  }).join('');
              } else {
                  ingredientsHtml = '<p class="text-muted">No matched products.</p>';
              }
              
              if (unmatchedItems.length > 0) {
                  unmatchedHtml = `
                    <div class="mt-3">
                      <h6 class="fw-bold mb-2" style="color:#64748b;"><i class="bi bi-cart-x me-2"></i>Additional Products</h6>
                      <div class="d-flex flex-wrap gap-1">
                          ${unmatchedItems.map(item => {
                              const name = escapeHtml(item.original || item.name || "Item");
                              return `<a href="/home?q=${encodeURIComponent(name)}" class="badge bg-light text-dark border p-1 px-2 text-decoration-none hover-bg-light" style="font-size: 0.75rem;">${name}</a>`;
                          }).join('')}
                      </div>
                    </div>
                  `;
              }
          } else {
              ingredientsHtml = '<p class="text-muted">No ingredients.</p>';
          }'''

text = text.replace(old_logic, new_logic)

# We also need to inject unmatchedHtml right below ingredientsHtml in the template.
old_template = r'''            <h6 class="fw-bold mb-2" style="color:#4f46e5;"><i class="bi bi-basket-fill me-2"></i>Shopping List</h6>
            <div class="mb-4 small">
                ${ingredientsHtml}
            </div>

            <div class="mt-auto text-center">'''

new_template = r'''            <h6 class="fw-bold mb-2" style="color:#4f46e5;"><i class="bi bi-basket-fill me-2"></i>Shopping List</h6>
            <div class="mb-2 small">
                ${ingredientsHtml}
            </div>
            ${unmatchedHtml}

            <div class="mt-auto text-center mt-4">'''

text = text.replace(old_template, new_template)

with open('templates/book.html', 'w', encoding='utf-8') as f:
    f.write(text)
