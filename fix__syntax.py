with open('templates/shopping_list.html', 'r', encoding='utf-8') as f:
    text = f.read()

target = "                        if (targetId) {\n                                setTimeout(() => switchList(targetId), 50);\n                        }\n                }\n\t\t}\n\n\t\t// Run restore on page load"
replacement = "                        if (targetId) {\n                                setTimeout(() => switchList(targetId), 50);\n                        }\n                }\n\n\t\t// Run restore on page load"

text = text.replace(target, replacement)
with open('templates/shopping_list.html', 'w', encoding='utf-8') as f:
    f.write(text)
print("Replaced!")
