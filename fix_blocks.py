import re

with open('templates/compare_prices.html', 'r') as f:
    text = f.read()

# We might have destroyed the final {% endblock %} when playing with the divs.
# Let's check if the main block is closed properly.

text_lines = text.split('\n')
for line in text_lines[-100:]:
    if '{% endblock %}' in line:
        print(line.strip())
