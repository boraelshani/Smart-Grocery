import re
with open('templates/compare_prices.html', 'r', encoding='utf-8') as f:
    text = f.read()
text = re.sub(r'\{%\s*set\s+valid_stores.*?\s*\{%\s*set\s+sorted_stores\s*=\s*number_stores\|sort\(attribute=''price''\)\|list\s*%\}', '{% set sorted_stores = p.get(''stores'', []) | rejectattr(''price'', ''none'') | sort(attribute=''price'') | list %}', text, flags=re.DOTALL)
with open('templates/compare_prices.html', 'w', encoding='utf-8') as f:
    f.write(text)
print('Fixed')
