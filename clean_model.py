import re

with open('models/price_predictor_model.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(
    r'\s+@staticmethod\n\s+def generate_price_history.*?return history\n',
    '\n',
    text,
    flags=re.DOTALL
)

with open('models/price_predictor_model.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Model cleaned")