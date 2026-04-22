with open("templates/admin_categories.html", "r") as f:
    text = f.read()

text = text.replace('{% macro render_category(cat, depth) %}', '{% macro render_category(cat, depth, all_cats) %}')
text = text.replace('{% for c in data.categories %}', '{% for c in all_cats %}')
text = text.replace('{{ render_category(child, depth + 1) }}', '{{ render_category(child, depth + 1, all_cats) }}')
text = text.replace('{{ render_category(top, 0) }}', '{{ render_category(top, 0, data.categories) }}')

with open("templates/admin_categories.html", "w") as f:
    f.write(text)
