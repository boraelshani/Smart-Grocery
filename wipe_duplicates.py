import re

with open('templates/compare_prices.html', 'r') as f:
    text = f.read()

# I see what I did. By using a replacement that had the full block of BOTH the inner HTML *and* the `{% endfor %}`,
# then doing `start_str + r'.*?\{% endfor %\}'`, I pasted it back. Wait, let me check if I doubled the `endfor`.

# The easiest and most bulletproof fix: 
# 1) Checkout fresh.
import subprocess
import os

subprocess.run(["git", "checkout", "HEAD", "templates/compare_prices.html"])

# 2) Only remove the Modal. Use explicit fixed string to be safe.
with open('templates/compare_prices.html', 'r') as f:
    clean_text = f.read()

modal_start = clean_text.find('<div class="modal fade" id="priceReportModal"')
if modal_start != -1:
    modal_end_marker = '<!-- JavaScript Dependencies -->'
    modal_end = clean_text.find(modal_end_marker, modal_start)
    if modal_end != -1:
        clean_text = clean_text[:modal_start] + clean_text[modal_end:]

# 3) Safely rewrite ONLY the inside of `card-body pb-0` until `{# unconditionally close card-body pb-0 #}`
# Looking at the original diff, it was:
# `<div class="card-body pb-0" style="background-color: #fff;">`
# to `{% if p.get('stores') %}`
# BUT WE ALSO wanted to rewrite the `{% if p.get('stores') %}` block.

# Let's extract the full snippet to replace from the ORIGINAL exact text.
import re
target_regex = r'<div class="card-body pb-0" style="background-color: #fff;">.*?</div>  \{# unconditionally close card-body pb-0 #\}\s*\{% if p\.get\(' + r"'" + r'stores' + r"'" + r'\) %\}.*?<!-- Stores Expanded Section -->.*?</div>.*?\{% endif %\}.*?<div class="card-body pt-2 mt-auto" style="background-color: #fff;">.*?<div class="mt-auto">.*?(?=<div class="d-flex flex-column gap-2">)'
pattern = re.compile(target_regex, re.DOTALL)

def replacer(match):
    s = match.group(0)
    # Return our brand new block ending JUST BEFORE `<div class="d-flex flex-column gap-2">` which holds the buttons
    return r'''<div class="card-body d-flex flex-column h-100" style="background-color: #fff;">
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
                '''

new_text, count = pattern.subn(replacer, clean_text)
if count > 0:
    print(f"Replaced {count} instances safely")
    with open('templates/compare_prices.html', 'w') as f:
        f.write(new_text)
else:
    print("Failed to replace safely, attempting simpler regex")
    
    # Simpler regex approach catching just the body content
    target_regex = r'<div class="card-body pb-0" style="background-color: #fff;">.*?<div class="d-flex flex-column gap-2">'
    new_text, count = re.subn(target_regex, replacer(re.match(r'', '')).rstrip() + '<div class="d-flex flex-column gap-2">', clean_text, flags=re.DOTALL)
    print(f"Fallback replaced {count} instances safely")
    with open('templates/compare_prices.html', 'w') as f:
        f.write(new_text)

