import re

with open('templates/admin_products.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Fix duplicate checkboxes: we have a sequence of <td class="ps-4">...</td><td class="ps-2">...</td><td class="ps-2">
text = re.sub(
    r'<td class="ps-4">\s*<input class="form-check-input product-checkbox".*?</td>\s*<td class="ps-2">\s*<input class="form-check-input product-checkbox".*?</td>\s*<td class="ps-2">',
    r'<td class="ps-4">\n    <input class="form-check-input product-checkbox" type="checkbox" value="{{ p._id }}" onchange="updateBulkDeleteButton()">\n</td>\n<td class="ps-2">',
    text,
    flags=re.DOTALL
)

with open('templates/admin_products.html', 'w', encoding='utf-8') as f:
    f.write(text)
print('Cleaned up duplicate checkboxes in HTML rows')
