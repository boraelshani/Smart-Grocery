import re

with open('templates/featured_deals.html', 'r') as f:
    content = f.read()

# remove old report button
pattern1 = re.compile(r'<button type="button" class="btn btn-sm text-secondary js-report-btn"[\s\S]*?<i class="bi bi-flag"></i>\s*</button>')
content = pattern1.sub('', content)

# update store and price logic
pattern2 = re.compile(r'(<!-- STORE NAME -->\s*<p class="text-muted small mb-2">{{ p.get\(\'store\'\).*?</p>\s*<!-- PRICE DISPLAY LOGIC -->\s*<div class="mb-3 d-flex flex-wrap align-items-center gap-2">)[\s\S]*?(<!-- ACTION BUTTONS -->)', re.MULTILINE)

replacement2 = r'''<!-- STORE & PRICE DISPLAY LOGIC -->
              {% if p.get('stores') and p.get('stores')|length > 0 %}
              {% set sorted_stores = p.get('stores')|sort(attribute='price')|list %}
              <div class="d-flex flex-column gap-2 mb-3 mt-2 w-100">
                {% for store in sorted_stores[:3] %}
                <div class="d-flex justify-content-between align-items-center w-100">
                  <span class="fw-medium text-secondary text-truncate" style="font-size: 0.85rem; max-width: 60%;">
                     {{ store.get('store') or store.get('name') }}
                  </span>
                  <div class="d-flex align-items-center">
                    <button type="button" class="btn btn-link p-0 text-muted me-2 js-report-btn"
                      title="Report inaccurate price"
                      data-product-id="{{ p.get('id') }}"
                      data-product-name="{{ p.get('title') or p.get('name','')|e }}"
                      data-product-stores='{{ p.get("stores")|tojson|forceescape }}'>
                      <i class="bi bi-exclamation-triangle" style="font-size: 0.85rem;"></i>
                    </button>
                    <span class="fw-bold {% if loop.first and sorted_stores|length > 1 %}text-success{% else %}text-dark{% endif %}" style="font-size: 0.95rem;">
                      €{{ "%.2f"|format(store.get('price')) }}
                    </span>
                  </div>
                </div>
                {% endfor %}
              </div>
              {% if sorted_stores|length > 1 %}
              {% set save_amount = sorted_stores[-1].get('price')|float - sorted_stores[0].get('price')|float %}
              {% if save_amount > 0 %}
              <div class="border-top pt-2 mt-1 mb-2 w-100">
                <span class="text-success fw-bold d-flex align-items-center justify-content-center" style="font-size: 0.85rem;">
                  <i class="bi bi-graph-down-arrow me-1" style="font-size: 0.95rem;"></i> Save up to €{{ "%.2f"|format(save_amount) }}
                </span>
              </div>
              {% endif %}
              {% endif %}
              {% else %}
              <div class="d-flex justify-content-between align-items-center mb-3">
                  <span class="fw-medium text-secondary text-truncate" style="font-size: 0.85rem; max-width: 60%;">
                      {{ p.get('store') or p.get('source','') }}
                  </span>
                  <div class="d-flex align-items-center">
                    <button type="button" class="btn btn-link p-0 text-muted me-2 js-report-btn"
                      title="Report inaccurate price"
                      data-product-id="{{ p.get('id') }}"
                      data-product-name="{{ p.get('title') or p.get('name','')|e }}"
                      data-product-stores='{{ p.get("stores")|tojson|forceescape if p.get("stores") else "[]" }}'>
                      <i class="bi bi-exclamation-triangle" style="font-size: 0.85rem;"></i>
                    </button>
                    <div class="d-flex align-items-center gap-2">
                        {% if is_buy_get_deal %}
                        <div class="fw-bold" style="color: #6d28d9; line-height: 1; font-size: 0.95rem;">
                          €{{ '%.2f' % (p.get('price') or 0) }} <span style="font-size: 0.75rem; font-weight: normal; color: #64748b;">each</span>
                        </div>
                        <div class="text-secondary small fw-medium" style="background: rgba(109, 40, 217, 0.1); padding: 2px 6px; border-radius: 4px;">{{ offer }}</div>
                        {% else %}
                        <div class="fw-bold" style="color: #6d28d9; line-height: 1; font-size: 0.95rem;">
                          €{{ '%.2f' % ((p.get('price') or 0)|float) }}
                        </div>
                        {% if original_price %}
                        <div class="text-muted small text-decoration-line-through mt-1">€{{ '%.2f' % (original_price|float) }}</div>
                        {% endif %}
                        {% endif %}
                    </div>
                  </div>
              </div>
              {% endif %}
              
              \2'''

content, count = pattern2.subn(replacement2, content)
print("replaced", count, "times")

with open('templates/featured_deals.html', 'w') as f:
    f.write(content)
