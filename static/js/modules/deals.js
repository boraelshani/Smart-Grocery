function setupClaimButtons() { // Deal claimer
  document.querySelectorAll('.claim-deal-btn').forEach(btn => btn.addEventListener('click', async (e) => {
    e.stopPropagation(); // Stop click from triggering parent "Card Detail" navigation
    
    // Data Extraction
    const id = btn.getAttribute('data-id') || btn.getAttribute('data-title');
    const title = btn.getAttribute('data-title') || '';
    const price = btn.getAttribute('data-price') || '';
    const originalPrice = btn.getAttribute('data-original-price') || '';
    const offerStr = btn.getAttribute('data-offer') || '';
    const offerJson = btn.getAttribute('data-offer-json') || '';
    const offerType = btn.getAttribute('data-offer-type') || '';
    const offerX = btn.getAttribute('data-offer-x') || '';
    const offerY = btn.getAttribute('data-offer-y') || '';
    const image = btn.getAttribute('data-image') || '';
    
    if (!id) return showNotification('Missing deal id', 'danger');

    // Price Normalization
    const discounted_price_val = Number(String(price).replace(/[^0-9.]/g, '')) || 0;
    const original_price_val = Number(String(originalPrice).replace(/[^0-9.]/g, '')) || discounted_price_val;

    // Offer Payload Parsing (Multibuy detection)
    let offerPayload = null;
    try { if (offerJson) offerPayload = JSON.parse(offerJson); } catch (err) { offerPayload = null; }
    
    // Logic fallback for different attribute naming schemes
    if (!offerPayload && offerType === 'buyXgetY' && offerX && offerY) {
      const xNum = parseInt(offerX, 10) || 0;
      const yNum = parseInt(offerY, 10) || 0;
      if (xNum && yNum) offerPayload = { type: 'buyXgetY', x: xNum, y: yNum };
    }
    if (!offerPayload && offerStr) { // regex match "1 + 1" or "2 + 1"
      const m = offerStr.match(/(\d+)\s*\+\s*(\d+)/);
      if (m) offerPayload = { type: 'buyXgetY', x: parseInt(m[1], 10) || 0, y: parseInt(m[2], 10) || 0 };
    }

    // Construct the standardized Item Object
    const item = {
      name: title,
      price: discounted_price_val || original_price_val,
      price_val: discounted_price_val || original_price_val,
      image: image,
      offer: offerPayload || offerStr || null,
      deal_id: id
    };

    try {
      // Logic: Instead of claiming blindly, we trigger the List Selector modal
      // This allows the user to choose WHICH list to add the deal to.
      const res = await addItemToShoppingList(item);
      if (res && res.deferred) {
        return; // List selector modal is now active, flow continues there.
      }
      
      // Handle non-modal path (Legacy or direct fallback)
      if (res && res.success) {
        showNotification('Deal added to your list', 'success');
        refreshShoppingListUI(); // Trigger sync
      } else if (res && res.error) {
        showNotification(res.error, 'danger');
      } else {
        showNotification('Could not add deal', 'danger');
      }
    } catch (err) {
      showNotification('Error adding deal', 'danger');
    }
  }));
}

/**
 * GLOBAL "ADD TO CART" HANDLER
 * The primary entry point for any product-to-list action requested by the user.
 * Supports both raw data parameters and DOM element extraction.
 * Handles "Comparison Mode" stores (where a user must pick a store before adding).
 */
window.handleAddToCart = async function (event, name, price, image, store) { // Shopping hub
  if (event) { // Standard browser event cleanup
    event.stopPropagation(); // Stop parent triggers
    if (event.preventDefault) event.preventDefault(); // Stop hash changes/scrolling
  }

  // 1. DATA HYDRATION: Support both direct (item) and element (this) binding
  let item;
  if (name instanceof HTMLElement) { // Called via handleAddToCart(event, this)
    const btn = name; // Reference input
    
    // 2. COMPARISON MODE LOGIC (Special handling for Compare Prices grid)
    // Check if item belongs to a product card that has multiple store options.
    const productCard = btn.closest('.product-card');
    let storeSelected = false; 

    if (productCard) { // Inside a product card?
        const hasStoreOptions = productCard.querySelector('.store-item'); // Multiple retailers found?
        if (hasStoreOptions) { // User MUST pick 1 store to add
            const selectedStoreItem = productCard.querySelector('.store-item.selected');
            // Removed restriction, defaults to main button price
            
            // Extract attributes with specific Store Overrides
            const itemName = btn.getAttribute('data-name') || btn.getAttribute('data-title') || 'Item';
            // Prefer the price specific to the selected store badge
            let itemPrice = (selectedStoreItem ? selectedStoreItem.getAttribute('data-store-price') : null) || btn.getAttribute('data-price') || '';
            const itemStore = (selectedStoreItem ? selectedStoreItem.getAttribute('data-store-name') : null) || btn.getAttribute('data-store') || '';
            const itemImage = (selectedStoreItem ? selectedStoreItem.getAttribute('data-image') : null) || btn.getAttribute('data-image') || '';
            const itemId = btn.getAttribute('data-id') || null;
            
            // Extract complex Offer meta-data
            const dealId = btn.getAttribute('data-deal-id') || null;
            const offerJson = btn.getAttribute('data-offer-json') || '';
            const tierJson = btn.getAttribute('data-tier-json') || '';
            const offerType = btn.getAttribute('data-offer-type') || '';
            const offerX = btn.getAttribute('data-offer-x') || '';
            const offerY = btn.getAttribute('data-offer-y') || '';
            
            let offerPayload = null;
            try { if (offerJson) offerPayload = JSON.parse(offerJson); } catch (err) { }
            
            let discountTiers = null;
            try { if (tierJson) discountTiers = JSON.parse(tierJson); } catch (err) { }
            
            // Standardize BuyXGetY if not in JSON blob
            if (!offerPayload && offerType === 'buyXgetY' && offerX && offerY) {
                offerPayload = { type: 'buyXgetY', x: parseInt(offerX), y: parseInt(offerY) };
            }

            // Create standardized aggregate object
            item = {
                name: itemName,
                price: itemPrice,
                store: itemStore,
                image: itemImage,
                id: itemId,
                deal_id: dealId,
                offer_payload: offerPayload,
                discount_tiers: discountTiers
            };
            storeSelected = true; // Signal we have a valid composite item
        }
    }
    
    // Fallback: If not handled by multi-store logic, just use the element reference directly
    if (!storeSelected) { item = name; }
  } else { // Called via direct parameters (legacy scripts)
    item = { name, price, store, image };
    const priceVal = formatPrice(price);
    if (!isNaN(priceVal) && priceVal > 0) item.price_val = priceVal;
  }

  try {
    // 3. TRANSACTION EXECUTION
    const res = await addItemToShoppingList(item);
    
    // Flow Branch:
    if (res && res.deferred) { // Modal is now open
      return; 
    }
    
    // Flow Branch:
    if (res && (res.success || res.success === true)) { // Immediate success (auto-add)
      showNotification('Added to shopping list', 'success');
      refreshShoppingListUI(); // sync UI
    } else if (res && res.error) { // Managed error
      showNotification(res.error, 'danger');
    } else { // Generic error
      showNotification('Could not add to list', 'danger');
    }
  } catch (err) { // Fatal error (Network/Auth)
    console.error('Error adding to cart:', err);
    showNotification('Error adding to list. Are you logged in?', 'danger');
  }
};

/**
 * PRODUCT MODAL SYSTEM
 * Orchestrates the "View Details" popup logic.
 * 1. Fetches full item documentation (origin, usage, storage) from MongoDB.
 * 2. Dynamically rebuilds the modal body HTML to match the specific product schema.
 * 3. Sanitizes and renders high-res images.
 */
