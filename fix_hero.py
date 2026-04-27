import re

with open('templates/home.html', 'r', encoding='utf-8') as f:
    content = f.read()

# we'll use regex to replace what's between <!-- Unified Premium Hero Section --> to </header>
hero_pattern = re.compile(r'<!-- Unified Premium Hero Section -->.*?</header>', re.DOTALL)

with open('templates/home.html', 'w', encoding='utf-8') as f:
    f.write(hero_pattern.sub('HERO_PLACEHOLDER', content))
