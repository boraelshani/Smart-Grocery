with open("templates/admin_products.html", "r") as f:
    text = f.read()

# Make the fetch more robust to avoid missing the form/DOM elements after replacement
new_script = """
<script>
document.addEventListener('DOMContentLoaded', () => {
    let fetchTimeout;
    
    function attachSearchListeners() {
        const searchForm = document.getElementById('productSearchForm');
        if (!searchForm) return;
        
        const searchInput = searchForm.querySelector('input[name="q"]');
        const brandSelect = searchForm.querySelector('select[name="brand"]');
        
        if (searchInput && !searchInput.dataset.listenerAttached) {
            searchInput.addEventListener('input', () => {
                clearTimeout(fetchTimeout);
                fetchTimeout = setTimeout(fetchProducts, 400);
            });
            searchInput.dataset.listenerAttached = 'true';
        }
        
        if (brandSelect && !brandSelect.dataset.listenerAttached) {
            brandSelect.addEventListener('change', (e) => {
                e.preventDefault();
                fetchProducts();
            });
            brandSelect.dataset.listenerAttached = 'true';
        }
        
        if (!searchForm.dataset.listenerAttached) {
            searchForm.addEventListener('submit', (e) => {
                e.preventDefault();
                clearTimeout(fetchTimeout);
                fetchProducts();
            });
            searchForm.dataset.listenerAttached = 'true';
        }
    }

    async function fetchProducts() {
        const searchForm = document.getElementById('productSearchForm');
        const searchInput = searchForm.querySelector('input[name="q"]');
        const brandSelect = searchForm.querySelector('select[name="brand"]');
        const wrapper = document.getElementById('products-list-wrapper');
        
        if (!searchForm || !wrapper) return;

        const url = new URL(searchForm.action, window.location.origin);
        url.searchParams.set('q', searchInput.value || '');
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
                // Because we might replace the wrapper or its contents,
                // let's just replace its innerHTML to keep the wrapper alive.
                wrapper.innerHTML = newWrapper.innerHTML;
                
                // Re-bind any inline handlers or initialize stuff if needed
                
                // Update URL without reloading
                window.history.replaceState({}, '', url);
            }
        } catch(e) {
            console.error('Search fetch error:', e);
        }
        wrapper.style.opacity = '1';
    }

    attachSearchListeners();
});
</script>
"""

import re
# Regex to match the old script block we injected previously
text = re.sub(r'<script>\s*const searchForm\s*=\s*document\.getElementById\(\'productSearchForm\'\);.*?<\/script>', new_script, text, flags=re.DOTALL)

with open("templates/admin_products.html", "w") as f:
    f.write(text)
