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

  // 1. CONTAINER MANAGEMENT
  // Locate or create the fixed-position vertical stack for toasts.
  let container = document.getElementById('sg-toast-container');
  if (!container) { // First notification of session?
    container = document.createElement('div');
    container.id = 'sg-toast-container'; // ID for reuse
    // STYLING: Fixed position, high z-index, flex-column stack
    container.style.position = 'fixed';
    container.style.top = '18px';
    container.style.right = '18px';
    container.style.zIndex = '9999'; // Stay above modals
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.maxWidth = '320px';
    document.body.appendChild(container); // Mount to viewport
  }

  // 2. BRANDED PALETTES
  // Maps status types to specific background/border/text hex codes.
  const palettes = {
    success: { bg: '#f2ebff', border: '#7a5af8', text: '#2f1b6d' }, // Soft Lavender
    danger: { bg: '#fbebf1', border: '#d63384', text: '#6b103f' },  // Deep Rose
    warning: { bg: '#f6edff', border: '#b388ff', text: '#3f2a73' }, // Bright Violet
    info: { bg: '#ede7ff', border: '#6f42c1', text: '#2f1b6d' },    // Standard Purple
    default: { bg: '#f1ecff', border: '#8a63f5', text: '#2f1b6d' }
  };
  const palette = palettes[type] || palettes.default;

  // 3. TOAST ELEMENT CONSTRUCTION
  const toast = document.createElement('div'); // The box
  toast.style.background = palette.bg;
  toast.style.border = `1px solid ${palette.border}`;
  toast.style.color = palette.text;
  toast.style.borderRadius = '12px'; // Round corners
  toast.style.boxShadow = '0 8px 30px rgba(0,0,0,0.12)'; // Soft drop shadow
  toast.style.padding = '12px 14px';
  toast.style.fontWeight = '600';
  toast.style.display = 'flex';
  toast.style.alignItems = 'center';
  toast.style.justifyContent = 'space-between';
  toast.style.opacity = '0'; // Start invisible for animation
  toast.style.transform = 'translateY(-6px)'; // Start slightly above
  toast.style.transition = 'all 0.2s ease'; // CSS transition for smooth entry

  // 4. TEXT CONTENT
  const textSpan = document.createElement('span');
  textSpan.textContent = message;
  textSpan.style.flex = '1';

  // 5. DISMISS BUTTON (X)
  const closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.innerHTML = '&times;'; // HTML Multiplication symbol
  closeBtn.style.background = 'transparent';
  closeBtn.style.border = 'none';
  closeBtn.style.color = palette.text;
  closeBtn.style.fontSize = '18px';
  closeBtn.style.lineHeight = '1';
  closeBtn.style.marginLeft = '10px';
  closeBtn.style.cursor = 'pointer';
  closeBtn.setAttribute('aria-label', 'Close notification');
  closeBtn.addEventListener('click', () => removeToast()); // Immediate dismissal

  // 6. ASSEMBLY & MOUNTING
  toast.appendChild(textSpan);
  toast.appendChild(closeBtn);
  container.appendChild(toast);

  // 7. ENTRANCE ANIMATION (Using requestAnimationFrame for buttery smooth motion)
  requestAnimationFrame(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)'; // Drop into place
  });

  // 8. AUTO-REMOVAL LOGIC
  const removeToast = () => { // Self-destruct function
    toast.style.opacity = '0'; // Fade out
    toast.style.transform = 'translateY(-6px)'; // Slide up
    setTimeout(() => toast.remove(), 160); // Delete from DOM after transition
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
