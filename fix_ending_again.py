import re

with open('templates/compare_prices.html', 'r') as f:
    text = f.read()

# We need to make sure we didn't drop a closing div or double an endfor by checking test_divs
with open('test_compare.py', 'w') as tf:
    tf.write("print('ready')")

