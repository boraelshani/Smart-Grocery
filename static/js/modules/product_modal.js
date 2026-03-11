function setupProductModalHandlers() { // Details hub
  // Use event delegation on document.body for high performance.
  // This avoids memory leaks and handles dynamically injected search results.
  if (productModalHandlerBound) return; // Prevent double registration
  productModalHandlerBound = true;

  document.addEventListener('click', async (e) => { // Global click delegator
    const target = e.target;
    if (!target) return;

    // 1. TRIGGER DETECTION: Is this a "View Details" button?
    const viewBtn = target.closest('.view-details-btn, .btn-premium-view');
    if (viewBtn) { // YES
      // Identify the product via ID or Name
      const pid = viewBtn.getAttribute('data-id') || viewBtn.getAttribute('data-product-id') || null;
      const titleAttr = viewBtn.getAttribute('data-title') || '';
      
      // Identify target modal element
      const targetSelector = viewBtn.getAttribute('data-bs-target') || '#productModal';
      const modal = document.querySelector(targetSelector);
      if (!modal) return; // Guard

      /**
       * INTERNAL UI HYDRATOR
       * Updates the modal's DOM with data fetched from the backend or the button attributes.
       */
      async function populateModalFromDoc(doc) { // Builder
        // Data Normalization (Handle empty/missing values)
        const title = doc.name || doc.title || titleAttr || 'Product';
        const price = doc.price || (doc.cheapest && doc.cheapest.price) || '';
        const store = doc.store || (doc.cheapest && doc.cheapest.store) || (doc.stores && doc.stores[0] && doc.stores[0].store) || '';
        
        // Image Processing logic
        let image = doc.image || (doc.images && doc.images[0]) || viewBtn.getAttribute('data-image') || 'https://via.placeholder.com/300x200';
        
        // PATH RESOLUTION: If `image` is a cloud identifier (no slash/protocol), convert to full CDN URL
        if (image && !/^https?:\/\//i.test(image) && !image.startsWith('/')) {
          image = `https://images.example.com/${image}`; // Example CDN path
        }
        
        // Header Update
        modal.querySelector('.modal-title') && (modal.querySelector('.modal-title').textContent = title + ' Details');
        
        // Visual Update (Main Gallery Image)
        const img = modal.querySelector('.modal-body img'); 
        if (img) {
          img.src = image;
          img.style.width = '700px'; 
          img.style.height = '700px'; 
          img.style.objectFit = 'cover'; // Maintain aspect ratio without distortion
        }
        
        // Content Area Selection
        const body = modal.querySelector('.modal-body');
        if (body) {
          body.querySelector('h6') && (body.querySelector('h6').textContent = title);
          
          // STRUCTURED DATA RENDERING:
          // We build an array of formatted HTML strings based on WHICH fields actually exist 
          // in the database document. This avoids showing empty labels like "Storage: N/A".
          const infoHtml = [];
          if (doc.identification_mark) infoHtml.push(`<p><strong>Identification Mark:</strong> ${escapeHtml(doc.identification_mark)}</p>`);
          if (doc.country_of_origin) infoHtml.push(`<p><strong>Country/Place of Origin:</strong> ${escapeHtml(doc.country_of_origin)}</p>`);
          if (doc.storage_instructions) infoHtml.push(`<p><strong>Storage Instructions:</strong><br>${escapeHtml(doc.storage_instructions)}</p>`);
          if (doc.usage_instructions) infoHtml.push(`<p><strong>Usage Instructions:</strong><br>${escapeHtml(doc.usage_instructions)}</p>`);
          if (doc.origin_country) infoHtml.push(`<p><strong>Country:</strong> ${escapeHtml(doc.origin_country)}</p>`);
          if (doc.product_labeling) infoHtml.push(`<p><strong>Product Labeling:</strong> ${escapeHtml(doc.product_labeling)}</p>`);
          
          // Universal Fallback: Show raw description if no structured fields match
          if (doc.description && infoHtml.length === 0) infoHtml.push(`<p>${escapeHtml(doc.description)}</p>`);

          // Lead Attributes: Price and Store (Prepend to the list)
          infoHtml.unshift(`<p><strong>Price:</strong> €${escapeHtml(price)}</p>`, `<p><strong>Available at:</strong> ${escapeHtml(store)}</p>`);

          // DOM CLEANUP: Remove old paragraphs from previous views
          // We preserve the Header (h6) and Image (img) to maintain container layout.
          const bodyChildren = Array.from(body.children).filter(ch => !ch.matches('img') && ch.tagName.toLowerCase() !== 'h6');
          bodyChildren.forEach(ch => ch.remove());
          
          // Inject new structured info as a single block to reduce DOM thrashing
          const insertDiv = document.createElement('div'); 
          insertDiv.innerHTML = infoHtml.join('\n');
          body.appendChild(insertDiv);
        }

        // SYNC MODAL ACTION BUTTON
        // Ensures the "Add to List" button inside the modal has the correct data for THIS product.
        const addBtn = modal.querySelector('.add-to-cart-btn');
        if (addBtn) {
          addBtn.setAttribute('data-name', title);
          addBtn.setAttribute('data-price', price);
          addBtn.setAttribute('data-store', store);
          addBtn.setAttribute('data-image', image);
        }
      }

      // 2. DATA ACQUISITION FLOW
      // IIFE (Immediately Invoked Function Expression) to handle async fetching
      (async () => { // Isolation layer
        try {
          // Construct API endpoint URL based on what identifier we have
          let url = '/api/product';
          if (pid) {
            url += `?id=${encodeURIComponent(pid)}`; // Search by DB ID
          } else {
            url += `?name=${encodeURIComponent(titleAttr)}`; // Search by string name
          }
          
          const r = await fetch(url, { credentials: 'same-origin' });
          const j = await r.json().catch(() => ({}));
          const doc = j.item || j; // Handle nested or flat response objects
          
          if (doc && Object.keys(doc).length) { // SUCCESS: Found full docs in MongoDB
            await populateModalFromDoc(doc);
          } else { // FAIL: Product not in rich database, fallback to basic UI attrs
            const fallback = {
              name: titleAttr,
              price: viewBtn.getAttribute('data-price') || '',
              store: viewBtn.getAttribute('data-store') || '',
              image: viewBtn.getAttribute('data-image') || ''
            };
            await populateModalFromDoc(fallback);
          }
        } catch (err) { // Network error: Use fallback UI data
          const fallback = {
            name: titleAttr,
            price: viewBtn.getAttribute('data-price') || '',
            store: viewBtn.getAttribute('data-store') || '',
            image: viewBtn.getAttribute('data-image') || ''
          };
          await populateModalFromDoc(fallback);
        }
      })();
      return; // Stop processing this click
    }

    // 2. TRIGGER DETECTION: "Add to Cart" button (e.g. inside the modal or a simple card)
    if (target.classList && (target.classList.contains('add-to-cart-btn') || target.closest('.add-to-cart-btn'))) {
      e.stopPropagation(); // Avoid double-clicks firing parent handlers
      
      const btn = target.classList.contains('add-to-cart-btn') ? target : target.closest('.add-to-cart-btn');
      const modalRoot = btn.closest('.modal'); // check if we are inside a modal
      
      // Extraction Priority: Attribute -> Modal Header -> Default
      const name = btn.getAttribute('data-name') || btn.getAttribute('data-title') || (modalRoot?.querySelector('h6')?.textContent || 'Item');
      const price = btn.getAttribute('data-price') || '';
      const store = btn.getAttribute('data-store') || '';
      const image = btn.getAttribute('data-image') || (modalRoot?.querySelector('img')?.src || '');
      
      const item = { name, price, store, image };
      const priceVal = formatPrice(price);
      if (!isNaN(priceVal) && priceVal > 0) item.price_val = priceVal;
      
      try {
        // Trigger the standard List Selector flow
        const res = await addItemToShoppingList(item);
        if (res && res.deferred) { // Modal logic handled it
          return;
        }
        
        if (res && (res.success || res.success === true)) {
          showNotification('Added to shopping list', 'success');
          // AUTOMATED UI CLEANUP: 
          // If the button was inside a modal, close the modal once the item is added.
          if (modalRoot) {
            try { 
              const modalEl = bootstrap.Modal.getInstance(modalRoot); 
              if (modalEl) modalEl.hide(); 
            } catch (e) { }
          }
          refreshShoppingListUI(); // Trigger sync
        } else if (res && res.error) {
          showNotification(res.error, 'danger');
        } else {
          showNotification('Could not add to list', 'danger');
        }
      } catch (err) {
        showNotification('Server error adding item', 'danger');
      }
      return;
    }

    // Add to List button in search results or elsewhere (including Compare Page)
    // 3. TRIGGER DETECTION: "Add to List" (Standard grid buttons, Compare page results, or Premium Hero actions)
    if (target.classList && (target.classList.contains('add-to-list-btn') || target.closest('.add-to-list-btn') ||
      target.classList.contains('btn-premium-add') || target.closest('.btn-premium-add') ||
      target.classList.contains('btn-premium-action') || target.closest('.btn-premium-action') ||
      target.classList.contains('btn-premium-hero-add') || target.closest('.btn-premium-hero-add'))) {
      
      e.stopPropagation(); // Avoid triggering parent links/cards
      e.preventDefault();  // Stop jump-to-top behavior

      // Resolve the actual button element (handles clicking the icon inside the button)
      const btn = target.classList.contains('add-to-list-btn') ? target :
        (target.closest('.add-to-list-btn') || target.closest('.btn-premium-add') || target.closest('.btn-premium-action') || target);
      
      // Standard Metadata extraction
      const name = btn.getAttribute('data-name') || btn.getAttribute('data-title') || 'Item';
      const offerJson = btn.getAttribute('data-offer-json') || '';
      const offerType = btn.getAttribute('data-offer-type') || '';
      const offerX = btn.getAttribute('data-offer-x') || '';
      const offerY = btn.getAttribute('data-offer-y') || '';
      const originalPrice = btn.getAttribute('data-original-price') || '';
      const dealId = btn.getAttribute('data-id') || btn.getAttribute('data-deal-id') || null;

      // DYNAMIC PRICE/STORE DETECTION:
      // Critical for the Compare Prices page where one product has multiple store prices.
      let price = btn.getAttribute('data-price') || '';
      let store = btn.getAttribute('data-store') || '';
      const productCard = btn.closest('.product-card');

      if (productCard) { // If button is inside a multi-store container
        // Locate the currently "selected" store badge in the list
        const selectedStoreItem = productCard.querySelector('.store-item.selected');

        // Check if store options exist but nothing is selected.
        const hasStoreOptions = productCard.querySelector('.store-item');
        if (hasStoreOptions && !selectedStoreItem) {
          showNotification('Please select a store first', 'warning'); // Mandatory choice
          return;
        }

        // If a store is active, override the generic product data with Store-specific data
        if (selectedStoreItem) {
          store = selectedStoreItem.getAttribute('data-store-name');
          const storePrice = selectedStoreItem.getAttribute('data-store-price');
          if (storePrice) price = storePrice;
        }
      }

      const id = btn.getAttribute('data-id') || null;
      const img = btn.getAttribute('data-image') || '';

      // Deserialize Offer Logic
      let offerPayload = null;
      try { if (offerJson) offerPayload = JSON.parse(offerJson); } catch (err) { offerPayload = null; }
      if (!offerPayload && offerType === 'buyXgetY' && offerX && offerY) {
        const xNum = parseInt(offerX, 10) || 0;
        const yNum = parseInt(offerY, 10) || 0;
        if (xNum && yNum) offerPayload = { type: 'buyXgetY', x: xNum, y: yNum };
      }

      // MULTIBUY MATH:
      // We must store the original unit price for BuyX-GetY calculation transparency on the list.
      let priceToUse = price;
      if (offerPayload && (offerPayload.type === 'buyXgetY' || offerType === 'buyXgetY') && originalPrice) {
        priceToUse = originalPrice;
      }

      // Final Hydration
      const item = { name, price: priceToUse, id };
      if (img) item.image = img;
      if (store) item.store = store;
      if (dealId) item.deal_id = dealId;
      if (offerPayload) item.offer = offerPayload;
      
      const priceVal = formatPrice(priceToUse);
      if (!isNaN(priceVal) && priceVal > 0) item.price_val = priceVal;

      try {
        // Trigger the asynchronous list picker flow
        const res = await addItemToShoppingList(item);
        if (res && res.deferred) { // UI Handled via Modal
          return;
        }
        
        // Immediate Success path
        if (res && (res.success || res.success === true)) {
          showNotification('Added to shopping list', 'success');
          refreshShoppingListUI();
        } else if (res && res.error) {
          showNotification(res.error, 'danger');
        } else {
          showNotification('Could not add to list', 'danger');
        }
      } catch (err) {
        showNotification('Server error adding item', 'danger');
      }
      return;
    }
  });
}

/**
 * PROFILE EDIT SYSTEM
 * Handles the "Edit Profile" modal logic on the user settings page.
 * Manages phone number formatting (Country Code + digits) and persistence.
 */
