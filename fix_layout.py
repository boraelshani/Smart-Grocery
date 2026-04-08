import re

with open('templates/compare_prices.html', 'r') as f:
    text = f.read()

# Change layout from col-lg-4 to col-xl-3 to get 4 items
text = text.replace('class="col-md-6 col-lg-4 product-card"', 'class="col-md-6 col-lg-3 col-xl-3 product-card"')

pattern = r"\{% if p\.get\('category'\) %\}.*?\{\{ p\.get\('category'\) \}\}.*?\{% endif %\}"
text = re.sub(pattern, "", text, flags=re.DOTALL)

with open('templates/compare_prices.html', 'w') as f:
    f.write(text)
print("Updated Layout.")
