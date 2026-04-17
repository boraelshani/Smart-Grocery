import re

with open('templates/compare_prices.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Remove the price drop badge
html = re.sub(r'\{%\s*if\s*p\.get\(\'deal_eval\'\).*?\{%\s*endif\s*%\}', '', html, flags=re.DOTALL)

# Add the modal and chart script
modal = '''
<!-- Price history modal -->
<div class="modal fade" id="priceHistoryModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header border-0 shadow-sm" style="background: linear-gradient(135deg, #0f172a, #4338ca); color: white;">
        <h5 class="modal-title"><i class="bi bi-graph-up me-2"></i><span id="history-product-name">Price History</span></h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body p-4 bg-light">
        <canvas id="priceHistoryChart"></canvas>
      </div>
      <div class="modal-footer border-0 p-3 bg-light d-flex justify-content-between">
        <small class="text-muted"><i class="bi bi-info-circle me-1"></i>30-day forecast simulation</small>
        <button type="button" class="btn btn-secondary rounded-pill px-4" data-bs-dismiss="modal">Close</button>
      </div>
    </div>
  </div>
</div>
'''

script = '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>'

if 'priceHistoryModal' not in html:
    html = html.replace('{% block scripts %}', f'{modal}\n{{% block scripts %}}\n{script}\n')

with open('templates/compare_prices.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Patch applied.")