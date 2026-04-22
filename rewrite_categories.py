with open("templates/admin_categories.html", "r") as f:
    text = f.read()

# I will replace the entire card with a hierarchical view using macros.
new_categories_content = """<div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
    <div class="card-body p-0">
        {% set top_categories = data.categories|selectattr("parentId", "none")|list %}
        {% if not top_categories %}
            {% set top_categories = data.categories|selectattr("parentId", "equalto", "")|list %}
        {% endif %}
        {% if not top_categories %}
            {# If still nothing, some might just lack the key or have it null #}
            {% set top_categories = [] %}
            {% for c in data.categories %}
                {% if not c.parentId %}
                    {% set _ = top_categories.append(c) %}
                {% endif %}
            {% endfor %}
        {% endif %}
        
        <div class="list-group list-group-flush" id="categoryTree">
        {% macro render_category(cat, depth) %}
            {% set children = [] %}
            {% for c in data.categories %}
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
                        <button class="btn btn-sm btn-light border shadow-sm rounded-pill text-primary fw-bold px-3 hover-primary" onclick='prepareCategoryModal("edit", {"categoryId":"{{cat.categoryId|replace('\\'', '\\\\\\'')}}", "name_en":"{{cat.name_en|replace('\\'', '\\\\\\'')}}", "name_de":"{{cat.name_de|replace('\\'', '\\\\\\'')}}", "image_url": "{{cat.image_url|replace('\\'', '\\\\\\'')}}", "parentId":"{{cat.parentId}}"})' data-bs-toggle="modal" data-bs-target="#categoryModal">
                            <i class="fas fa-pen"></i> Edit
                        </button>
                    </div>
                </div>
            </div>
            {% if children %}
            <div class="collapse" id="collapse-{{ cat.categoryId|replace(' ', '-')|regex_replace('[^a-zA-Z0-9-]', '') }}">
                <div class="list-group list-group-flush rounded-0 bg-light bg-opacity-50">
                    {% for child in children %}
                        {{ render_category(child, depth + 1) }}
                    {% endfor %}
                </div>
            </div>
            {% endif %}
        {% endmacro %}
        
        {% for top in top_categories %}
            {{ render_category(top, 0) }}
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
"""

import re
old_card_pattern = r'<div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">.*?</div>\s*</div>'
text = re.sub(old_card_pattern, new_categories_content, text, flags=re.DOTALL)

with open("templates/admin_categories.html", "w") as f:
    f.write(text)
