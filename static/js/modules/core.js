async function apiPostJson(url, body) { // Network utility
  const res = await fetch(url, {
    method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
  });
  return res.json().catch(() => ({}));
}

/**
 * REFRESH UI HELPER
 * Determines if the current page needs a hard reload to reflect updated database state.
 */
function refreshShoppingListUI() { // Force update
  const path = window.location.pathname || ''; // Read current URL
  // We only force a reload on the shopping list page so users see their latest additions immediately.
  if (path.includes('shopping_list') || path.endsWith('/shopping-list')) {
    window.location.reload(); // Perform browser refresh
  }
}

/**
 * CUSTOM NOTIFICATION SYSTEM (TOASTS)
 * Creates a floating, non-blocking alert in the top-right of the screen.
 * Uses a unique purple-forward design language consistent with the Smart-Grocery brand.
 * 
 * @param {string} message - Text to display
 * @param {string} type - 'success', 'danger', 'warning', 'info'
 */
function showNotification(message, type = 'info') { // UI Alert
  if (!message) return; // Silent discard for empty msgs

  const TOAST_DURATION_MS = 3600; // Visible for 3.6 seconds
  const normalizedType = type === 'error' ? 'danger' : type;
  const variants = {
    success: { title: 'Success', icon: 'bi-check2-circle' },
    danger: { title: 'Error', icon: 'bi-exclamation-octagon-fill' },
    warning: { title: 'Warning', icon: 'bi-exclamation-triangle-fill' },
    info: { title: 'Info', icon: 'bi-info-circle-fill' }
  };
  const variant = variants[normalizedType] || { title: 'Notice', icon: 'bi-bell-fill' };

  // 1. CONTAINER MANAGEMENT
  // Locate or create the fixed-position vertical stack for toasts.
  let container = document.getElementById('sg-toast-container');
  if (!container) { // First notification of session?
    container = document.createElement('div');
    container.id = 'sg-toast-container'; // ID for reuse
    container.className = 'sg-toast-container';
    document.body.appendChild(container); // Mount to viewport
  }

  // 3. TOAST ELEMENT CONSTRUCTION
  const toast = document.createElement('div'); // The box
  toast.className = `sg-toast sg-toast--${normalizedType}`;
  toast.style.setProperty('--toast-duration', `${TOAST_DURATION_MS}ms`);

  // 4. TEXT CONTENT
  const iconWrap = document.createElement('div');
  iconWrap.className = 'sg-toast__icon';
  iconWrap.innerHTML = `<i class="bi ${variant.icon}"></i>`;

  const content = document.createElement('div');
  content.className = 'sg-toast__content';

  const label = document.createElement('div');
  label.className = 'sg-toast__label';
  label.textContent = variant.title;

  const title = document.createElement('div');
  title.className = 'sg-toast__title';
  title.textContent = message;

  content.appendChild(label);
  content.appendChild(title);

  // 5. DISMISS BUTTON (X)
  const closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.className = 'sg-toast__close';
  closeBtn.innerHTML = '<i class="bi bi-x-lg"></i>';
  closeBtn.setAttribute('aria-label', 'Close notification');
  closeBtn.addEventListener('click', () => removeToast()); // Immediate dismissal

  const progress = document.createElement('span');
  progress.className = 'sg-toast__progress';

  // 6. ASSEMBLY & MOUNTING
  toast.appendChild(iconWrap);
  toast.appendChild(content);
  toast.appendChild(closeBtn);
  toast.appendChild(progress);
  container.appendChild(toast);

  // 7. ENTRANCE ANIMATION (Using requestAnimationFrame for buttery smooth motion)
  requestAnimationFrame(() => {
    toast.classList.add('is-visible');
  });

  // 8. AUTO-REMOVAL LOGIC
  const removeToast = () => { // Self-destruct function
    toast.classList.add('is-leaving');
    setTimeout(() => toast.remove(), 180); // Delete from DOM after transition
  };

  // Set timer for automatic cleanup
  setTimeout(removeToast, TOAST_DURATION_MS);
}

/**
 * CURRENCY UTILITY
 * Strips non-numeric characters from price strings to enable math operations.
 * 
 * @param {string|number} price - "€10.50" -> 10.50
 */
function formatPrice(price) { // Cleanup price
  if (typeof price === 'string') {
    price = price.replace(/[^0-9.]/g, ''); // Strip Euro/Dollar/Pound
  }
  return Number(price) || 0; // Cast to numeric
}

// Global state: Stores the "Item Data" temporarily while user chooses a destination list
let pendingItemToAdd = null;

/**
 * GLOBAL LIST SELECTOR (The "Heart" of the Shopping List system)
 * Displays a modal asking: "Which list do you want to add this to?"
 * Handles complex parsing for multibuy deals and quantity tiers.
 * 
 * @param {HTMLElement|Object} item - Triggering element or pre-built object
 */
