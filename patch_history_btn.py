import re
content = open('templates/compare_prices.html').read()
new_content = re.sub(r'(<button type="button" class="inline-action-btns+btn-report-price")', r'<button type="button" class="inline-action-btn btn-price-history" title="Price history" data-product-id="{{ p.get(\'id\') }}" data-product-name="{{ p.get(\'name\') or p.get(\'title\','')|e }}">\n                      <i class="bi bi-graph-up"></i>\n                    </button>\n                    \1', content)
open('templates/compare_prices.html','w').write(new_content)
