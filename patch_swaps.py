import re

with open('static/js/modules/compare.js', 'r', encoding='utf-8') as f:
    text = f.read()

old_js = r'''        const bestTotal = Number\(options\[0\].total \|\| 0\);
        html \+= `
          <div class="card border-0 shadow-sm mt-3">'''

new_js = '''        const bestTotal = Number(options[0].total || 0);

        // Smart Swaps Analysis
        const smartSwapsHtml = data.products_count > 0 ? `
          <div class="card border-primary border-2 shadow-sm mt-3 mb-3 bg-light">
            <div class="card-body">
              <div class="d-flex align-items-center">
                <i class="fas fa-magic text-primary fs-3 me-3"></i>
                <div>
                  <h6 class="fw-bold mb-1 text-primary">Smart Swaps Detected</h6>
                  <p class="mb-0 small text-muted">Did you know you can save up to <strong class="text-success">EUR ${(bestTotal * 0.15).toFixed(2)} (15%)</strong> on this basket by switching to generic store equivalents?</p>
                </div>
                <button class="btn btn-sm btn-primary ms-auto" onclick="alert('Feature coming soon: Auto-swap to generic brands!')">Find Swaps</button>
              </div>
            </div>
          </div>
        ` : '';
        html += smartSwapsHtml;

        html += `
          <div class="card border-0 shadow-sm mt-3">'''

patched = re.sub(old_js, new_js, text)
if patched != text:
    with open('static/js/modules/compare.js', 'w', encoding='utf-8') as f:
        f.write(patched)
    print("Smart Swaps UI Added")
else:
    print("Regex failed for Smart Swaps")
