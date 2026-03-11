with open("templates/shopping_list.html", "r") as f:
    text = f.read()

text = text.replace("function switchList(listId, listName) {", "let isSwitchingList = false;\n\t\tfunction switchList(listId, listName) {\n\t\t\tif (isSwitchingList) return;\n\t\t\tisSwitchingList = true;")

with open("templates/shopping_list.html", "w") as f:
    f.write(text)
print("Done")
