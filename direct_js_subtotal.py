import codecs
import re

t = codecs.open('templates/shopping_list.html', 'r', 'utf-8').read()

pattern = re.compile(r"uniqueStores\.forEach\(store => \{\s*itemsHTML \+= `<div class=\"store-group.*?; display: inline-block;\">`;\s*itemsHTML \+= `<i class=\"bi bi-shop(?:\\n| )me-2\"></i>\$\{store\}</div>`;\s*itemsHTML \+= `<div(?:\\n| )class=\"store-items-wrapper\">`;", re.DOTALL)

new_js = r'''uniqueStores.forEach(store => {
                                let subtotal = 0;
                                groupedByStore[store].forEach((it) => {
                                        const raw_price = (it.price_val !== undefined ? it.price_val : it.price || 0);
                                        const unit = parseFloat(raw_price) || 0;
                                        const qty = (it.qty || 1);
                                        // Just basic quantity multiplication here - actual calculation handled by calculateItemPrice on load
                                        subtotal += (unit * qty);
                                });

                                itemsHTML += `<div class="store-group mt-3 mb-2 px-3 fw-bold text-premium-purple" style="font-size: 1.1rem; border-bottom: 2px solid #e0e7ff; display: inline-block;">`;
                                itemsHTML += `<i class="bi bi-shop me-2"></i>${store} &nbsp;&mdash;&nbsp; €${subtotal.toFixed(2)}</div>`;
                                itemsHTML += `<div class="store-items-wrapper">`;'''

new_t, count = pattern.subn(lambda m: new_js, t)
if count == 0:
    print("NOT FOUND MATCH JS LOOP!")
    exit(1)

codecs.open('templates/shopping_list.html', 'w', 'utf-8').write(new_t)
print("SUCCESS!")
