import re

with open('templates/compare_prices.html', 'r') as f:
    text = f.read()

pattern = r"""\s*\{\% if p\.get\('stores'\) \%\}\s*<!-- Store Link injected below pb-0, inside card directly, or inside a new section -->\s*<div class="px-3 pb-2 pt-1" style="background-color: #fff;">\s*<a href="\{\{ url_for\('main\.product_detail', product_id=p\.get\('id'\)\) \}\}".*?</a>\s*</div>\s*\{\% endif \%\}"""

replacement = """              {% if p.get('stores') %}
              <!-- Stores Expanded Section -->
              <div class="px-3 pb-2 pt-1" style="background-color: #fff;">
                {% set sorted_stores = p.get('stores')|sort(attribute='price') %}
                {% set cheapest_store = sorted_stores[0] %}
                
                <div class="d-flex align-items-center justify-content-between p-2 rounded mb-2" style="background: #f8f9fa; border: 1px solid #eee;">
                  <div class="d-flex align-items-center gap-2">
                    <img src="{{ prefer_processed(cheapest_store.get('logo') or cheapest_store.get('store_image') or url_for('static', filename='placeholder.svg')) }}" 
                         alt="{{ cheapest_store.get('store') or cheapest_store.get('name') }}" 
                         style="width: 24px; height: 24px; object-fit: contain; border-radius: 4px;">
                    <span class="fw-semibold small text-truncate" style="max-width: 100px;">{{ cheapest_store.get('store') or cheapest_store.get('name') }}</span>
                  </div>
                  <div class="text-end">
                    <span class="fw-bold text-success d-block lh-1">€{{ cheapest_store.get('price') }}</span>
                    {% if cheapest_store.get('normalized_unit_price') %}
                    <small class="text-muted" style="font-size: 0.65rem;">({{ cheapest_store.get('normalized_unit_label') }}: €{{ "%.2f"|format(cheapest_store.get('normalized_unit_price')) }})</small>
                    {% endif %}
                  </div>
                </div>
                
                {% if sorted_stores|length > 1 %}
                <button class="btn btn-sm w-100 fw-medium d-flex align-items-center justify-content-between" 
                   type="button" data-bs-toggle="collapse" data-bs-target="#stores-collapse-{{ p.get('id') }}" aria-expanded="false"
                   style="background-color: #f8f6ff; color: #7c3aed; border: 1px solid #e9d5ff; border-radius: 8px; padding: 6px 10px; font-size: 0.85rem;"
                   onclick="this.querySelector('.bi-chevron-down').classList.toggle('rotate-180')">
                   <span><i class="bi bi-chevron-down transition-transform me-1" style="transition: transform 0.2s;"></i> Compare {{ sorted_stores|length - 1 }} other store{{ 's' if (sorted_stores|length - 1) != 1 else '' }}</span>
                   <span class="text-xs opacity-75">Click to view</span>
                </button>

                <div class="collapse mt-2" id="stores-collapse-{{ p.get('id') }}">
                  <div class="d-flex flex-column gap-2">
                    {% for s in sorted_stores[1:] %}
                    <div class="d-flex justify-content-between align-items-center">
                      <div class="d-flex align-items-center gap-2">
                        <img src="{{ prefer_processed(s.get('logo') or s.get('store_image') or url_for('static', filename='placeholder.svg')) }}" 
                             alt="{{ s.get('store') or s.get('name') }}" 
                             style="width: 18px; height: 18px; object-fit: contain; border-radius: 3px; filter: grayscale(20%);">
                        <span class="small text-muted text-truncate" style="max-width: 90px;">{{ s.get('store') or s.get('name') }}</span>
                      </div>
                      <div class="text-end">
                        <span class="fw-semibold small d-block lh-1 text-dark">€{{ s.get('price') }}</span>
                         {% if s.get('normalized_unit_price') %}
                          <small class="text-muted" style="font-size: 0.6rem;">({{ s.get('normalized_unit_label') }}: €{{ "%.2f"|format(s.get('normalized_unit_price')) }})</small>
                         {% endif %}
                      </div>
                    </div>
                    {% endfor %}
                  </div>
                </div>
                {% endif %}
              </div>
              {% endif %}"""

new_text = re.sub(pattern, replacement, text, flags=re.DOTALL)
if text == new_text:
    print("Match failed")
else:
    with open('templates/compare_prices.html', 'w') as f:
        f.write(new_text)
    print("Match succeeded")
