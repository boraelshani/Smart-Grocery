with open("templates/admin_brands.html", "r") as f:
    text = f.read()

# 1. Remove table head and body slug
text = text.replace('<th class="text-uppercase text-muted text-xs fw-bold py-3">Slug</th>', '')
text = text.replace("""                    <td>
                        <span class="badge bg-secondary bg-opacity-10 text-secondary border border-secondary border-opacity-25 px-2 py-1">{{ b.brandId }}</span>
                    </td>""", '')

# 2. Hide form slug
text = text.replace("""           <div class="mb-3">
              <label class="form-label small fw-bold text-muted text-uppercase mb-1">Brand Slug / ID <span class="text-danger">*</span></label>
              <input type="text" class="form-control form-control-lg bg-light border" name="brandId_new" id="field_brandId" placeholder="e.g. coca-cola" required>
              <small class="text-muted mt-1 text-xs">Used internally to link products. Must be unique.</small>
           </div>""", """           <div class="mb-3 d-none">
              <label class="form-label small fw-bold text-muted text-uppercase mb-1">Brand Slug / ID <span class="text-danger">*</span></label>
              <input type="text" class="form-control form-control-lg bg-light border" name="brandId_new" id="field_brandId" placeholder="e.g. coca-cola" required>
              <small class="text-muted mt-1 text-xs">Used internally to link products. Must be unique.</small>
           </div>""")

script_add = """
<script>
document.getElementById('field_brand_name_en').addEventListener('input', function(e) {
    if (!document.getElementById('field_brandId').readOnly) {
        document.getElementById('field_brandId').value = e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
    }
});
</script>
"""
text = text.replace("{% endblock %}", script_add + "{% endblock %}")

with open("templates/admin_brands.html", "w") as f:
    f.write(text)

