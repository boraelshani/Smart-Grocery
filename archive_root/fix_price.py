import re

with open('templates/recipe_planner.html', 'r', encoding='utf-8') as f:
    text = f.read()

old_price_html = r'''                              <h4 class="fw-bold text-success m-0">€${parseFloat(prod.price_val || 0).toFixed(2)}</h4>'''
new_price_html = r'''                              <h4 class="fw-bold text-success m-0">€${parseFloat(prod.price_val || prod.price || 0).toFixed(2)}</h4>'''

text = text.replace(old_price_html, new_price_html)

old_price_js = r'''                        price: prod.price_val ? parseFloat(prod.price_val).toFixed(2) : '0.00','''
new_price_js = r'''                        price: (prod.price_val || prod.price) ? parseFloat(prod.price_val || prod.price).toFixed(2) : '0.00','''

text = text.replace(old_price_js, new_price_js)

with open('templates/recipe_planner.html', 'w', encoding='utf-8') as f:
    f.write(text)
