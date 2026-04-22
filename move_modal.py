import re

with open('templates/compare_prices.html', 'r') as f:
    html = f.read()

pattern = re.compile(r'\s*<div class="modal fade" id="priceReportModal".*?<!-- JavaScript Dependencies -->', re.DOTALL)
html, count = pattern.subn('\n\n      <!-- JavaScript Dependencies -->', html)
print("Removed modal from compare:", count)
with open('templates/compare_prices.html', 'w') as f:
    f.write(html)
