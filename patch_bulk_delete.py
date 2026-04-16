import re

with open('templates/admin_products.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Add Bulk Delete Button
btn_target = '<a href="/admin/products/smart-import"'
btn_replace = '''
<button type="button" id="bulkDeleteBtn" class="btn btn-danger rounded-pill px-3 shadow-sm fw-bold me-2" style="display: none;" onclick="deleteSelectedProducts()">
    <i class="fas fa-trash-alt me-1"></i> Delete Selected
</button>
<a href="/admin/products/smart-import"
'''.strip()

content = content.replace(btn_target, btn_replace)

# Add header checkbox
th_target = '<th class="text-uppercase text-muted text-xs fw-bold py-3 ps-4">Product</th>'
th_replace = '''
<th class="py-3 ps-4" style="width: 40px;">
    <input class="form-check-input" type="checkbox" id="selectAllProducts" onchange="toggleAllProducts(this)">
</th>
<th class="text-uppercase text-muted text-xs fw-bold py-3 ps-2">Product</th>
'''.strip()

content = content.replace(th_target, th_replace)

# Add row checkbox
td_target = '<td class="ps-4">'
td_replace = '''
<td class="ps-4">
    <input class="form-check-input product-checkbox" type="checkbox" value="{{ p._id }}" onchange="updateBulkDeleteButton()">
</td>
<td class="ps-2">
'''.strip()

content = content.replace(td_target, td_replace)

# JS for toggling checkboxes
js_replace = '''
<script>
    function toggleAllProducts(source) {
        var checkboxes = document.querySelectorAll('.product-checkbox');
        for(var i=0; i<checkboxes.length; i++) {
            checkboxes[i].checked = source.checked;
        }
        updateBulkDeleteButton();
    }
    
    function updateBulkDeleteButton() {
        var anyChecked = document.querySelectorAll('.product-checkbox:checked').length > 0;
        var btn = document.getElementById('bulkDeleteBtn');
        if (anyChecked) {
            btn.style.display = 'inline-block';
        } else {
            btn.style.display = 'none';
        }
    }
    
    async function deleteSelectedProducts() {
        var checked = document.querySelectorAll('.product-checkbox:checked');
        if (checked.length === 0) return;
        if (!confirm('Are you sure you want to delete ' + checked.length + ' products?')) return;
        
        var ids = Array.from(checked).map(function(cb) { return cb.value; });
        try {
            var resp = await fetch('/admin/api/products/bulk-delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: ids })
            });
            var data = await resp.json();
            if (resp.ok) {
                alert(data.message || 'Products deleted successfully');
                window.location.reload();
            } else {
                alert(data.error || 'Delete failed');
            }
        } catch (e) {
            console.error(e);
            alert('An error occurred');
        }
    }
</script>
{% block scripts %}
'''

if 'function toggleAllProducts' not in content:
    if '{% block scripts %}' in content:
        content = content.replace('{% block scripts %}', js_replace)
    else:
        content += js_replace

with open('templates/admin_products.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done frontend admin_products.html update')
