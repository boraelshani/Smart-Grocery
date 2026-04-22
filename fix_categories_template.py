text = """{% extends "admin_layout.html" %}

{% block admin_title %}Categories Structure{% endblock %}
{% block admin_subtitle %}Manage taxonomy and global grocery catalog{% endblock %}

{% block admin_content %}
<div class="row mb-4 align-items-center">
    <div class="col-md-8">
    </div>
    <div class="col-md-4 text-md-end">
        <button class="btn btn-primary rounded-pill px-4 shadow-sm fw-bold" onclick="prepareCategoryModal('new')" data-bs-toggle="modal" data-bs-target="#categoryModal">
            <i class="fas fa-plus me-1"></i> New Category
        </button>
    </div>
</div>

<div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
    <div class="card-body p-0">
        {% set all_cats = data.categories or [] %}
        {% set top_categories = all_cats|selectattr("parentId", "none")|list %}
        {% if not top_categories %}
            {% set top_categories = all_cats|selectattr("parentId", "equalto", "")|list %}
        {% endif %}
        {% if not top_categories %}
            {# If still nothing, some might just lack the key or have it null #}
            {% set top_categories = [] %}
            {% for c in all_cats %}
                {% if not c.parentId %}
                    {% set _ = top_categories.append(c) %}
                {% endif %}
            {% endfor %}
        {% endif %}
        
        <div class="list-group list-group-flush" id="categoryTree">
        {% macro render_category(cat, depth, all_cats) %}
            {% set children = [] %}
            {% for c in all_cats %}
                {% if c.parentId == cat.categoryId %}
                    {% set _ = children.append(c) %}
                {% endif %}
            {% endfor %}
            <div class="list-group-item border-bottom-0 py-3" style="padding-left: {{ 1.5 + depth * 2 }}rem !important; border-left: {% if depth > 0 %}2px solid #e9ecef{% else %}none{% endif %};">
                <div class="d-flex align-items-center justify-content-between">
                    <div class="d-flex align-items-center flex-grow-1 cursor-pointer" {% if children %}data-bs-toggle="collapse" data-bs-target="#collapse-{{ cat.categoryId|replace(' ', '-')|regex_replace('[^a-zA-Z0-9-]', '') }}" aria-expanded="false"{% endif %}>
                        <div class="me-3 bg-light rounded d-flex justify-content-center align-items-center overflow-hidden border shadow-sm" style="width: 48px; height: 48px;">
                            {% if cat.image_url %}
                            <img src="{{ cat.image_url }}" alt="..." style="width: 100%; height: 100%; object-fit: contain;">
                            {% else %}
                            <i class="fas fa-tags text-primary text-opacity-50 fs-5"></i>
                            {% endif %}
                        </div>
                        <div>
                            <h6 class="mb-0 fw-bold text-dark d-flex align-items-center">
                                {{ cat.name_en or cat.categoryId }}
                                {% if children %}
                                <i class="fas fa-chevron-down ms-2 fs-7 text-muted transition-transform collapse-icon"></i>
                                {% endif %}
                            </h6>
                            <span class="text-muted small">{% if children %}{{ children|length }} subcategories{% else %}No subcategories{% endif %}</span>
                        </div>
                    </div>
                    <div class="text-end ps-3">
                        <button class="btn btn-sm btn-light border shadow-sm rounded-pill text-primary fw-bold px-3 hover-primary" onclick='prepareCategoryModal("edit", {"categoryId":"{{ cat.categoryId }}", "name_en":"{{ cat.name_en }}", "name_de":"{{ cat.name_de }}", "image_url": "{{ cat.image_url }}", "parentId":"{{ cat.parentId }}"})' data-bs-toggle="modal" data-bs-target="#categoryModal">
                            <i class="fas fa-pen"></i> Edit
                        </button>
                    </div>
                </div>
            </div>
            {% if children %}
            <div class="collapse" id="collapse-{{ cat.categoryId|replace(' ', '-')|regex_replace('[^a-zA-Z0-9-]', '') }}">
                <div class="list-group list-group-flush rounded-0 bg-light bg-opacity-50">
                    {% for child in children %}
                        {{ render_category(child, depth + 1, all_cats) }}
                    {% endfor %}
                </div>
            </div>
            {% endif %}
        {% endmacro %}
        
        {% for top in top_categories %}
            {{ render_category(top, 0, all_cats) }}
        {% else %}
            <div class="text-center py-5 text-muted">
                <div class="mb-3"><i class="fas fa-tags fs-1 text-muted text-opacity-50"></i></div>
                <h6 class="fw-bold">No categories found.</h6>
            </div>
        {% endfor %}
        </div>
    </div>
</div>

<style>
.collapse-icon {
    transition: transform 0.3s ease;
    font-size: 0.7rem;
}
[aria-expanded="true"] .collapse-icon {
    transform: rotate(180deg);
}
.hover-primary:hover {
    background-color: var(--bs-primary) !important;
    color: white !important;
}
.cursor-pointer {
    cursor: pointer;
}
</style>

<!-- Modal: Category Editor -->
<div class="modal fade" id="categoryModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content border-0 rounded-4 shadow-lg">
      <div class="modal-header bg-light border-bottom-0 pb-0 pt-4 px-4">
        <h5 class="modal-title fw-bold text-dark d-flex align-items-center" id="categoryModalLabel">
            <div class="bg-primary text-white rounded-circle d-flex align-items-center justify-content-center me-2 shadow-sm" style="width: 32px; height: 32px; font-size: 0.9rem;"><i class="fas fa-tags"></i></div>
            <span>Category Details</span>
        </h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <form method="post" action="{{ url_for('admin.admin_save_category') }}">
        <div class="modal-body p-4">
           <input type="hidden" name="categoryId" id="field_categoryId_hidden">
           
           <div class="mb-3 d-none">
              <label class="form-label small fw-bold text-muted text-uppercase mb-1">Category Slug / ID <span class="text-danger">*</span></label>
              <input type="text" class="form-control form-control-lg bg-light border" name="categoryId_new" id="field_categoryId" placeholder="e.g. dairy-eggs" required>
           </div>
           
           <div class="row g-3 mb-3">
              <div class="col-md-6">
                 <label class="form-label small fw-bold text-muted text-uppercase mb-1">Name (EN)</label>
                 <input type="text" class="form-control form-control-lg bg-light border" name="name_en" id="field_cat_name_en">
              </div>
              <div class="col-md-6">
                 <label class="form-label small fw-bold text-muted text-uppercase mb-1">Name (DE)</label>
                 <input type="text" class="form-control form-control-lg bg-light border" name="name_de" id="field_cat_name_de">
              </div>
           </div>

           <div class="mb-3">
              <label class="form-label small fw-bold text-muted text-uppercase mb-1">Image URL</label>
              <input type="text" class="form-control form-control-lg bg-light border" name="image_url" id="field_cat_image_url" placeholder="https://...">
           </div>

           <div class="mb-2">
              <label class="form-label small fw-bold text-muted text-uppercase mb-1">Parent Category</label>
              <select class="form-select form-control-lg bg-light border" name="parentId" id="field_cat_parentId">
                 <option value="">(None - Top Level)</option>
                 {% for c in data.categories or [] %}
                 <option value="{{ c.categoryId }}">{{ c.name_en or c.categoryId }}</option>
                 {% endfor %}
              </select>
           </div>
        </div>
        <div class="modal-footer border-top-0 px-4 pb-4 pt-0 justify-content-between">
           <button type="button" class="btn btn-light rounded-pill px-4 fw-bold shadow-sm" data-bs-dismiss="modal">Cancel</button>
           <div class="d-flex gap-2">
              <button type="submit" formaction="" class="btn btn-outline-danger rounded-pill px-4 fw-bold shadow-sm d-none" id="btn_delete_cat" onclick="return confirm('Delete this category?')"><i class="fas fa-trash-alt me-1"></i> Delete</button>
              <button type="submit" class="btn btn-primary rounded-pill px-4 fw-bold shadow-sm"><i class="fas fa-save me-1"></i> Save Category</button>
           </div>
        </div>
      </form>
    </div>
  </div>
</div>

<script>
function prepareCategoryModal(mode, category) {
   const label = document.getElementById('categoryModalLabel').querySelector('span');
   const delBtn = document.getElementById('btn_delete_cat');
   
   if (mode === 'new' || !category) {
      label.innerText = "Create New Category";
      document.getElementById('field_categoryId_hidden').value = '';
      document.getElementById('field_categoryId').value = '';
      document.getElementById('field_categoryId').readOnly = false;
      document.getElementById('field_cat_name_en').value = '';
      document.getElementById('field_cat_name_de').value = '';
      document.getElementById('field_cat_image_url').value = '';
      document.getElementById('field_cat_parentId').value = '';
      delBtn.classList.add('d-none');
      delBtn.removeAttribute('formaction');
   } else {
      label.innerText = `Edit: ${category.name_en || category.categoryId}`;
      document.getElementById('field_categoryId_hidden').value = category.categoryId || '';
      document.getElementById('field_categoryId').value = category.categoryId || '';
      document.getElementById('field_categoryId').readOnly = true;
      document.getElementById('field_cat_name_en').value = category.name_en || '';
      document.getElementById('field_cat_name_de').value = category.name_de || '';
      document.getElementById('field_cat_image_url').value = category.image_url || '';
      document.getElementById('field_cat_parentId').value = category.parentId || '';
      delBtn.classList.remove('d-none');
      delBtn.setAttribute('formaction', `/admin/categories/delete/${category.categoryId}`);
   }
}

document.getElementById('field_cat_name_en').addEventListener('input', function(e) {
    if (!document.getElementById('field_categoryId').readOnly) {
        document.getElementById('field_categoryId').value = e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
    }
});
</script>
{% endblock %}"""

with open("templates/admin_categories.html", "w") as f:
    f.write(text)
