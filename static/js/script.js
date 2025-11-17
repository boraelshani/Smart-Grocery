// Smart Grocery JavaScript Functions

// Initialize tooltips and popovers on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeBootstrapComponents();
    setupEventListeners();
});

// Initialize Bootstrap components
function initializeBootstrapComponents() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
}

// Setup event listeners
function setupEventListeners() {
    // Add to cart functionality
    const addToCartButtons = document.querySelectorAll('.add-to-cart-btn');
    addToCartButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const productName = this.getAttribute('data-product-name');
            const productPrice = this.getAttribute('data-product-price');
            addToCart(productName, productPrice);
        });
    });

    // Remove from cart functionality
    const removeFromCartButtons = document.querySelectorAll('.remove-from-cart-btn');
    removeFromCartButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const itemId = this.getAttribute('data-item-id');
            removeFromCart(itemId);
        });
    });

    // Shopping list item checkbox
    const shoppingItems = document.querySelectorAll('.shopping-item-checkbox');
    shoppingItems.forEach(item => {
        item.addEventListener('change', function() {
            toggleItemComplete(this);
        });
    });

    // Form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });
}

// Add item to shopping cart
function addToCart(productName, productPrice) {
    console.log(`Added ${productName} (${productPrice}) to cart`);
    showNotification(`${productName} added to cart!`, 'success');
}

// Remove item from shopping cart
function removeFromCart(itemId) {
    console.log(`Removed item ${itemId} from cart`);
    showNotification('Item removed from cart', 'info');
}

// Toggle item complete status
function toggleItemComplete(checkbox) {
    const itemRow = checkbox.closest('.shopping-item');
    if (checkbox.checked) {
        itemRow.classList.add('completed');
    } else {
        itemRow.classList.remove('completed');
    }
}

// Show notification toast
function showNotification(message, type = 'info') {
    const alertClass = `alert-${type}`;
    const alertHTML = `
        <div class="alert ${alertClass} alert-dismissible fade show" role="alert" style="position: fixed; top: 20px; right: 20px; z-index: 9999; min-width: 300px;">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', alertHTML);
    
    // Auto-dismiss after 4 seconds
    setTimeout(() => {
        const alert = document.querySelector('.alert:not(.show)');
        if (alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }
    }, 4000);
}

// Format price to currency
function formatPrice(price) {
    if (typeof price === 'string') {
        return parseFloat(price.replace('$', ''));
    }
    return parseFloat(price);
}

// Calculate total from shopping list
function calculateTotal() {
    const items = document.querySelectorAll('.shopping-item-price');
    let total = 0;
    items.forEach(item => {
        const price = formatPrice(item.textContent);
        total += price;
    });
    return total.toFixed(2);
}

// Search products
function searchProducts(query) {
    const products = document.querySelectorAll('.product-card');
    products.forEach(product => {
        const productName = product.getAttribute('data-product-name').toLowerCase();
        if (productName.includes(query.toLowerCase())) {
            product.style.display = 'block';
        } else {
            product.style.display = 'none';
        }
    });
}

// Filter stores by distance
function filterStoresByDistance(maxDistance) {
    const stores = document.querySelectorAll('.store-card');
    stores.forEach(store => {
        const distance = parseFloat(store.getAttribute('data-distance'));
        if (distance <= maxDistance) {
            store.style.display = 'block';
        } else {
            store.style.display = 'none';
        }
    });
}

// Sort products by price
function sortProductsByPrice(order = 'asc') {
    const productContainer = document.querySelector('.products-container');
    if (!productContainer) return;

    const products = Array.from(productContainer.querySelectorAll('.product-card'));
    
    products.sort((a, b) => {
        const priceA = formatPrice(a.getAttribute('data-price'));
        const priceB = formatPrice(b.getAttribute('data-price'));
        
        return order === 'asc' ? priceA - priceB : priceB - priceA;
    });

    productContainer.innerHTML = '';
    products.forEach(product => {
        productContainer.appendChild(product);
    });
}

// Export functions for use in templates
window.smartGrocery = {
    addToCart,
    removeFromCart,
    toggleItemComplete,
    showNotification,
    formatPrice,
    calculateTotal,
    searchProducts,
    filterStoresByDistance,
    sortProductsByPrice
};
