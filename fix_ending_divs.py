import re

with open('templates/compare_prices.html', 'r') as f:
    text = f.read()

# Delete ALL loose </div> tags that are outside of Jinja blocks at the bottom of the file
# Or specifically delete the weird ones after {% endblock %}
text = re.sub(r'</div>\s*(</div>\s*)*(</div>\s*)?\{% block scripts %\}', '{% block scripts %}', text)

# Let's cleanly fix the container boundary before {% endblock %}
# The page usually has <div class="container..."> at the top, which needs to be closed.
# If I deleted stuff around Modal, I might have deleted real closing tags.
# Instead of guessing, let's just restore from git checkout and then apply ONLY the exact modal removal without regex DOTALL!

