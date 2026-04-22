with open("templates/admin_products.html", "r") as f:
    text = f.read()

# I want to attach the input listener globally to the body, since the target form itself might be replaced:
new_script = """
<script>
document.addEventListener('DOMContentLoaded', () => {
    let fetchTimeout;

    document.body.addEventListener('input', (e) => {
        if (e.target && e.target.name === 'q' && e.target.closest('form#productSearchForm')) {
            clearTimeout(fetchTimeout);
            fetchTimeout = setTimeout(fetchProducts, 400);
        }
    });

    document.body.addEventListener('change', (e) => {
        if (e.target && e.target.name === 'brand' && e.target.closest('form#productSearchForm')) {
            e.preventDefault();
            fetchProducts();
        }
    });

    document.body.addEventListener('submit', (e) => {
        if (e.target && e.target.id === 'productSearchForm') {
            e.preventDefault();
            clearTimeout(fetchTimeout);
            fetchProducts();
        }
    });

    async function fetchProducts() {
        const searchForm = document.getElementById('productSearchForm');
        if (!searchForm) return;

        const searchInput = searchForm.querySelector('input[name="q"]');
        const brandSelect = searchForm.querySelector('select[name="brand"]');
        const wrapper = document.getElementById('products-list-wrapper');
        
        if (!wrapper) return;

        const url = new URL(searchForm.action, window.location.origin);
        if (searchInput) url.searchParams.set('q', searchInput.value || '');
        if (brandSelect && brandSelect.value) {
            url.searchParams.set('brand', brandSelect.value);
        }
        
        wrapper.style.opacity = '0.5';
        try {
            const resp = await fetch(url);
            const html = await resp.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newWrapper = doc.getElementById('products-list-wrapper');

            // Wait, does the form get replaced too? Let's replace the whole parent container if necessary, 
            // but the form is OUTSIDE the wrapper right now in the HTML structure.
            if (newWrapper) {
                wrapper.innerHTML = newWrapper.innerHTML;
                window.history.replaceState({}, '', url);
            }
        } catch(e) {
            console.error('Search fetch error:', e);
        }
        wrapper.style.opacity = '1';
    }
});
</script>
"""

import re
text = re.sub(r'<script>\s*document\.addEventListener\(\'DOMContentLoaded\', \(\) => \{\s*let fetchTimeout;\s*function attachSearchListeners\(\).*?<\/script>', new_script, text, flags=re.DOTALL)

with open("templates/admin_products.html", "w") as f:
    f.write(text)
