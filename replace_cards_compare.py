import re

with open('templates/compare_prices.html', 'r') as f:
    content = f.read()

# Find everything between <h5 class="card-title ...">{{ p.get('name') ... }}</h5> and <div class="card-body pt-2 mt-auto"

pattern = re.compile(r'(<h5 class="card-title mb-0 fw-bold" style="font-size: 1rem;">.*?</h5>).*?(<div class="card-body pt-2 mt-auto" style="background-color: #fff;">)', re.DOTALL)

replacement = r'''\1
              </div>

              {% if p.get('combo_deal') %}
              <div class="mb-2">
                <span class="combo-badge"><i class="bi bi-lightning-charge-fill me-1"></i>{{ p.get('combo_deal_label') or 'Combo offer' }}</span>
              </div>
              {% endif %}

            </div>  {# unconditionally close card-body pb-0 #}

            {% if p.get('stores') %}
            <div class="px-3 pb-3 mt-2" style="background-color: #fff;">
              {% set sorted_stores = p.get('stores')|sort(attribute='price')|list %}
              <div class="d-flex flex-column gap-2 mb-3">
                {% for store in sorted_stores %}
                <div class="d-flex justify-content-between align-items-center">
                  <span class="fw-medium text-secondary" style="font-size: 0.95rem;">
                     {{ store.get('store') or store.get('name') }}
                  </span>
                  <div class="d-flex align-items-center">
                    <button type="button" class="btn btn-link p-0 text-muted me-2 js-report-btn"
                      title="Report inaccurate price"
                      data-product-id="{{ p.get('id') }}"
                      data-product-name="{{ p.get('name') or p.get('title','')|e }}"
                      data-product-stores='{{ p.get("stores")|tojson|forceescape }}'>
                      <i class="bi bi-exclamation-triangle" style="font-size: 0.85rem;"></i>
                    </button>
                    <span class="fw-bold {% if loop.first and sorted_stores|length > 1 %}text-success{% else %}text-dark{% endif %}" style="font-size: 1rem;">
                      €{{ "%.2f"|format(store.get('price')) }}
                    </span>
                  </div>
                </div>
                {% endfor %}
              </div>
              
              {% if sorted_stores|length > 1 %}
              {% set save_amount = sorted_stores[-1].get('price')|float - sorted_stores[0].get('price')|float %}
              {% if save_amount > 0 %}
              <div class="border-top pt-2 mt-2">
                <span class="text-success fw-bold d-flex align-items-center" style="font-size: 0.95rem;">
                  <i class="bi bi-graph-down-arrow me-2" style="font-size: 1.1rem;"></i> Save up to €{{ "%.2f"|format(save_amount) }}
                </span>
              </div>
              {% endif %}
              {% endif %}
            </div>
            {% endif %}

            \2'''

new_content, count = pattern.subn(replacement, content)
print("Replaced", count, "times.")

with open('templates/compare_prices.html', 'w') as f:
    f.write(new_content)
