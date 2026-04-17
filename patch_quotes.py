content = open('templates/compare_prices.html', encoding='utf-8').read()
content = content.replace(r"\'", "'")
open('templates/compare_prices.html','w', encoding='utf-8').write(content)
