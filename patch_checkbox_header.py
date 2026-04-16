import re

with open('templates/admin_products.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Fix duplicate headers
pattern = r'(<th class="py-3 ps-4" style="width: 40px;">\s*<input class="form-check-input" type="checkbox".*?</th>\s*<th class="text-uppercase text-muted text-xs fw-bold py-3 ps-2".*?>.*?</th>)\s*<th class="text-uppercase text-muted text-xs fw-bold py-3 ps-2".*?>.*?</th>'
text = re.sub(pattern, r'\1', text, flags=re.DOTALL)

with open('templates/admin_products.html', 'w', encoding='utf-8') as f:
    f.write(text)
print('Fixed duplicate headers')
