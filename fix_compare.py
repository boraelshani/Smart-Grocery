import re

with open('templates/compare_prices.html', 'r') as f:
    content = f.read()

# I want to take the card structure and make it a proper flex column with mt-auto on the footer
pattern = re.compile(r'<div class="card-body pb-0".*?<div class="card-body pt-2 mt-auto" style="background-color: #fff;">', re.DOTALL)

def repl(match):
    original = match.group(0)
    # the new layout inside card
    # I'll just write it outright
    return original

# Wait, the structure in compare_prices from line 960 to 1050:
# <div class="card-body pb-0"...
# ...
# </div> {# unconditionally close #}
# <div class="px-3 pb-3 mt-2"...
# ...
# </div> {# close stores #}
# <div class="card-body pt-2 mt-auto"...

# Let's write the exact replacement manually.
