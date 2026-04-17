import re
content = open('templates/compare_prices.html').read()
new_content = re.sub(r'(<span class="price-badge">)', r'{% if p.get(\'deal_eval\') and p.get(\'deal_eval\').get(\'is_great_deal\') %}\n                  <span class="badge bg-danger position-absolute top-0 start-0 m-2 rounded-pill px-3 shadow-sm" style="z-index:9; font-size:0.85rem; border:1px white solid;">\n                    <i class="bi bi-fire me-1"></i> -{{ p.get(\'deal_eval\').get(\'discount_pct\')|round|int }}% Avg\n                  </span>\n                  {% endif %}\n                  \1', content, count=1)
open('templates/compare_prices.html','w').write(new_content)
