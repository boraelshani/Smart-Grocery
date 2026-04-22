import re

with open('templates/home.html', 'r') as f:
    content = f.read()

# Replace the block displaying prices in home.html
pattern = re.compile(r'''<div class="product-name product-description-clamp">\{\{ product\.get\('name', 'Premium Item'\) \}\}.*?</div>.*?<div class="d-flex flex-column gap-1 mb-2 mt-2 w-100">.*?\{% endfor %\}
                \{% if sorted_stores\|length > 3 %\}
                <div class="text-muted text-center w-100" style="font-size: 0\.70rem;">\+ \{\{ sorted_stores\|length - 3 \}\} more stores</div>
                \{% endif %\}
              </div>''', re.DOTALL)

replacement = r'''<div class="d-flex justify-content-between align-items-start mb-2">
                <div class="product-name product-description-clamp mb-0" style="flex: 1;">{{ product.get('name', 'Premium Item') }}</div>
                <button type="button" class="btn btn-link p-0 text-muted ms-2 js-report-btn"
                  title="Report inaccurate price"
                  data-product-id="{{ product.get('id') or product.get('_id') }}"
                  data-product-name="{{ product.get('name') or product.get('title','')|e }}"
                  data-product-stores='{{ product.get("stores")|tojson|forceescape }}'>
                  <i class="bi bi-exclamation-triangle" style="font-size: 1rem;"></i>
                </button>
              </div>
              
              {% if product.get('stores') and product.get('stores')|length > 0 %}
              {% set sorted_stores = product.get('stores')|sort(attribute='price')|list %}
              {% set cheapest_price = sorted_stores[0].get('price')|float %}
              <div class="d-flex flex-column gap-1 mb-2 w-100">
                {% for store in sorted_stores[:3] %}
                {% set store_price = store.get('price')|float %}
                <div class="d-flex justify-content-between align-items-center w-100">
                  <span class="{% if store_price == cheapest_price %}text-success fw-bold{% else %}text-secondary fw-medium{% endif %} text-truncate" style="font-size: 0.85rem; max-width: 65%; font-family: system-ui, -apple-system, sans-serif;">
                     {{ store.get('store') or store.get('name') }}
                  </span>
                  <div class="d-flex align-items-center">
                    <span class="fw-bold {% if store_price == cheapest_price %}text-success{% else %}text-dark{% endif %}" style="font-size: 0.9rem;">
                      €{{ "%.2f"|format(store.get('price')) }}
                    </span>
                  </div>
                </div>
                {% endfor %}
                {% if sorted_stores|length > 3 %}
                <div class="text-muted text-center w-100 mt-1" style="font-size: 0.75rem; font-weight: 500;">+ {{ sorted_stores|length - 3 }} more stores</div>
                {% endif %}
              </div>'''

new_content, count = pattern.subn(replacement, content)
print("Replaced in home.html", count, "times.")

with open('templates/home.html', 'w') as f:
    f.write(new_content)
