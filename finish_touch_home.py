import re

with open('templates/home.html', 'r') as f:
    html = f.read()

# Make sure the container holds the buttons at the bottom.
# For home.html horizontal cards:
html = html.replace('<div class="product-card-body">', '<div class="product-card-body d-flex flex-column">')
html = html.replace('<button class="add-to-list-btn w-100"', '<div class="mt-auto w-100"><button class="add-to-list-btn w-100"')
html = html.replace('add to list</button>', 'add to list</button></div>')

with open('templates/home.html', 'w') as f:
    f.write(html)
