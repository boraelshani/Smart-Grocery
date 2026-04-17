import re
with open('templates/compare_prices.html', 'r', encoding='utf-8') as f:
    text = f.read()
    match = re.search(r'<select[^>]*name=[\'\"]?sort[\'\"]?[\s\S]*?</select>', text)
    if match: print(match.group(0))
