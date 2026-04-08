import re

with open('templates/shopping_list.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Jinja fix
old_str = '''                                </div> <!-- Items List -->
                                <div class="py-2" id="items-container">
                                        {% for it in items %}
                                        {% set name = (it.name if it.name is defined else it) %}'''
                                        
new_str = '''                                </div> <!-- Items List -->
                                <div class="py-2" id="items-container">
                                        {% set stores = [] %}
                                        {% for it in items %}
                                            {% set st = (it.store if it.store is defined and it.store else 'Other') %}
                                            {% if st not in stores %}
                                                {% set _ = stores.append(st) %}
                                            {% endif %}
                                        {% endfor %}
                                        {% for cst in stores %}
                                        <div class="store-group mt-3 mb-2 px-3 fw-bold text-premium-purple" style="font-size: 1.1rem; border-bottom: 2px solid #e0e7ff; display: inline-block;">
                                            <i class="bi bi-shop me-2"></i>{{ cst }}
                                        </div>
                                        <div class="store-items-wrapper">
                                        {% for it in items %}
                                        {% set store_val = (it.store if it.store is defined and it.store else 'Other') %}
                                        {% if store_val == cst %}
                                        {% set name = (it.name if it.name is defined else it) %}'''

text = text.replace(old_str, new_str)

# also need to close the loops earlier before "{% endfor %} </div> {% else %}"
old_end = '''                                       </div>
                                        {% endfor %}
                                </div>
                                {% else %}'''
                                
new_end = '''                                       </div>
                                        {% endif %}
                                        {% endfor %}
                                        </div>
                                        {% endfor %}
                                </div>
                                {% else %}'''

text = text.replace(old_end, new_end)

# JS Fix in displayListItems
old_js = '''                    // Build HTML for items
                        let itemsHTML = \
                                <div class="p-3 border-bottom bg-light bg-opacity-50">'''

new_js = '''                    // Build HTML for items
                        let itemsHTML = \
                                <div class="p-3 border-bottom bg-light bg-opacity-50">'''

text = text.replace(old_js, new_js)

with open('templates/shopping_list.html', 'w', encoding='utf-8') as f:
    f.write(text)
