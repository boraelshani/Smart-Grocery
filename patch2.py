import re
with open("templates/shopping_list.html", "r") as f:
    text = f.read()

# Replace totalCountEl with itemsCountEl
text = text.replace(
    "const totalCountEl = document.getElementById('total-count');", 
    "const itemsCountEl = document.getElementById('items-count');"
)
text = text.replace(
    "if (totalCountEl) totalCountEl.textContent = totalCount;", 
    "if (itemsCountEl) itemsCountEl.textContent = totalCount;"
)

with open("templates/shopping_list.html", "w") as f:
    f.write(text)
print("Done")
