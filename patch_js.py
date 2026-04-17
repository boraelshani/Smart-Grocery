import re

with open('static/js/modules/compare.js', 'r', encoding='utf-8') as f:
    text = f.read()

old_code = r'''        if \(!options.length\) \{
          html \+= '<div class="alert alert-info">No single store currently covers all selected products.</div>';
          bestBasketPanel.innerHTML = html;
          return;
        \}[\s\S]*?         </div>
        `;
        bestBasketPanel.innerHTML = html;'''

new_code = '''        // TWO STOP SHOP HTML
        const twoStopOptions = Array.isArray(data.two_stop_options) ? data.two_stop_options : [];
        if (twoStopOptions.length > 0) {
          html += `
            <div class="card border-0 shadow-sm mb-3">
              <div class="card-body">
                <h6 class="fw-bold mb-3 text-primary"><i class="fas fa-route me-2"></i>Two-Stop Shop (Best Pairs)</h6>
                <div class="table-responsive">
                  <table class="table table-sm align-middle mb-0">
                    <thead class="table-light"><tr><th>Stores</th><th>Total</th><th>Details</th></tr></thead>
                    <tbody>
                      ${twoStopOptions.slice(0, 3).map(opt => {
                        return `<tr>
                          <td><span class="badge bg-secondary">${opt.store.replace(' + ', '</span> <small class="text-muted">+</small> <span class="badge bg-secondary">')}</span></td>
                          <td class="fw-bold text-success">EUR ${Number(opt.total || 0).toFixed(2)}</td>
                          <td><button class="btn btn-sm btn-outline-secondary" onclick="alert('TODO: Show breakdown modal')">View split</button></td>
                        </tr>`;
                      }).join('')}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          `;
        }

        if (!options.length) {
          html += '<div class="alert alert-info mt-3">No single store currently covers all selected products.</div>';
          bestBasketPanel.innerHTML = html;
          return;
        }

        const bestTotal = Number(options[0].total || 0);
        html += `
          <div class="card border-0 shadow-sm mt-3">
            <div class="card-body">
              <h6 class="fw-bold mb-3">Single-store basket ranking</h6>
              <div class="table-responsive">
                <table class="table table-striped align-middle mb-0">
                  <thead class="table-light"><tr><th>Store</th><th>Basket Price</th><th>Savings</th></tr></thead>
                  <tbody>
                    ${options.slice(0, 8).map((row, idx) => {
                      const total = Number(row.total || 0);
                      const savings = total - bestTotal;
                      const savingsText = idx === 0 ? 'BEST' : `+EUR ${savings.toFixed(2)}`;
                      const savingsClass = idx === 0 ? 'badge bg-success' : 'text-muted';
                      return `<tr><td><strong>${row.store}</strong></td><td>EUR ${total.toFixed(2)}</td><td><span class="${savingsClass}">${savingsText}</span></td></tr>`;
                    }).join('')}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        `;
        bestBasketPanel.innerHTML = html;'''

new_text = re.sub(old_code, new_code, text)

with open('static/js/modules/compare.js', 'w', encoding='utf-8') as f:
    f.write(new_text)

print("Split basket UI applied")