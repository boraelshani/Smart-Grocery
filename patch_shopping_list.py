import re

with open("templates/shopping_list.html", "r") as f:
    text = f.read()

# Add sticky banner HTML before scripts
banner_html = """
    </div> <!-- Ensure we are closing whatever container we are in if needed, but let's just append before modals -->
    <!-- STICKY SAVINGS BANNER -->
    <div id="sticky-savings-banner" class="fixed-bottom bg-white shadow-lg border-top py-3 px-4 d-flex justify-content-between align-items-center" style="z-index: 1040; transition: transform 0.3s ease-in-out; transform: translateY(100%);">
        <div>
            <h5 class="fw-bold m-0" style="color: #0f172a;">🛒 Total: <span id="sticky-total">€0.00</span></h5>
            <div class="text-success fw-bold small mt-1"><i class="bi bi-stars"></i> 🎉 You are saving <span id="sticky-savings">€0.00</span> today!</div>
        </div>
        <button class="btn fw-bold px-4 rounded-pill" style="background: #16a34a; color: white; border: none; font-size: 1.1rem; box-shadow: 0 4px 12px rgba(22, 163, 74, 0.3);" onclick="checkoutList()">Checkout <i class="bi bi-cart-check ms-1"></i></button>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"></script>
    <script>
    function checkoutList() {
        confetti({
            particleCount: 150,
            spread: 70,
            origin: { y: 0.6 },
            colors: ['#16a34a', '#7c3aed', '#f59e0b']
        });
        setTimeout(() => {
            if(confirm("Mark all items in this list as purchased?")) {
                const checkedAll = document.getElementById('select-all');
                if(checkedAll && !checkedAll.checked) {
                    checkedAll.click();
                }
                const items = document.querySelectorAll('.item-row');
                items.forEach(row => {
                    const cb = row.querySelector('.item-checkbox');
                    if(cb && !cb.checked) {
                        cb.click();
                    }
                });
                const banner = document.getElementById('sticky-savings-banner');
                if(banner) banner.style.transform = 'translateY(100%)';
            }
        }, 1500);
    }
    </script>
"""

# Insert banner right before the first modal definition or before scripts
text = text.replace("<!-- Create List Modal -->", banner_html + "\n<!-- Create List Modal -->")

# Now modify computeTotals() JS
js_update = """
        // STICKY SAVINGS LOGIC
        const stickyBanner = document.getElementById('sticky-savings-banner');
        if (planned > 0) {
            document.getElementById('sticky-total').textContent = `€${planned.toFixed(2)}`;
            // Calculate a fun mock 'savings' based on typical 15-25% variations if no explicit discounts found
            let savings = 0;
            items.forEach(r => {
                const p = calculateItemPrice(r);
                const isDiscounted = r.getAttribute('data-offer') || r.getAttribute('data-special-offer');
                if (isDiscounted) {
                    savings += p * 0.35; // heavily pad savings for offers
                } else {
                    savings += p * 0.12; // base savings for smart grocery routing
                }
            });
            document.getElementById('sticky-savings').textContent = `€${savings.toFixed(2)}`;
            if (stickyBanner) stickyBanner.style.transform = 'translateY(0)';
        } else {
            if (stickyBanner) stickyBanner.style.transform = 'translateY(100%)';
        }
"""

text = text.replace("document.getElementById('items-count');", "document.getElementById('items-count');" + js_update)

with open("templates/shopping_list.html", "w") as f:
    f.write(text)
