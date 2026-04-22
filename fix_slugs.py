with open("templates/admin_categories.html", "r") as f:
    text = f.read()

# Hide the category slug field visually, but keep inputs
text = text.replace('<div class="mb-3">\n              <label class="form-label small fw-bold text-muted text-uppercase mb-1">Category Slug / ID <span class="text-danger">*</span></label>\n              <input type="text" class="form-control form-control-lg bg-light border" name="categoryId_new" id="field_categoryId" placeholder="e.g. dairy-eggs" required>\n           </div>', '<div class="mb-3 d-none">\n              <label class="form-label small fw-bold text-muted text-uppercase mb-1">Category Slug / ID <span class="text-danger">*</span></label>\n              <input type="text" class="form-control form-control-lg bg-light border" name="categoryId_new" id="field_categoryId" placeholder="e.g. dairy-eggs" required>\n           </div>')

# Add JS to auto-fill slug from name_en
script_add = """
<script>
document.getElementById('field_cat_name_en').addEventListener('input', function(e) {
    if (!document.getElementById('field_categoryId').readOnly) {
        document.getElementById('field_categoryId').value = e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
    }
});
</script>
"""
text = text.replace("{% endblock %}", script_add + "{% endblock %}")

with open("templates/admin_categories.html", "w") as f:
    f.write(text)

