import re
import sys

with open('templates/book.html', 'r', encoding='utf-8') as f:
    text = f.read()

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
                  ingredientsHtml = '<p class="text-muted" style="font-size:0.9rem;">No matched products.</p>';
              }
              
              if (unmatchedItems.length > 0) {
                  unmatchedHtml = `
                    <div class="mt-3">
                      <h6 class="fw-bold mb-2" style="color:#64748b;"><i class="bi bi-cart-x me-2"></i>Additional Products</h6>
                      <div class="d-flex flex-wrap gap-1">
                          ${unmatchedItems.map(item => {
                              const name = escapeHtml(item.original || item.name || "Item");
                              return `<a href="/home?q=${encodeURIComponent(name)}" class="badge bg-light text-dark border p-1 px-2 text-decoration-none hover-bg-light shadow-sm" style="font-size: 0.75rem;">${name}</a>`;
                          }).join('')}
                      </div>
                    </div>
                  `;
              }
          } else {
              ingredientsHtml = '<p class="text-muted">No ingredients.</p>';
          }'''

# Replace the JS logic
text_new = re.sub(
    r'let ingredientsHtml = \'\';(.*?)ingredientsHtml = \'<p class="text-muted">No ingredients.</p>\';\s+}',
    new_logic,
    text,
    flags=re.DOTALL
)

# Also update the HTML part inserting unmatchedHtml
text_new = re.sub(
    r'<div class="mb-4 small">\s*\$\{ingredientsHtml\}\s*</div>\s*<div class="mt-auto text-center">',
    r'''<div class="mb-2 small">
                  ${ingredientsHtml}
              </div>
              ${unmatchedHtml}

              <div class="mt-auto text-center mt-4">''',
    text_new,
    flags=re.DOTALL
)

if text != text_new:
    with open('templates/book.html', 'w', encoding='utf-8') as f:
        f.write(text_new)
    print("Replaced successfully!")
else:
    print("No changes made. regex failed.")
