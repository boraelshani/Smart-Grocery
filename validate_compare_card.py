with open("templates/compare_prices.html", "r") as f:
    text = f.read()

# Extract from just inside the for loop to the endfor
import re
match = re.search(r'\{% for p in products %\}(.*?)\{% endfor %\}', text, re.DOTALL)
if match:
    card_html = match.group(1)
    opens = card_html.count('<div ')
    closes = card_html.count('</div>')
    print(f"Product Loop -> Opens: {opens}, Closes: {closes}")
else:
    print("Loop not found")
