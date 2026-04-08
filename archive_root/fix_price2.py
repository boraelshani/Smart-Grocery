import re

with open('templates/recipe_planner.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Just replace that specific JS pattern
text = text.replace('parseFloat(prod.price_val || 0).toFixed(2)', 'parseFloat(prod.price_val || prod.price || 0).toFixed(2)')

with open('templates/recipe_planner.html', 'w', encoding='utf-8') as f:
    f.write(text)
