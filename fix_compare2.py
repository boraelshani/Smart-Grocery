import re

with open('templates/compare_prices.html', 'r') as f:
    text = f.read()

# The card-body class is "card-body pb-0" in the original file
start_str = r'<div class="card-body pb-0" style="background-color: #fff;">'
end_str = r'\{% endfor %\}'
pattern2 = re.compile(start_str + r'.*?' + end_str, re.DOTALL)

replacement2 = r'''<div class="card-body d-flex flex-column h-100" style="background-color: #fff;">
              <div class="d-flex justify-content-between align-items-start mb-3">
                <h5 class="card-title mb-0 fw-bold" style="font-size: 1rem; flex: 1;">{{ p.get('name') or p.get('title','') }}</h5>
                <button type="button" class="btn btn-link p-0 text-muted ms-2 js-report-btn"
                  title="Report inaccurate price"
                  data-product-id="{{ p.get('id') }}"
                  data-product-name="{{ p.get('name') or p.get('title','')|e }}"
                  data-product-stores='{{ p.get("stores")|tojson|forceescape }}'>
                  <i class="bi bi-exclamation-triangle" style="font-size: 1.1rem;"></i>
                </button>
              </div>

              {% if p.get('combo_deal') %}
              <div class="mb-2">
                <span class="combo-badge"><i class="bi bi-lightning-charge-fill me-1"></i>{{ p.get('combo_deal_label') or 'Combo offer' }}</span>
              </div>
              {% endif %}

              <div class="flex-grow-1 w-100">
                {% if p.get('stores') %}
                {% set sorted_stores = p.get('stores')|sort(attribute='price')|list %}
                {% set cheapest_price = sorted_stores[0].get('price')|float %}
                <div class="d-flex flex-column gap-2 w-100 mb-3">
                  {% for store in sorted_stores %}
                  {% set store_price = store.get('price')|float %}
                  {% set is_cheapest = store_price == cheapest_price %}
                  <div class="d-flex justify-content-between align-items-start w-100">
                    <span class="{% if is_cheapest %}text-success fw-bold{% else %}text-secondary fw-medium{% endif %} text-truncate" style="font-size: 0.95rem; max-width: 65%; font-family: system-ui, -apple-system, sans-serif; line-height: 1.2;">
                       {{ store.get('store') or store.get('name') }}
                    </span>
                    <div class="d-flex align-items-start">
                      <span class="fw-bold {% if is_cheapest %}text-success{% else %}text-dark{% endif %}" style="font-size: 1rem; line-height: 1.2;">
                        €{{ "%.2f"|format(store.get('price')) }}
                      </span>
                    </div>
                  </div>
                  {% endfor %}
                </div>
                
                {% if sorted_stores|length > 1 %}
                {% set save_amount = sorted_stores[-1].get('price')|float - cheapest_price %}
                {% if save_amount > 0 %}
                <div class="border-top pt-2 mt-2 w-100">
                  <span class="text-success fw-bold d-flex align-items-center" style="font-size: 0.95rem;">
                    <i class="bi bi-graph-down-arrow me-2" style="font-size: 1.1rem;"></i> Save up to €{{ "%.2f"|format(save_amount) }}
                  </span>
                </div>
                {% endif %}
                {% endif %}
                {% endif %}
              </div>

              <div class="mt-auto pt-3">
                {% if p.get('expires') %}
                <p class="text-muted small mb-3">
                  <i class="bi bi-clock-history"></i> Expires in {{ p.get('expires') }}
                </p>
                {% endif %}
                <div class="d-flex flex-column gap-2">
                  <button type="button" class="btn btn-premium btn-premium-add w-100"
                    data-name="{{ p.get('name') or p.get('title','')|e }}" data-id="{{ p.get('id') }}"
                    data-price="{{ (p.get('cheapest') and p.get('cheapest').get('price')) or p.get('price','N/A')|e }}"
                    data-initial-price="{{ (p.get('cheapest') and p.get('cheapest').get('price')) or p.get('price','N/A')|e }}"
                    data-original-price="{{ p.original_price|e if p.original_price else '' }}"
                    data-image="{{ prefer_processed(p.get('image') or (p.get('images') and p.get('images')[0]) or url_for('static', filename='placeholder.svg'))|e }}"
                    data-store=""
                    data-offer-json='{{ p.offer|tojson|forceescape if p.offer else "" }}'
                    data-tier-json='{{ p.discount_tiers|tojson|forceescape if p.discount_tiers else "" }}'
                    data-special-offer="{{ p.special_offer_type or '' }}"
                    data-offer-type="{{ p.offer_type or '' }}"
                    data-offer-x="{{ p.offer_x or '' }}"
                    data-offer-y="{{ p.offer_y or '' }}"
                    onclick="event.stopPropagation(); handleAddToCart(event, this);">
                    <i class="bi bi-cart-plus-fill"></i>Add to List
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
        {% endfor %}'''

text, count2 = pattern2.subn(replacement2, text)
print(f"Replaced layout: {count2}")

with open('templates/compare_prices.html', 'w') as f:
    f.write(text)
