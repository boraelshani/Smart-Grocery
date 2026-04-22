import re

with open("templates/admin_products.html", "r") as f:
    text = f.read()

# 1. remove the old oninput I just added
text = text.replace('oninput="clearTimeout(window.searchTimeout); window.searchTimeout = setTimeout(() => this.form.submit(), 400);"', '')

# 2. Add ID to form and table wrapper
text = text.replace('<form method="get" action="{{ url_for(\'admin.admin_products_page\') }}" class="d-flex bg-white rounded-pill shadow-sm overflow-hidden p-1 border">', '<form id="productSearchForm" method="get" action="{{ url_for(\'admin.admin_products_page\') }}" class="d-flex bg-white rounded-pill shadow-sm overflow-hidden p-1 border">')

text = text.replace('<div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">', '<div id="products-list-wrapper" class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">')

# 3. Add script at the end
script = """
<script>
    const searchForm = document.getElementById('productSearchForm');
    const searchInput = searchForm.querySelector('input[name="q"]');
    const brandSelect = searchForm.querySelector('select[name="brand"]');
    const wrapper = document.getElementById('products-list-wrapper');

    let fetchTimeout;
    
    async function fetchProducts() {
        const url = new URL(searchForm.action, window.location.origin);
        url.searchParams.set('q', searchInput.value);
        if (brandSelect.value) {
            url.searchParams.set('brand', brandSelect.value);
        }
        
        wrapper.style.opacity = '0.5';
        try {
            const resp = await fetch(url);
            const html = await resp.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newWrapper = doc.getElementById('products-list-wrapper');
            if (newWrapper) {
                wrapper.innerHTML = newWrapper.innerHTML;
            }
            // Update URL without reloading
            window.history.replaceState({}, '', url);
        } catch(e) {
            console.error(e);
        }
        wrapper.style.opacity = '1';
    }

    searchInput.addEventListener('input', () => {
        clearTimeout(fetchTimeout);
        fetchTimeout = setTimeout(fetchProducts, 300);
    });
    
    brandSelect.addEventListener('change', (e) => {
        e.preventDefault();
        fetchProducts();
    });
    
    searchForm.addEventListener('submit', (e) => {
        e.preventDefault();
        clearTimeout(fetchTimeout);
        fetchProducts();
    });
</script>
{% endblock %}
"""

text = text.replace("{% endblock %}", script)

with open("templates/admin_products.html", "w") as f:
    f.write(text)

