import re

with open('templates/featured_deals.html', 'r') as f:
    html = f.read()

# I want to rewrite the inner card body of featured deals.
pattern = re.compile(
    r'<div class="card-body d-flex flex-column" style="background-color: #f8f9fa;">.*?'
    r'(<!-- ACTION BUTTONS -->)',
    re.DOTALL
)

replacement = r'''<div class="card-body d-flex flex-column h-100" style="background-color: #f8f9fa;">
              <!-- Data Logic to determine display strings -->
              {% set original_price = p.get('original_price') %}
              {% set discount_label = p.get('discount_label') or (p.get('discount_percent') ~ '% off' if
              p.get('discount_percent') is not none else '') %}
              {% set offer_obj = p.get('offer') if p.get('offer') is mapping else None %}
              {% set offer = p.get('offer', '') %}
              {% set discount_tiers = p.get('discount_tiers') %}
              
              <!-- Logic for Multibuy (Buy X Get Y) -->
              {% set offer_x = offer_obj.x if offer_obj is not none else (p.get('buy_quantity') or p.get('multibuy_buy')
              or '') %}
              {% set offer_y = offer_obj.y if offer_obj is not none else (p.get('free_quantity') or p.get('multibuy_free')
              or '') %}
              {% set offer_type = offer_obj.type if offer_obj is not none else ('buyXgetY' if offer_x and offer_y else '')
              %}
              {% set is_buy_get_deal = (offer_type == 'buyXgetY') or ('buy' in offer|lower and ('get' in offer|lower or
              'free' in offer|lower or '+' in offer)) %}
              
              <!-- TITLE & BADGE -->
              <div class="d-flex justify-content-between align-items-start mb-3">
                <div class="d-flex flex-column gap-1" style="flex: 1;">
                  <h6 class="card-title mb-0 fw-bold text-dark" style="font-size: 0.95rem; line-height: 1.3; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;">{{ p.get('title') or p.get('name','') }}</h6>
                </div>
                <button type="button" class="btn btn-link p-0 text-muted ms-2 js-report-btn"
                  title="Report inaccurate price"
                  data-product-id="{{ p.get('id') }}"
                  data-product-name="{{ p.get('title') or p.get('name','')|e }}"
                  data-product-stores='{{ p.get("stores")|tojson|forceescape if p.get("stores") else "[]" }}'>
                  <i class="bi bi-exclamation-triangle" style="font-size: 1.1rem;"></i>
                </button>
              </div>
              
              <div class="flex-grow-1">
              <!-- STORE & PRICE DISPLAY LOGIC -->
              {% if p.get('stores') and p.get('stores')|length > 0 %}
              {% set sorted_stores = p.get('stores')|sort(attribute='price')|list %}
              {% set cheapest_price = sorted_stores[0].get('price')|float %}
              <div class="d-flex flex-column gap-2 w-100">
                {% for store in sorted_stores[:3] %}
                {% set store_price = store.get('price')|float %}
                {% set is_cheapest = store_price == cheapest_price %}
                <div class="d-flex justify-content-between align-items-start w-100">
                  <span class="{% if is_cheapest %}text-success fw-bold{% else %}text-secondary fw-medium{% endif %} text-truncate" style="font-size: 0.85rem; max-width: 65%; font-family: system-ui, -apple-system, sans-serif; line-height: 1.2;">
                     {{ store.get('store') or store.get('name') }}
                  </span>
                  <div class="d-flex align-items-start">
                    <span class="fw-bold {% if is_cheapest %}text-success{% else %}text-dark{% endif %}" style="font-size: 0.95rem; line-height: 1.2;">
                      €{{ "%.2f"|format(store.get('price')) }}
                    </span>
                  </div>
                </div>
                {% endfor %}
              </div>
              {% if sorted_stores|length > 1 %}
              {% set save_amount = sorted_stores[-1].get('price')|float - cheapest_price %}
              {% if save_amount > 0 %}
              <div class="border-top pt-2 mt-2 mb-2 w-100">
                <span class="text-success fw-bold d-flex align-items-center justify-content-center" style="font-size: 0.85rem;">
                  <i class="bi bi-graph-down-arrow me-1" style="font-size: 0.95rem;"></i> Save up to €{{ "%.2f"|format(save_amount) }}
                </span>
              </div>
              {% endif %}
              {% endif %}
              {% else %}
              <div class="d-flex justify-content-between align-items-start mb-3">
                  <span class="text-muted fw-medium text-truncate" style="font-size: 0.85rem; max-width: 60%; font-family: system-ui, -apple-system, sans-serif; line-height: 1.2;">
                      {{ p.get('store') or p.get('source','') }}
                  </span>
                  <div class="d-flex justify-content-end">
                    <div class="d-flex align-items-center gap-2">
                        {% if is_buy_get_deal %}
                        <div class="fw-bold" style="color: #6d28d9; line-height: 1.2; font-size: 0.95rem;">
                          €{{ '%.2f' % (p.get('price') or 0) }} <span style="font-size: 0.75rem; font-weight: normal; color: #64748b;">each</span>
                        </div>
                        <div class="text-secondary small fw-medium" style="background: rgba(109, 40, 217, 0.1); padding: 2px 6px; border-radius: 4px;">{{ offer }}</div>
                        {% else %}
                        <div class="fw-bold" style="color: #6d28d9; line-height: 1.2; font-size: 0.95rem;">
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
              </div>
              
              \1'''

new_html, count = pattern.subn(replacement, html)
print("Replaced featured deals:", count)
with open('templates/featured_deals.html', 'w') as f:
    f.write(new_html)
