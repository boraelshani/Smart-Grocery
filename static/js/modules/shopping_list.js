window.showListSelector = async function (item) { // List picker
  // 1. TYPE DETECTION: If 'item' is a HTML button, hydrate from its data-attributes
  if (item instanceof HTMLElement) {
    const btn = item;
    // Extract metadata strings
    const name = btn.getAttribute('data-name') || btn.getAttribute('data-title') || 'Item';
    const price = btn.getAttribute('data-price') || '';
    const originalPrice = btn.getAttribute('data-original-price') || '';
    const store = btn.getAttribute('data-store') || '';
    const image = btn.getAttribute('data-image') || '';
    const id = btn.getAttribute('data-id') || null;

    // Extract Special Offer Data (JSON encoded in HTML)
    const dealId = btn.getAttribute('data-deal-id') || null;
    const offerJson = btn.getAttribute('data-offer-json') || ''; // Multibuy logic
    const tierJson = btn.getAttribute('data-tier-json') || '';   // Quantity discount logic
    const offerType = btn.getAttribute('data-offer-type') || ''; 
    const offerX = btn.getAttribute('data-offer-x') || '';
    const offerY = btn.getAttribute('data-offer-y') || '';

    // Deserialize Offer Payloads
    let offerPayload = null;
    try { if (offerJson) offerPayload = JSON.parse(offerJson); } catch (err) { }
    
    let discountTiers = null;
    try { if (tierJson) discountTiers = JSON.parse(tierJson); } catch (err) { }

    // Fallback logic for legacy "Buy X Get Y" attributes
    if (!offerPayload && offerType === 'buyXgetY' && offerX && offerY) {
      const xNum = parseInt(offerX, 10) || 0;
      const yNum = parseInt(offerY, 10) || 0;
      if (xNum && yNum) offerPayload = { type: 'buyXgetY', x: xNum, y: yNum };
    }

    // BASE PRICE SELECTION LOGIC
    // For "Buy X Get Y" deals, we MUST store the ORIGINAL (full) unit price.
    // The shopping list needs the full price so it can correctly apply "Free item" math 
    // when the user reaches the required threshold (X+Y).
    let basePriceToStore = price;
    if (offerPayload && (offerPayload.type === 'buyXgetY' || offerType === 'buyXgetY') && originalPrice) {
      basePriceToStore = originalPrice; // Store the non-discounted rate
    }

    // Build Internal Item Object
    item = { name, price: basePriceToStore, store, image, id };
    if (dealId) item.deal_id = dealId; // link to database deal record
    if (offerPayload) item.offer = offerPayload;
    if (discountTiers) item.discount_tiers = discountTiers;
    
    // Numeric Verification
    const priceVal = formatPrice(basePriceToStore);
    if (!isNaN(priceVal) && priceVal > 0) item.price_val = priceVal;
  }

  // 2. STATE CAPTURE: Save item to global memory for the secondary 'confirmAdd' step
  pendingItemToAdd = item;

  try {
    // 3. ASYNC FETCH: Get the user's available lists (e.g., "Main List", "Weekly Shop")
    // 3. ASYNC FETCH: Get the user's available lists (e.g., "Main List", "Weekly Shop")
    const response = await fetch('/api/get-lists');
    const data = await response.json(); // Transform JSON body

    // 4. NULL STATE: Handle users with zero lists
    if (!data.success || !data.lists || data.lists.length === 0) {
      showNotification('No shopping lists available. Please create one first.', 'warning');
      return; // Stop flow
    }

    // 5. MODAL PREPARATION: Find the physical container on the page
    const modalBody = document.getElementById('globalListSelectorBody');
    if (!modalBody) {
      // Emergency Fallback: If the modal UI is missing, just try to hit the "Direct Add" endpoint
      return await apiPostJson('/api/list/add-item', { item });
    }

    modalBody.innerHTML = ''; // Start with a blank canvas

    // 6. PREVIEW HEADER: Show the user a visual confirmation of what they're adding
    const itemPreview = document.createElement('div');
    itemPreview.className = 'text-center mb-4';
    
    // Logic: If item has a valid image, show it. Otherwise, show a stylized icon.
    let imgHtml = '';
    if (item.image && item.image !== 'undefined' && item.image !== '' && !item.image.includes('placeholder')) {
      imgHtml = `<img src="${item.image}" class="shadow-sm" style="width: 80px; height: 80px; object-fit: contain; background: white; border-radius: 20px; padding: 6px; box-shadow: 0 8px 25px rgba(0,0,0,0.15); margin-bottom: 15px;">`;
    } else {
      imgHtml = `<div class="mx-auto shadow-sm" style="width: 70px; height: 70px; background: rgba(255,255,255,0.2); border-radius: 20px; display: flex; align-items: center; justify-content: center; margin-bottom: 15px; border: 1px solid rgba(255,255,255,0.3);"><i class="bi bi-cart-plus-fill fs-2 text-white"></i></div>`;
    }

    // Inject Name, Price, and Store metadata into the header
    itemPreview.innerHTML = `
      ${imgHtml}
      <h4 class="fw-800 text-white mb-2" style="font-weight: 800; letter-spacing: -0.5px;">${escapeHtml(item.name || 'New Item')}</h4>
      <div class="d-flex justify-content-center gap-2 align-items-center">
        ${item.price ? `<span class="badge bg-white text-primary fw-bold px-3 py-2 rounded-pill shadow-sm" style="font-size: 0.95rem;">€${item.price}</span>` : ''}
        ${item.store ? `<span class="badge bg-dark bg-opacity-25 text-white border border-white border-opacity-25 px-3 py-2 rounded-pill">${escapeHtml(item.store)}</span>` : ''}
      </div>
    `;
    modalBody.appendChild(itemPreview);

    // 7. LIST OPTIONS GRID: Create selectable buttons for each Shopping List
    const listContainer = document.createElement('div');
    listContainer.className = 'd-flex flex-column gap-2';
    modalBody.appendChild(listContainer);

    data.lists.forEach(list => {
      const itemCount = list.items ? list.items.length : 0;
      const card = document.createElement('div');
      card.className = 'list-selector-option btn-smooth'; // Custom CSS class for hover effects
      
      // DESIGN TOUCH: Generate a pseudo-random hue based on list name length.
      // This gives each list a slightly different colored icon without manual config.
      const hue = (list.name.length * 25) % 360; 

      card.innerHTML = `
        <div class="card-body p-3 d-flex align-items-center w-100">
          <div class="list-selector-icon me-3 shadow-sm flex-shrink-0" style="width: 50px; height: 50px; background: linear-gradient(135deg, hsl(${hue}, 70%, 60%), hsl(${hue}, 70%, 45%));">
            <i class="bi bi-bag-heart-fill fs-4 text-white"></i>
          </div>
          <div class="list-info flex-grow-1 text-start" style="min-width: 0;">
            <div class="list-title text-dark fw-bold mb-1 text-truncate" style="font-size: 1.05rem;">${escapeHtml(list.name)}</div>
            <div class="list-subtitle text-muted small d-flex align-items-center gap-2">
                <span class="badge bg-light text-secondary border rounded-pill px-2">${itemCount} items</span>
                <small class="text-truncate">Created: ${list.created_at ? list.created_at.substring(0,10) : 'Recent'}</small>
            </div>
          </div>
          <div class="list-action-icon rounded-circle bg-primary bg-opacity-10 text-primary d-flex align-items-center justify-content-center flex-shrink-0" style="width: 40px; height: 40px;">
            <i class="bi bi-plus-lg fw-bold"></i>
          </div>
        </div>
      `;

      // Trigger the final DB commit logic when a list is clicked
      card.addEventListener('click', () => addItemToSelectedList(list.id));
      listContainer.appendChild(card);
    });

    // 8. MODAL VISIBILITY: Use Bootstrap 5 JS API to reveal the UI
    const modalEl = document.getElementById('globalListSelectorModal');
    if (modalEl) {
      if (typeof bootstrap === 'undefined' || !bootstrap.Modal) {
        console.warn('Bootstrap Modal not available, falling back to direct add');
        return apiPostJson('/api/list/add-item', { item });
      }
      
      let modal = bootstrap.Modal.getInstance(modalEl);
      if (!modal) {
        modal = new bootstrap.Modal(modalEl); // Initialize if needed
      }
      modal.show(); // Display to user
    }
  } catch (err) {
    console.error('Error showing list selector:', err);
    // EMERGENCY FALLBACK: If everything fails, try to add to the first/active list blindly
    try {
      if (pendingItemToAdd) {
        const fallbackRes = await apiPostJson('/api/list/add-item', { item: pendingItemToAdd });
        if (fallbackRes?.success) {
           showNotification('Added to shopping list', 'success');
           refreshShoppingListUI();
        } else {
           showNotification('Error adding to shopping list', 'danger');
        }
      }
    } catch(e) {}
  }
};

/**
 * FINAL COMMIT HANDLER
 * Sends the selected list ID and the pending item to the server.
 * 
 * @param {string} listId - ID of the target shopping list in MongoDB
 */
async function addItemToSelectedList(listId) { // Final Add
  if (!pendingItemToAdd) { // Guard
    showNotification('No item to add', 'danger');
    return;
  }

  try {
    // API Call: POST to internal endpoint
    const response = await apiPostJson('/api/list/add-item', { item: pendingItemToAdd, list_id: listId });

    if (response && response.success) { // Server Success 200
      showNotification(`${pendingItemToAdd.name || 'Item'} added to shopping list`, 'success');

      // 1. Close Modal
      const modalEl = document.getElementById('globalListSelectorModal');
      if (modalEl) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }

      // 2. Trigger UI Refresh
      if (typeof refreshShoppingListUI === 'function') {
        refreshShoppingListUI();
      }

      // 3. Reset state
      pendingItemToAdd = null;
    } else { // Handle DB errors (e.g. duplicate item)
      showNotification(response?.error || 'Could not add item to list', 'danger');
    }
  } catch (err) { // Network layer errors
    console.error('Error adding item:', err);
    showNotification('Error adding item to list', 'danger');
  }
}

/**
 * SHOPPING LIST GATEKEEPER
 * The standard entry point for adding any item to a shopping list from the UI.
 * It first attempts to show a list selector modal so the user can choose which list to use.
 * 
 * @param {Object|HTMLElement} item - The item metadata or the triggering element
 * @returns {Promise<Object>} - Success/Failure status
 */
async function addItemToShoppingList(item) { // Primary entry
  if (!item) return { success: false, error: 'missing_item' };

  // Always show list selector to let user choose which list
  if (typeof window.showListSelector === 'function') {
    try {
      await window.showListSelector(item);
      return { success: true, deferred: true };
    } catch (err) {
      console.error('List selector error:', err);
      // fall through to direct add
    }
  }

  // Fallback: add to active list directly (legacy behavior or if modal fails)
  try {
    return await apiPostJson('/api/list/add-item', { item });
  } catch (err) {
    return { success: false, error: 'request_failed' };
  }
}

/**
 * FAVORITE TOGGLE SYSTEM
 * Handles the logic for the "Heart" buttons found on product cards.
 * Uses Optimistic UI: Transforms the heart instantaneously before the server responds.
 * 
 * @param {Event} event - Mouse click event
 * @param {string|HTMLElement} arg1 - Either the Product ID or the button element
 * @param {HTMLElement} [arg2] - The button element if ID was passed as arg1
 */
const asyncToggleFavorite = async function (event, arg1, arg2) { // Internal Heart handler
  if (event) { // Prevent navigation if button is inside a link
    event.stopPropagation();
    event.preventDefault();
  }

  let btn, productId;
  // Overload Support: Handles different ways the function is called in Jinja templates
  if (arg1 instanceof HTMLElement) {
    btn = arg1;
    productId = btn.getAttribute('data-product-id') || btn.getAttribute('data-id');
  } else {
    productId = arg1; // ID string
    btn = arg2;      // Element
  }

  if (!productId || !btn) { // Safe exit
    console.error('Missing product ID or button element', { productId, btn });
    showNotification('Error: Cannot toggle favorite', 'danger');
    return;
  }

  // 1. OPTIMISTIC UI: Give instant gratification to the user
  const heartIcon = btn.querySelector('i'); // Locate icon
  const wasActive = btn.classList.contains('active'); // current state
  
  if (wasActive) { // REMOVE favorite
    btn.classList.remove('active'); // remove purple fill
    if (heartIcon) {
      heartIcon.classList.remove('bi-heart-fill');
      heartIcon.classList.add('bi-heart'); // change to outline
    }
  } else { // ADD favorite
    btn.classList.add('active'); // add purple fill
    if (heartIcon) {
      heartIcon.classList.remove('bi-heart');
      heartIcon.classList.add('bi-heart-fill'); // change to solid
    }
    
    // MICRO-ANIMATION: A small pop effect when liking
    btn.style.transform = 'scale(1.2)';
    setTimeout(() => {
      btn.style.transform = 'scale(1)';
    }, 200);
  }

  try {
    // 2. SERVER SYNC: POST to favorite toggle endpoint
    const response = await fetch('/api/toggle-favorite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_id: productId })
    });

    const data = await response.json();

    if (!response.ok) { // Backend rejection (e.g., unauthorized)
      throw new Error(data.error || 'Failed to toggle favorite');
    }

    // 3. CONFIRMATION FEEDBACK
    if (data.action === 'added') {
      showNotification('Added to favorites', 'success');
    } else {
      showNotification('Removed from favorites', 'info');
    }
    
    // 4. CROSS-PAGE SYNC: Update all other heart buttons for THIS same product
    // (e.g. if the item appears in both "Deals" and "Search Results")
    document.querySelectorAll(`.btn-favorite[data-product-id="${productId}"], .btn-favorite[data-id="${productId}"]`).forEach(otherBtn => {
      if (otherBtn === btn) return; // skip the one we already clicked
      if (data.is_favorite) {
        otherBtn.classList.add('active');
        const icon = otherBtn.querySelector('i');
        if (icon) { icon.classList.remove('bi-heart'); icon.classList.add('bi-heart-fill'); }
      } else {
        otherBtn.classList.remove('active');
        const icon = otherBtn.querySelector('i');
        if (icon) { icon.classList.remove('bi-heart-fill'); icon.classList.add('bi-heart'); }
      }
    });

  } catch (err) { // Failure: Roll back the UI state
    console.error('Error toggling favorite:', err);
    showNotification('Error updating favorites. Are you logged in?', 'danger');
    
    // UI REVERSION: Put the heart back how it was
    if (wasActive) {
      btn.classList.add('active');
      if (heartIcon) { heartIcon.classList.remove('bi-heart'); heartIcon.classList.add('bi-heart-fill'); }
    } else {
      btn.classList.remove('active');
      if (heartIcon) { heartIcon.classList.remove('bi-heart-fill'); heartIcon.classList.add('bi-heart'); }
    }
  }
};

/**
 * XSS PROTECTION HELPER
 * Sanitizes strings for safe insertion into the DOM via innerHTML.
 * Essential when rendering user-generated or external API content.
 */
function escapeHtml(unsafe) { // Safe text formatter
  if (unsafe === null || unsafe === undefined) return ''; // blank fallback
  return String(unsafe).replace(/[&<>'"]/g, function (m) { 
    return ({ 
      '&': '&amp;',  // Ampersand
      '<': '&lt;',   // Less than
      '>': '&gt;',   // Greater than
      '"': '&quot;', // Double quote
      "'": '&#39;'   // Single quote
    }[m]); 
  });
}

// Global flag to prevent multiple registration of modal listeners
let productModalHandlerBound = false;

/**
 * SHOPPING LIST UI HANDLERS
 * Attaches listeners to the physical table rows on the /shopping-list page.
 */
function setupShoppingListHandlers() {
  // 1. DELETE BUTTONS
  document.querySelectorAll('.remove-item-btn').forEach(btn => btn.addEventListener('click', async (e) => {
    const name = btn.getAttribute('data-name') || btn.getAttribute('data-id'); 
    if (!name) return; // Guard

    // API Call
    const r = await apiPostJson('/shopping-list/remove', { item: name }); 
    if (r && r.success) { 
      showNotification('Item removed', 'info'); 
      refreshShoppingListUI(); // Trigger reload to cleanup table
    } else {
      showNotification('Could not remove item', 'danger');
    }
  }));

  // 2. CHECKBOX TOGGLES (Mark as Bought)
  document.querySelectorAll('.checkbox-item').forEach(cb => cb.addEventListener('change', () => {
    const row = cb.closest('.item-row'); // target row
    if (!row) return;

    if (cb.checked) {
      row.classList.add('purchased'); // Strike-through styling
    } else {
      row.classList.remove('purchased'); // Remove strike-through
    }
    // persistence logic
    if (typeof debounceSaveOrder === 'function') debounceSaveOrder(); 
  }));
}

/**
 * CLAIM BUTTONS (FEATURED DEALS)
 * Logic for converting a promotional Deal into a Shopping List item.
 */

function setupShoppingListInteractions() {
  const list = document.getElementById('shopping-list') || document.querySelector('.list-rows'); 
  if (!list) return;

  // 1. VISUAL REORDERING (Drag/Drop)
  let dragSrc = null;
  list.addEventListener('dragstart', (e) => { 
    const r = e.target.closest('.item-row'); 
    if (!r) return; 
    dragSrc = r; 
    e.dataTransfer.effectAllowed = 'move'; 
  });

  list.addEventListener('dragover', (e) => e.preventDefault());
  
  list.addEventListener('drop', (e) => { 
    e.preventDefault(); 
    const target = e.target.closest('.item-row'); 
    if (!target || !dragSrc || target === dragSrc) return; 
    list.insertBefore(dragSrc, target); 
    postCurrentListOrder(); // Sync to server
  });

  // 2. BULK OPERATIONS
  document.getElementById('clear-purchased')?.addEventListener('click', () => {
    const rows = Array.from(list.querySelectorAll('.item-row.purchased'));
    rows.forEach(r => { 
      const name = r.getAttribute('data-name'); 
      apiPostJson('/shopping-list/remove', { item: name }).then(res => { 
        if (res && res.success) refreshShoppingListUI(); 
      }); 
    });
  });

  document.getElementById('clear-all')?.addEventListener('click', () => {
    if (!confirm('Clear all items from your shopping list?')) return;
    apiPostJson('/shopping-list/clear', {}).then(res => { 
      if (res && res.success) { 
        showNotification('All items cleared', 'info'); 
        refreshShoppingListUI(); 
      } 
    }).catch(() => showNotification('Server error', 'danger'));
  });

  // 3. ROW CLICK DELEGATION: Quantities
  list.addEventListener('click', (e) => {
    const inc = e.target.closest('.qty-incr');
    const dec = e.target.closest('.qty-decr');
    
    if (inc || dec) {
      const row = (inc || dec).closest('.item-row'); if (!row) return;
      const badge = row.querySelector('.qty-badge');
      let qty = Number(row.getAttribute('data-qty') || 1) || 1;
      
      qty = Math.max(1, qty + (inc ? 1 : -1)); // Clamp at 1
      row.setAttribute('data-qty', String(qty));
      if (badge) badge.textContent = String(qty);

      // Recursive Price Math
      const unit = formatPrice(row.getAttribute('data-price') || (row.querySelector('.item-price')?.textContent || '0'));
      const offer = parseOfferFromRow(row);
      const effective = calculateEffectiveUnitPrice(unit, offer);
      
      const priceEl = row.querySelector('.item-price');
      if (priceEl) priceEl.textContent = `€${(effective * qty).toFixed(2)}`;

      debounceSaveOrder();
      computeTotals();
    }
  });

  computeTotals(); // Init screen
}

/**
 * UTILITY: PERSISTENCE
 * Serializes the current DOM state to the database to preserve sort order and quantities.
 */
async function postCurrentListOrder() {
  const rows = Array.from(document.querySelectorAll('.item-row'));
  const items = rows.map(r => ({
    name: r.getAttribute('data-name'),
    purchased: r.classList.contains('purchased'),
    qty: Number(r.getAttribute('data-qty') || 1),
    price: formatPrice(r.getAttribute('data-price') || (r.querySelector('.item-price')?.textContent || '0'))
  }));
  return apiPostJson('/shopping-list/update', { items });
}

/**
 * UTILITY: DEBOUNCER
 * Prevents flooding the server with updates during rapid quantity changes.
 * Waits 700ms after the last interaction before committing the list order.
 */
let _saveTimer = null; 
function debounceSaveOrder() { 
  if (_saveTimer) clearTimeout(_saveTimer); 
  _saveTimer = setTimeout(() => postCurrentListOrder(), 700); 
}

/**
 * UTILITY: MULTIBUY PARSING
 * Converts string/attribute metadata into a math-ready Offer Object.
 */
const parseOfferFromRow = (row) => {
  // 1. Check for stored JSON object (Highest precision)
  const json = row.getAttribute('data-offer-json');
  if (json) { 
    try { 
      return JSON.parse(json); 
    } catch (e) {
      // JSON syntax error, proceed to fallbacks
    } 
  }

  // 2. Check for explicit data attributes (Legacy/Static)
  const type = row.getAttribute('data-offer-type'); // e.g. "buyXgetY"
  const x = parseInt(row.getAttribute('data-offer-x')); // e.g. 1
  const y = parseInt(row.getAttribute('data-offer-y')); // e.g. 1
  if (type === 'buyXgetY' && x && y) {
    return { type, x, y };
  }

  // 3. Fallback: Parse display string via Regex (e.g. from "1 + 1")
  const str = row.getAttribute('data-offer') || '';
  const m = str.match(/(\d+)\s*\+\s*(\d+)/);
  if (m) {
    return { type: 'buyXgetY', x: parseInt(m[1]), y: parseInt(m[2]) };
  }
  
  return null; // No offer found
};

/**
 * UTILITY: EFFECTIVE PRICE
 * Calculates unit cost after applying multibuy discounts (e.g. 1+1 = 50% off).
 */
function calculateEffectiveUnitPrice(base, offer) {
  // If no offer or invalid parameters, return full base price
  if (!offer || offer.type !== 'buyXgetY' || !offer.x || !offer.y) {
    return base;
  }
  // Formula: (Paid Items * Base Price) / Total Items (Paid + Free)
  return (offer.x * base) / (offer.x + offer.y);
}

/**
 * FOOTER CALCULATOR
 * Totals up the shopping list based on unit prices, quantities, and active deals.
 */
function computeTotals() {
  const rows = Array.from(document.querySelectorAll('.item-row')); // Get all active items
  let planned = 0;   // Grand total of the entire list
  let remaining = 0; // Total of items not yet "purchased"
  let completed = 0; // Total count of items checked off

  rows.forEach((row) => {
    // Extract unit price and quantity from row metadata
    const base = formatPrice(row.getAttribute('data-price') || (row.querySelector('.item-price')?.textContent || '0'));
    const qty = Number(row.getAttribute('data-qty') || 1);
    
    // Calculate price after applying discounts
    const effective = calculateEffectiveUnitPrice(base, parseOfferFromRow(row));
    const total = effective * qty; // Total for this specific row line

    planned += total; // Add to overall list total
    
    // Categorize based on checkbox status
    if (row.classList.contains('purchased')) {
      completed += 1; // Increment count for badge
    } else {
      remaining += total; // Increment remaining cost
    }
  });

  // UI HYDRATION: Update footer labels with formatted currency
  const pEl = document.getElementById('planned-total'); 
  if (pEl) pEl.textContent = `€${planned.toFixed(2)}`;
  
  const rEl = document.getElementById('remaining-total'); 
  if (rEl) rEl.textContent = `€${remaining.toFixed(2)}`;
  
  const cEl = document.getElementById('completed-count'); 
  if (cEl) cEl.textContent = completed;
}

/**
 * LEGACY COMPATIBILITY: CartCounter
 * Supports older templates that rely on a local-storage based cart before the MongoDB move.
 * Provides a transient cart experience for guests or specific legacy flows.
 */
class CartCounter {
  constructor() { 
    this.cartItems = []; // Internal item array
    this.loadFromStorage(); // Refresh from browser disk
    this.updateDisplay(); // Sync UI widgets
  }

  // ADD: Push new item into session
  addItem(name, price) { 
    const it = { name, price, id: Date.now() }; 
    this.cartItems.push(it); 
    this.saveToStorage(); 
    this.updateDisplay(); 
    return it.id; 
  }

  // REMOVE: Filter out item by ID
  removeItem(id) { 
    this.cartItems = this.cartItems.filter(i => i.id !== id); 
    this.saveToStorage(); 
    this.updateDisplay(); 
  }

  // UTILITY: Get item count
  getCount() { return this.cartItems.length; }

  // MATH: sum of all item prices
  getTotal() { 
    return this.cartItems.reduce((sum, item) => sum + Number(item.price || 0), 0); 
  }

  // UI: Inject counts into floating badges and cart summaries
  updateDisplay() { 
    const badge = document.getElementById('cart-counter'); 
    if (badge) { 
      badge.textContent = this.getCount(); 
      badge.style.display = this.getCount() > 0 ? 'inline-block' : 'none'; 
    }
    const totalLabel = document.getElementById('cart-total');
    if (totalLabel) {
      totalLabel.textContent = `€${this.getTotal().toFixed(2)}`; 
    }
  }

  // PERSISTENCE: Sync internal state to LocalStorage
  saveToStorage() { 
    localStorage.setItem('smartGroceryCart', JSON.stringify(this.cartItems)); 
  }

  // RESTORATION: Parse string back into array
  loadFromStorage() { 
    try { 
      this.cartItems = JSON.parse(localStorage.getItem('smartGroceryCart')) || [];
    } catch (e) { 
      this.cartItems = []; 
    } 
  }
}

const cart = new CartCounter();

/**
 * ALIAS: favoriteProduct
 * Bridge function to connect template-level `onclick` attributes to the modern favorite system.
 * This handles UI event cancellation and checks for specific "Quick Favorite" logic on the home page.
 */
const favoriteProduct = (event, arg1, arg2) => {
  if (event) {
    event.stopPropagation(); // Prevent card navigation
    event.preventDefault(); // Prevent scroll jump
  }
  
  // Choose which favorite system to invoke based on page context
  // Home page uses a specialized 'quickFavorite' to update shared storage or specific UI widgets
  if (typeof quickFavorite !== 'undefined') {
    quickFavorite(event, arg1, arg2); 
  } else {
    // All other pages use the standard async handler
    asyncToggleFavorite(event, arg1, arg2);
  }
};

// Global Exposure: Make internal helpers available to window context and external scripts.
// We also assign the wrapper to 'window.toggleFavorite' so that it is globally available 
// to inline HTML 'onclick' handlers in the templates.
window.toggleFavorite = favoriteProduct;
window.smartGrocery = { 
  showNotification, 
  formatPrice, 
  cart, 
  toggleFavorite: favoriteProduct 
};
