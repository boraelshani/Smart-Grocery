import re

with open('templates/home.html', 'r') as f:
    content = f.read()

# Replace the block displaying prices in home.html
pattern = re.compile(r'''({%\s*if product.get\('stores'\).*?%})[\s\S]*?(<div class="d-grid mt-auto">)''', re.MULTILINE)

replacement = r'''\1
              {% set sorted_stores = product.get('stores')|sort(attribute='price')|list %}
              <div class="d-flex flex-column gap-1 mb-2 mt-2 w-100">
                {% for store in sorted_stores[:3] %}
                <div class="d-flex justify-content-between align-items-center w-100">
                  <span class="fw-medium text-secondary text-truncate" style="font-size: 0.8rem; max-width: 60%;">
                     {{ store.get('store') or store.get('name') }}
                  </span>
                  <div class="d-flex align-items-center">
                    <button type="button" class="btn btn-link p-0 text-muted me-1 js-report-btn"
                      title="Report inaccurate price"
                      data-product-id="{{ product.get('id') or product.get('_id') }}"
                      data-product-name="{{ product.get('name') or product.get('title','')|e }}"
                      data-product-stores='{{ product.get("stores")|tojson|forceescape }}'>
                      <i class="bi bi-exclamation-triangle" style="font-size: 0.75rem;"></i>
                    </button>
                    <span class="fw-bold {% if loop.first and sorted_stores|length > 1 %}text-success{% else %}text-dark{% endif %}" style="font-size: 0.85rem;">
                      €{{ "%.2f"|format(store.get('price')) }}
                    </span>
                  </div>
                </div>
                {% endfor %}
                {% if sorted_stores|length > 3 %}
                <div class="text-muted text-center w-100" style="font-size: 0.70rem;">+ {{ sorted_stores|length - 3 }} more stores</div>
                {% endif %}
              </div>
              
              {% if sorted_stores|length > 1 %}
              {% set save_amount = sorted_stores[-1].get('price')|float - sorted_stores[0].get('price')|float %}
              {% if save_amount > 0 %}
              <div class="border-top pt-1 mt-1 w-100 pb-2">
                <span class="text-success fw-bold d-flex align-items-center justify-content-center" style="font-size: 0.8rem;">
                  <i class="bi bi-graph-down-arrow me-1" style="font-size: 0.9rem;"></i> Save up to €{{ "%.2f"|format(save_amount) }}
                </span>
              </div>
              {% endif %}
              {% endif %}
              {% endif %}
              
              \2'''

new_content, count = pattern.subn(replacement, content)
print("Replaced in home.html", count, "times.")

with open('templates/home.html', 'w') as f:
    f.write(new_content)
