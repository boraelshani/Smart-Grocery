with open("output_test.html", "r") as f:
    text = f.read()
print("Opening divs:", text.count("<div"))
print("Closing divs:", text.count("</div"))
