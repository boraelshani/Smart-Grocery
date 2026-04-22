import re

with open('templates/home.html', 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if "product-card-horizontal" in line or "product-card " in line:
            print(f"Line {i}: {line.strip()}")
