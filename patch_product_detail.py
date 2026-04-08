import re

with open("templates/product_detail.html", "r") as f:
    text = f.read()

# I want to update the store card HTML to render deals.
replacement = """                  <div class="card-store-name" title="{{ store.store or store.name }}">{{ store.store or store.name }}</div> <!-- Retailer name label -->
                  <div class="card-price mb-2">€{{ store.price }}</div> <!-- Retailer-specific product price -->

                  {% if store.get('has_deal') %}
                  <div class="offer-badge mb-2 d-flex flex-column align-items-center justify-content-center" style="border: 2px dashed #ff4757; border-radius: 8px; padding: 4px; background: #fff5f5;">
                    <div class="d-flex align-items-center gap-2">
                        <span class="badge bg-danger px-2 py-1"><i class="bi bi-fire"></i> {{ store.get('discount_label', 'Hot Deal!') }}</span>
                        {% if store.get('original_price') %}
                        <span class="text-muted text-decoration-line-through fw-bold" style="font-size:0.8rem">€{{ "%.2f"|format(store.original_price|float) }}</span>
                        {% endif %}
                    </div>
                    {% if store.get('valid_until') %}
                    <small class="text-danger fw-bold mt-1" style="font-size: 0.75rem;"><i class="bi bi-clock-history"></i> Ends: {{ store.valid_until }}</small>
                    {% endif %}
                  </div>
                  {% endif %}

                  {# External Link to Store Website (if available) #}"""

text = re.sub(r"                  <div class=\"card-store-name\".*?\{\# External Link to Store Website \(if available\) \#\}", replacement, text, flags=re.DOTALL)

with open("templates/product_detail.html", "w") as f:
    f.write(text)
