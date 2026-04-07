import re

with open('utils/recipe_ai.py', 'r', encoding='utf-8') as f:
    text = f.read()

def inject_stripping(match):
    # This match is `raw_text = ...`
    orig = match.group(0)
    return orig + "\n        raw_text = raw_text.strip().removeprefix('```json').removesuffix('```').strip()\n        raw_text = raw_text.removeprefix('```').strip()"

# Replace all JSON parsing spots
text_fixed = re.sub(r'        raw_text = data\["candidates"\]\[0\]\["content"\]\["parts"\]\[0\]\["text"\]', inject_stripping, text)

with open('utils/recipe_ai.py', 'w', encoding='utf-8') as f:
    f.write(text_fixed)
