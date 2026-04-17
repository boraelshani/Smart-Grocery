with open('templates/compare_prices.html', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
'''    .inline-actions {
      display: flex;
      align-items: center;
      gap: 0.4rem;
      flex-shrink: 0;
    }''',
'''    .inline-actions {
      display: flex;
      align-items: center;
      gap: 0.4rem;
      flex-shrink: 0;
      position: relative;
      z-index: 50;
    }'''
)

text = text.replace(
'''    .inline-action-btn {
      border: 1px solid #dbeafe;''',
'''    .inline-action-btn {
      position: relative;
      z-index: 50;
      cursor: pointer;
      pointer-events: auto;
      border: 1px solid #dbeafe;'''
)

with open('templates/compare_prices.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("CSS classes patched")