import re
with open("templates/compare_prices.html", "r") as f:
    text = f.read()

match = re.search(r'\{% for p in products %\}(.*?)\{% endfor %\}', text, re.DOTALL)
if match:
    print(match.group(1))
