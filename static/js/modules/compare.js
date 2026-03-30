function setupCompareHandlers() { // Sorting assistant
  document.addEventListener('click', (e) => { // Delegate click events
    // Check if the specific target or its parent is the Sort button
    const btn = e.target.closest('.sort-stores-btn'); // CSS class check
    if (!btn) return; // Ignore irrelevant clicks
    
    // Find context (Identify the specific product card containing the pricing list)
    const card = btn.closest('.card'); // Upward traversal
    if (!card) return; // Safeguard
    const list = card.querySelector('.list-group'); // Target the unordered list of prices
    if (!list) return; // Safeguard

    // Collect all list items into a native array for sorting
    const items = Array.from(list.querySelectorAll('li')); // DOM Node array
    // Internal Helper: Strip symbols and whitespace to get a raw float
    function parsePriceFromText(text) { // Sanitizer
      if (!text) return Number.POSITIVE_INFINITY; // Handle empty
      const m = String(text).match(/\d+[\d,.]*/); // Regex match for decimal numbers
      if (!m) return Number.POSITIVE_INFINITY; // Handle no numbers found
      const cleaned = m[0].replace(/,/g, ''); // Standardize (remove commas)
      const n = Number(cleaned); // Cast to float
      return isNaN(n) ? Number.POSITIVE_INFINITY : n; // Fallback to infinity (sorts to bottom)
    }
    
    // Create temporary processing array of objects [Original_Node, Numeric_Value]
    const mapped = items.map(li => { // Map for efficiency
      const priceText = li.textContent || li.innerText || ''; // Extract text content
      return { node: li, price: parsePriceFromText(priceText) }; // Return pair
    });
    
    // Sort array in-memory by Price (Ascending: Low -> High)
    mapped.sort((a, b) => a.price - b.price); // Standard comparison
    
    // Re-render: Clear existing unsorted list and append sorted nodes back into DOM
    list.innerHTML = ''; // Wipe content
    mapped.forEach((m, idx) => { // Re-append loop
      // VISUAL ENHANCEMENT: Add 'Best Price' badge to the winner (first item in sorted array)
      if (idx === 0) { // Top result?
        // Check if the badge is already present to avoid duplicates
        if (!m.node.querySelector('.best-price-badge')) { // Missing badge?
          const span = document.createElement('span'); // Create new tag
          span.className = 'badge bg-warning text-dark ms-2 best-price-badge'; // Style
          span.textContent = 'Best Price'; // Label
          // Append to the specific list item node
          m.node.appendChild(span); // DOM update
        }
      } else { // Not the best price?
        // Cleanup: Remove existing badges from items that were previously winners but lost their rank
        const existing = m.node.querySelector('.best-price-badge'); if (existing) existing.remove(); // Remove tag
      }
      list.appendChild(m.node); // Re-attach node to parent list
    });
  });
}

/**
 * CLIENT-SIDE COMPARISON FILTERS
 * Allows users to filter distinct store cards without page reload.
 */
function setupStoreSelection() { // Interactive pricing logic
  document.addEventListener('click', function (e) { // Track interactions
    // EXCEPTION: If clicking the "Go to Store" button (external link), 
    // don't trigger selection logic which would just toggle the UI.
    if (e.target.closest('.btn-go-store')) { // External link check
      e.stopPropagation(); // Avoid bubbling
      return; // Exit
    }

    // Check if clicked element is a Store Option within a product card (.store-item)
    const storeItem = e.target.closest('.store-item'); // Match target
    if (storeItem) { // Valid interaction?
      const productCard = storeItem.closest('.product-card') || storeItem.closest('.card'); // Get container
      if (productCard) { // Within a valid card?
        const isAlreadySelected = storeItem.classList.contains('selected'); // State check

        // 1. GLOBAL RESET (Ensures only one store is active across the entire page)
        // This is a UI decision to maintain a clean compare view.
        try { // Error safety
          document.querySelectorAll('.store-item.selected').forEach(selectedItem => { // Clear all "Selected"
            if (selectedItem === storeItem) return; // Skip current if we're just toggling in local scope

            // Find other cards and reset their UI state to their default/cheapest price
            const otherCard = selectedItem.closest('.product-card') || selectedItem.closest('.card'); // Parent lookup
            selectedItem.classList.remove('selected'); // CSS Change

            if (otherCard) { // Reset siblings
              const otherAddBtn = otherCard.querySelector('.btn-premium-add'); // Primary button
              const otherPriceBadge = otherCard.querySelector('.price-badge'); // Price label

              // Revert Button Data to initial state
              if (otherAddBtn) { // Found button?
                // Restore original (lowest) price stored in data-initial-price attribute
                otherAddBtn.dataset.price = otherAddBtn.getAttribute('data-initial-price') || ''; // Reset price
                otherAddBtn.dataset.store = ''; // Clear specific store selection tag
              }
              // Revert Price Badge text
              if (otherPriceBadge) { // Found badge?
                const initialPrice = otherAddBtn ? otherAddBtn.getAttribute('data-initial-price') : ''; // Read cached price
                if (initialPrice) { // Has value?
                  const inner = otherPriceBadge.querySelector('i') ? '<i class="bi bi-tag-fill"></i> ' : ''; // Preserve icon
                  otherPriceBadge.innerHTML = inner + '€' + initialPrice; // Reset label
                }
              }
            }
          });
        } catch (err) { console.error('Error in global store reset', err); } // Log failures

        // 2. LOCAL CARD RESET
        // Deselect other optional stores within THIS same card to ensure internal consistency
        const allLocalStoreItems = productCard.querySelectorAll('.store-item'); // Grab siblings
        allLocalStoreItems.forEach(item => item.classList.remove('selected')); // Wipe local state

        // Local References for UI updates
        const addBtn = productCard.querySelector('.btn-premium-add'); // "Add to List" target
        const priceBadge = productCard.querySelector('.price-badge'); // Main price label
        const productImage = productCard.querySelector('.product-image'); // Visual slot

        // 3. TOGGLE STATES (Select vs Deselect logic)
        if (isAlreadySelected) { // User clicked the currently active store?
          // A. DESELECT (Revert to default "best price" view)
          if (addBtn) { // Reset button data attributes
            addBtn.dataset.price = addBtn.getAttribute('data-initial-price') || ''; // Revert to lowest
            addBtn.dataset.store = ''; // Clear store name
          }
          if (priceBadge) { // Reset price label
            const initialPrice = addBtn ? addBtn.getAttribute('data-initial-price') : ''; // Get cache
            if (initialPrice) { // Apply
              const inner = priceBadge.querySelector('i') ? '<i class="bi bi-tag-fill"></i> ' : ''; // Keep icon
              priceBadge.innerHTML = inner + '€' + initialPrice; // Update text
            }
          }
          // Revert Product Image to the generic variant
          if (productImage && addBtn) { // Found visual?
            const originalImage = addBtn.getAttribute('data-image'); // Read source
            if (originalImage) productImage.src = originalImage; // Switch back
          }
        } else { // User clicked a new, inactive store?
          // B. SELECT (Target the specific store data)
          storeItem.classList.add('selected'); // Highlight item
          
          // Update "Add to List" button with selected store's specific price and brand name
          if (addBtn) { // Sync data
            addBtn.dataset.price = storeItem.dataset.storePrice; // Set specific price
            addBtn.dataset.store = storeItem.dataset.storeName; // Set specific store
          }
          // Update Price Badge with visual feedback animation
          if (priceBadge) { // Sync label
            const inner = priceBadge.querySelector('i') ? '<i class="bi bi-tag-fill"></i> ' : ''; // Icon persistent
            priceBadge.innerHTML = inner + '€' + storeItem.dataset.storePrice; // New price
            // Trigger "Pop" scale animation via inline style manipulation
            priceBadge.style.transform = 'scale(1.1)'; // Enlarge
            setTimeout(() => { priceBadge.style.transform = 'scale(1)'; }, 200); // Shrink back after delay
          }
          // Update Product Image to specific store version (if available in dataset)
          if (productImage && storeItem.dataset.image) { // Asset check
            // Only swap if the image provided is a real asset and not a generic placeholder
            if (!storeItem.dataset.image.includes('placeholder.svg')) { // Real image found?
               productImage.src = storeItem.dataset.image; // Visual switch
            }
          }
        }
      }
      e.preventDefault(); // Stop page jumps
      e.stopPropagation(); // Stop event propagation
    }
  });
}


/**
 * ===============================================
 * COMPARE PAGE: HYBRID FILTERING SYSTEM
 * ===============================================
 * This module handles the complex task of filtering product comparison cards.
 * It employs a "Hybrid" strategy handling both:
 * 1. SERVER-SIDE Query Params (e.g. ?category=dairy&page=2) -> Reloads page
 * 2. CLIENT-SIDE DOM Filtering (e.g. Price Range, Store) -> Hides elements instantly
 */
function setupCompareFilters() {
  const productsRow = document.getElementById('products-grid') || document.querySelector('section.container .row.g-4');
  if (!productsRow) return;

  // ----------------------
  // INPUT REFERENCES
  // ----------------------
  const searchInput = document.getElementById('product-search-input');
  const searchBtn = document.getElementById('product-search-btn');
  const storeFilter = document.getElementById('store-filter'); // Dropdown
  const categorySelect = document.getElementById('category-filter'); // Dropdown
  const categoryChipsRow = document.querySelector('.category-chip-row'); // Horizontal scrollable chips
  const minInput = document.getElementById('min-price');
  const maxInput = document.getElementById('max-price');
  const sortSelect = document.getElementById('sort-order');
  const applyBtn = document.getElementById('apply-filters');
  const clearBtn = document.getElementById('clear-filters');
  const activeFiltersDiv = document.getElementById('active-filters'); // Area for "Pills"

  // ----------------------
  // STATE MANAGEMENT
  // ----------------------
  // We store a reference to every product card on initial load.
  // This allows us to "un-hide" them later without reloading the page.
  let allProducts = [];

  /**
   * INITIALIZER: SCAN DOM
   * Scans the server-rendered HTML to build our internal index of products.
   * Also dynamically populates the "Store" dropdown based on what's visible.
   */
  const collectStoresAndCategories = () => {
    const productDivs = Array.from(productsRow.querySelectorAll('[data-stores]'));
    allProducts = productDivs;
    const storeSet = new Set();
    
    // Extract available stores from JSON data attributes
    productDivs.forEach(div => {
      try {
        const stores = JSON.parse(div.getAttribute('data-stores') || '[]');
        stores.forEach(s => { 
          if (s && (s.store || s.name)) storeSet.add((s.store || s.name).trim()); 
        });
      } catch (e) { console.warn('Bad JSON in data-stores', e); }
    });
    
    // Add unique found stores to the filter dropdown
    if (storeFilter) {
      const existing = new Set(Array.from(storeFilter.options).map(o => o.value));
      storeSet.forEach(name => { 
        if (!existing.has(name)) { 
          const opt = document.createElement('option'); 
          opt.value = name; 
          opt.textContent = name; 
          storeFilter.appendChild(opt); 
        } 
      });
    }
  };

  /**
   * HELPER: PRICE PARSER
   * Sanitizes currency strings ("€2,300.00") into sortable numbers (2300.00).
   */
  const parsePrice = (v) => { 
    if (v === null || v === undefined || v === '') return Number.POSITIVE_INFINITY; 
    const n = Number(String(v).toString().replace(/[^0-9.\-]/g, '')); 
    return isNaN(n) ? Number.POSITIVE_INFINITY : n; 
  };

  /**
   * CORE LOGIC: APPLY FILTERS
   * Iterates over all known products and checks them against ALL active criteria.
   * This is an "AND" filter (must match Search AND Store AND Category AND Price).
   */
  const applyFilters = () => {
    // 1. Snapshot Input Values
    const searchVal = searchInput ? searchInput.value.trim().toLowerCase() : '';
    const activeChip = categoryChipsRow ? categoryChipsRow.querySelector('.category-chip.active') : null;
    const chipVal = activeChip ? (activeChip.dataset.categoryChip || '').trim() : '';
    const selectCategoryVal = categorySelect ? (categorySelect.value || '').trim() : '';
    const categoryVal = chipVal || selectCategoryVal; // Chip wins if both present
    const storeVal = storeFilter ? storeFilter.value : '';
    const minVal = minInput ? parseFloat(minInput.value) : NaN;
    const maxVal = maxInput ? parseFloat(maxInput.value) : NaN;
    const sortVal = sortSelect ? sortSelect.value : 'price-asc';

    const visible = [];

    // 2. Evaluation Loop
    allProducts.forEach(col => {
      if (!col) return;

      // Extract Item Data
      const priceAttr = col.getAttribute('data-price') || '';
      const price = parsePrice(priceAttr);
      const productName = (col.getAttribute('data-name') || '').toLowerCase();

      // TEST A: Search Text (Partial match)
      let searchMatch = true;
      if (searchVal) {
        searchMatch = productName.includes(searchVal);
      }

      // TEST B: Store Availability
      // Does this product exist in the selected store?
      let storeMatch = true;
      if (storeVal) {
        try {
          const stores = JSON.parse(col.getAttribute('data-stores') || '[]');
          storeMatch = stores.some(s => { 
            const n = (s.store || s.name || '').toString().trim(); 
            return n.toLowerCase() === storeVal.toLowerCase(); 
          });
        } catch (e) { storeMatch = false; }
      }

      // TEST C: Category
      let categoryMatch = true;
      if (categoryVal) {
        const cat = (col.getAttribute('data-category') || '').trim().toLowerCase();
        categoryMatch = cat === categoryVal.toLowerCase();
      }

      // TEST D: Price Range
      let priceMatch = true;
      if (!isNaN(minVal)) priceMatch = priceMatch && (price >= minVal);
      if (!isNaN(maxVal)) priceMatch = priceMatch && (price <= maxVal);

      // 3. Visibility Toggle
      if (searchMatch && storeMatch && categoryMatch && priceMatch) {
        col.style.display = ''; // Show
        visible.push({ col, price, name: productName });
      } else {
        col.style.display = 'none'; // Hide
      }
    });

    // 4. Client-Side Sorting
    if (visible.length) {
      if (sortVal === 'price-asc' || sortVal === 'price-desc') {
        visible.sort((a, b) => sortVal === 'price-asc' ? a.price - b.price : b.price - a.price);
      } else if (sortVal === 'name-asc' || sortVal === 'name-desc') {
        visible.sort((a, b) => sortVal === 'name-asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name));
      }
      // Re-order DOM elements
      visible.forEach(v => productsRow.appendChild(v.col));
    }

    // 5. Update UI Badges
    updateActiveFilters(searchVal, categoryVal, storeVal, minVal, maxVal);
  };


  /**
   * UI COMPONENT: ACTIVE FILTER PILLS
   * Renders the "Search: Milk [x]" badges at the top of the grid.
   */
  const updateActiveFilters = (searchVal, categoryVal, storeVal, minVal, maxVal) => { // Badge manager
    if (!activeFiltersDiv) return; // Exit if visual area is missing
    activeFiltersDiv.innerHTML = ''; // Start from scratch
    let hasFilters = false; // Flag for "Clear All" visibility

    // Helper: Create Pill (Reusable component for badges)
    const createFilterBadge = (text, onRemove) => { // UI element builder
      const badge = document.createElement('span'); // Create span
      badge.className = 'badge bg-primary d-flex align-items-center gap-1 p-2'; // Tailwind-esque Bootstrap classes
      badge.style.borderRadius = '20px'; // Rounded aesthetics
      badge.innerHTML = `${text} <i class="bi bi-x-circle ms-1" style="cursor:pointer;"></i>`; // Insert text and icon
      badge.querySelector('i').onclick = onRemove; // Attach specific deletion logic
      return badge; // Return node
    };

    // Add Pill for Search (If user typed a query)
    if (searchVal) { // Found search?
      hasFilters = true; // Raise flag
      activeFiltersDiv.appendChild(createFilterBadge('Search: ' + searchVal, () => { // Create and bind
        if (searchInput) { searchInput.value = ''; applyFilters(); } // Reset and refresh
      }));
    }

    // Add Pill for Category (If user selected a category tag)
    if (categoryVal) { // Found category?
      hasFilters = true; // Raise flag
      activeFiltersDiv.appendChild(createFilterBadge('Category: ' + categoryVal, () => { // Create and bind
        if (categoryChipsRow) categoryChipsRow.querySelectorAll('.category-chip').forEach(ch => ch.classList.remove('active')); // Reset chips
        if (categorySelect) categorySelect.value = ''; // Reset select
        applyFilters(); // Trigger layout update
      }));
    }

    // Add Pill for Store (If user filtered by store name)
    if (storeVal) { // Found store?
      hasFilters = true; // Raise flag
      activeFiltersDiv.appendChild(createFilterBadge('Store: ' + storeVal, () => { // Create and bind
        if (storeFilter) { storeFilter.value = ''; applyFilters(); } // Reset and refresh
      }));
    }

    // Add Pill for Price Range (If user provided numerical limits)
    if (!isNaN(minVal) || !isNaN(maxVal)) { // Found pricing?
      hasFilters = true; // Raise flag
      let text = 'Price: '; // Base label
      if (!isNaN(minVal) && !isNaN(maxVal)) text += `€${minVal}-€${maxVal}`; // Range text
      else if (!isNaN(minVal)) text += `Min €${minVal}`; // Floor only
      else text += `Max €${maxVal}`; // Ceiling only

      activeFiltersDiv.appendChild(createFilterBadge(text, () => { // Create and bind
        if (minInput) minInput.value = ''; // Reset floor
        if (maxInput) maxInput.value = ''; // Reset ceiling
        applyFilters(); // Synchronize view
      }));
    }

    // Show/Hide "Clear All" button based on whether filters are currently active
    if (hasFilters) { // Active filters?
      activeFiltersDiv.style.display = 'flex'; // Make visible
      const clearAll = document.createElement('button'); // Create reset trigger
      clearAll.className = 'btn btn-sm btn-outline-secondary rounded-pill ms-2'; // Styling
      clearAll.innerHTML = '<i class="bi bi-x-circle"></i> Clear All'; // Label
      clearAll.onclick = clearFilters; // Attach mass reset logic
      activeFiltersDiv.appendChild(clearAll); // Add to UI
    } else { // No active filters?
      activeFiltersDiv.style.display = 'none'; // Hide container
    }
  };

  /**
   * RESET HANDLER
   * Clears all filters and restores full list without needing a server reload.
   */
  const clearFilters = () => { // Memory reset
    if (searchInput) searchInput.value = ''; // Clear text
    if (storeFilter) storeFilter.value = ''; // Reset store
    if (categorySelect) categorySelect.value = ''; // Reset select
    if (categoryChipsRow) categoryChipsRow.querySelectorAll('.category-chip').forEach(ch => ch.classList.remove('active')); // Deselect all chips
    if (minInput) minInput.value = ''; // Reset floor price
    if (maxInput) maxInput.value = ''; // Reset ceiling price
    if (sortSelect) sortSelect.value = 'price-asc'; // Revert to default cheapest-first sort
    
    // Restoration step: Reset every product node to visible state
    allProducts.forEach(col => { if (col) col.style.display = ''; }); // Remove 'none' display
    updateActiveFilters('', '', '', NaN, NaN); // Wipe visual badges
  };

  // ----------------------
  // EVENT LISTENERS: Initialize reactive behavior
  // ----------------------
  collectStoresAndCategories(); // Build initial product index

  // URL Parameter Helper (Handles state when a page reload is required for deep data)
  const updateParamAndReload = (key, value) => { // URL sync
    const url = new URL(window.location.href); // Extract current state
    if (value) url.searchParams.set(key, value); // Apply new key
    else url.searchParams.delete(key); // Remove if empty
    url.searchParams.set('page', '1'); // Reset pagination to avoid index errors
    window.location.href = url.toString(); // Trigger server-side navigation
  };

  // Search Input Handler: Pressing Enter triggers a full page reload for server-side search
  // This ensures deep database queries are executed for results not present in current view.
  searchInput && searchInput.addEventListener('keydown', (e) => { // Text box
    if (e.key === 'Enter') { // Enter key?
      e.preventDefault(); // Stop form submit defaults
      updateParamAndReload('search', searchInput.value.trim()); // Navigate to results
    } 
  });
  
  // Search Button Handler: Clicking also triggers full server-side scan
  searchBtn && searchBtn.addEventListener('click', (e) => { // Click button
    e.preventDefault(); // Stop bubble
    updateParamAndReload('search', searchInput ? searchInput.value.trim() : ''); // Sync and reload
  });
  
  // Sidebar "Apply" Button: Executes high-speed Client-Side logic on the existing DOM
  applyBtn && applyBtn.addEventListener('click', (e) => { e.preventDefault(); applyFilters(); }); // Quick filter
  
  // Sidebar "Clear" Button: Hybrid logic to intelligently handle URL vs DOM clearing
  clearBtn && clearBtn.addEventListener('click', (e) => { // Mass reset
    e.preventDefault(); // Stop
    const url = new URL(window.location.href); // Check URL state
    // If the server has filtered the results (e.g. ?category=dairy), we MUST reload to see hidden items
    if (url.searchParams.has('category') || url.searchParams.has('search')) { // URL filtered?
      window.location.href = window.location.pathname; // strip params and reload
    } else { // Only client-side filters active?
      // Just clear the DOM states instantly without a page jump
      clearFilters(); // Instant wipe
    }
  });

  // Category Dropdown Change: Triggers server-side reload to fetch new category datasets
  categorySelect && categorySelect.addEventListener('change', () => { // Select change
    updateParamAndReload('category', categorySelect.value); // Reload with param
  });

  // Live filtering for Store, Price, and Sort changes (Instant UI Updates)
  storeFilter && storeFilter.addEventListener('change', () => { applyFilters(); }); 
  minInput && minInput.addEventListener('change', () => { applyFilters(); });
  maxInput && maxInput.addEventListener('change', () => { applyFilters(); });
  sortSelect && sortSelect.addEventListener('change', () => { applyFilters(); });
  
  // Chip Click Handler: Handles navigation when clicking horizontal scrolling category pills
  if (categoryChipsRow) { // Chip area found?
    categoryChipsRow.addEventListener('click', (e) => { // Track clicks
      const btn = e.target.closest('.category-chip'); // Identify clicked chip
      if (!btn) return; // Exit if background clicked
      const val = (btn.dataset.categoryChip || '').trim(); // Extract value
      updateParamAndReload('category', val); // Navigate to category
    });
  }
}

// Smooth-ish transition when paging compare results (fade grid, then navigate)
function setupPaginationSmoothTransition() { // UI Polish
  const grid = document.getElementById('products-grid'); // Main visual area
  if (!grid) return; // Skip if no products present
  const links = document.querySelectorAll('[data-pagination-link="true"]'); // Find page numbers
  if (!links.length) return; // Exit if no links

  links.forEach(link => { // Track every number link
    link.addEventListener('click', (e) => { // Track click
      const href = link.getAttribute('href'); // Target URL
      if (!href || href === '#') return; // Valid?
      e.preventDefault(); // Stop immediate jump
      grid.classList.add('fade-out'); // Trigger CSS opacity transition
      setTimeout(() => { window.location.href = href; }, 140); // Jump after animation frame
    });
  });
}
/**
 * ===============================================
 * HOME PAGE SEARCH: MIXED MODE
 * ===============================================
 * This complex function handles two different search paradigms:
 * 1. SERVER-SIDE SEARCH (Async Fetch): Used when typing in the main input to find new data.
 *    - Hits `/api/search-products` endpoint.
 *    - Renders entirely new HTML cards dynamically.
 * 2. CLIENT-SIDE FILTERING (DOM Manipulation): Used when clicking "Apply Filters" sidebar.
 *    - Iterates over existing DOM elements already rendered.
 *    - Toggles `display: none` for faster interaction.
 */

function setupCompareExperience() {
  const tray = document.getElementById('comparison-tray');
  if (!tray) return;

  const trayItemsEl = document.getElementById('comparison-tray-items');
  const openInsightsBtn = document.getElementById('tray-open-insights');
  const bestBasketBtn = document.getElementById('tray-best-basket');
  const clearBtn = document.getElementById('tray-clear');
  const compareBody = document.getElementById('compare-table-body');
  const bestBasketPanel = document.getElementById('best-basket-panel');
  const alertsPanel = document.getElementById('alerts-panel');

  const insightsModal = document.getElementById('compareInsightsModal');
  const alertModalEl = document.getElementById('priceAlertModal');
  const reportModalEl = document.getElementById('priceReportModal');

  const alertProductName = document.getElementById('alert-product-name');
  const alertTargetInput = document.getElementById('alert-target-price');
  const saveAlertBtn = document.getElementById('save-alert-btn');

  const reportProductName = document.getElementById('report-product-name');
  const reportStoreSelect = document.getElementById('report-store-select');
  const reportPriceInput = document.getElementById('report-price-input');
  const reportNoteInput = document.getElementById('report-note-input');
  const reportFeedback = document.getElementById('report-feedback');
  const submitReportBtn = document.getElementById('submit-report-btn');

  const bsInsightsModal = insightsModal ? bootstrap.Modal.getOrCreateInstance(insightsModal) : null;
  const bsAlertModal = alertModalEl ? bootstrap.Modal.getOrCreateInstance(alertModalEl) : null;
  const bsReportModal = reportModalEl ? bootstrap.Modal.getOrCreateInstance(reportModalEl) : null;

  const STORAGE_KEY = 'sg_compare_tray_v1';
  const ALERTS_KEY = 'sg_price_alerts_v1';

  let trayItems = [];
  let pendingAlertItem = null;
  let pendingReportItem = null;

  const escapeHtml = (value) => String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

  const renderStoreRowsFromPayload = (card, stores, bestPrice) => {
    const list = card.querySelector('.js-store-list');
    if (!list) return;

    const placeholder = '/static/placeholder.svg';
    const productImage = card.querySelector('.product-image')?.getAttribute('src') || placeholder;
    const rendered = [];

    (stores || []).forEach((storeNode) => {
      const storeName = String(storeNode.store || storeNode.name || '').trim();
      const price = Number(storeNode.price);
      if (!storeName || !Number.isFinite(price)) return;

      const isCheapest = Number.isFinite(bestPrice) && price === Number(bestPrice);
      const unitPrice = Number(storeNode.normalized_unit_price);
      const unitLabel = String(storeNode.normalized_unit_label || '').trim();
      const hasUnit = Number.isFinite(unitPrice) && unitLabel;
      const storeFallback = placeholder;
      const storeLogo = storeNode.logo || storeNode.store_image || storeFallback;
      const storeImage = storeNode.image || productImage;
      const storeUrl = String(storeNode.url || '').trim();

      rendered.push(`
        <div class="store-item" data-store-name="${escapeHtml(storeName)}"
          data-store-price="${price.toFixed(2)}"
          data-store-unit-price="${hasUnit ? unitPrice.toFixed(2) : ''}"
          data-store-unit-label="${escapeHtml(hasUnit ? unitLabel : '')}"
          data-image="${escapeHtml(storeImage)}">
          <div class="d-flex justify-content-between align-items-center gap-1">
            <div class="d-flex align-items-center gap-2 flex-grow-1" style="min-width:0;">
              <img src="${escapeHtml(storeLogo)}" alt="${escapeHtml(storeName)}"
                style="width: 24px; height: 24px; object-fit: contain; border-radius: 4px; background: white; padding: 2px; border: 1px solid #eee;"
                data-fallback-src="${escapeHtml(storeFallback)}"
                onerror="this.src=this.dataset.fallbackSrc">
              <div class="lh-sm overflow-hidden">
                <span class="fw-semibold text-truncate d-block" style="color: #7c3aed;">${escapeHtml(storeName)}</span>
              </div>
            </div>
            <div class="text-end d-flex align-items-center gap-2" style="min-width: 130px;">
              <div>
                <span class="text-success fw-bold fs-5 d-block price-main">
                  ${isCheapest
                    ? '<span class="star-slot"><i class="bi bi-star-fill" style="color: #ffc107;"></i></span>'
                    : '<span class="star-slot empty"><i class="bi bi-star-fill"></i></span>'}
                  €${price.toFixed(2)}
                </span>
                <small class="text-muted js-store-unit-price" ${hasUnit ? '' : 'style="display:none;"'}>${hasUnit ? `(${escapeHtml(unitLabel)}: €${unitPrice.toFixed(2)})` : ''}</small>
              </div>
              ${storeUrl ? `<a href="${escapeHtml(storeUrl)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-go-store p-1" title="Go to official store" style="background: #f0f0ff; border-radius: 6px; color: #7c3aed; border: 1px solid #dadaff; line-height: 1;"><i class="bi bi-box-arrow-up-right" style="font-size: 0.85rem;"></i></a>` : ''}
            </div>
          </div>
        </div>
      `);
    });

    if (rendered.length) {
      list.innerHTML = rendered.join('');
    }
  };

  const hydrateCompareCardsFromApi = async () => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('legacyCompare') === '1') return;

    const cards = Array.from(document.querySelectorAll('.product-card[data-product-id]'));
    if (!cards.length) return;

    const params = new URLSearchParams(window.location.search);
    const query = new URLSearchParams({
      page: params.get('page') || '1',
      per_page: String(cards.length),
      category: params.get('category') || '',
      search: params.get('search') || '',
    });

    try {
      const res = await fetch(`/api/compare/list?${query.toString()}`, { credentials: 'same-origin' });
      if (!res.ok) return;
      const data = await res.json();
      const products = Array.isArray(data.products) ? data.products : [];
      if (!products.length) return;

      const byId = new Map(products.map((p) => [String(p.id || ''), p]));

      cards.forEach((card) => {
        const id = String(card.getAttribute('data-product-id') || '');
        const payload = byId.get(id);
        if (!payload) return;

        const cheapest = payload.cheapest || {};
        const bestPrice = Number.isFinite(Number(cheapest.price)) ? Number(cheapest.price) : Number(payload.price);
        if (Number.isFinite(bestPrice)) {
          card.setAttribute('data-price', String(bestPrice));
        }

        const storesJson = JSON.stringify(payload.stores || []);
        card.setAttribute('data-stores', storesJson);

        const priceNode = card.querySelector('.js-compare-price');
        if (priceNode && Number.isFinite(bestPrice)) {
          priceNode.textContent = bestPrice.toFixed(2);
        }

        const reportCount = Number(payload.community_report_count || 0);
        const storesCount = Array.isArray(payload.stores) ? payload.stores.length : 0;
        const confidenceLabel = ((payload.confidence || {}).label || 'Unknown').toLowerCase();
        let statusText = 'Estimated';
        if (reportCount > 0) statusText = `Community Reported (${reportCount})`;
        else if (confidenceLabel === 'high confidence') statusText = 'Confirmed';

        const priceStatusNode = card.querySelector('.js-price-status');
        if (priceStatusNode) {
          priceStatusNode.innerHTML = `<i class="bi bi-shield-check"></i> Price: ${statusText}`;
        }

        const storeCountNode = card.querySelector('.js-store-count');
        if (storeCountNode) {
          storeCountNode.innerHTML = `<i class="bi bi-shop"></i> ${storesCount} store${storesCount === 1 ? '' : 's'}`;
          storeCountNode.setAttribute('data-store-count', String(storesCount));
        }

        renderStoreRowsFromPayload(card, payload.stores || [], bestPrice);

        const addBtn = card.querySelector('.btn-premium-add');
        if (addBtn && Number.isFinite(bestPrice)) {
          addBtn.setAttribute('data-price', String(bestPrice));
          addBtn.setAttribute('data-initial-price', String(bestPrice));
        }

        const compareBtn = card.querySelector('.btn-add-compare');
        if (compareBtn) {
          compareBtn.setAttribute('data-product-stores', storesJson);
          if (Number.isFinite(bestPrice)) compareBtn.setAttribute('data-product-price', String(bestPrice));
          if (payload.normalized_unit_price !== null && payload.normalized_unit_price !== undefined) {
            compareBtn.setAttribute('data-product-unit-price', String(payload.normalized_unit_price));
          }
          compareBtn.setAttribute('data-product-unit-label', payload.normalized_unit_label || '');
          compareBtn.setAttribute('data-product-confidence', (payload.confidence || {}).label || 'Unknown');
        }

        const alertBtn = card.querySelector('.btn-set-alert');
        if (alertBtn && Number.isFinite(bestPrice)) {
          alertBtn.setAttribute('data-product-price', String(bestPrice));
        }

        const reportBtn = card.querySelector('.btn-report-price');
        if (reportBtn) {
          reportBtn.setAttribute('data-product-stores', storesJson);
        }
      });
    } catch (_) {
      // Silent fallback to server-rendered data.
    }
  };

  const parseNum = (v) => {
    const n = Number(String(v || '').replace(/[^0-9.\-]/g, ''));
    return Number.isFinite(n) ? n : null;
  };

  const readJSON = (raw, fallback) => {
    try { return JSON.parse(raw); } catch (_) { return fallback; }
  };

  const loadTray = () => {
    trayItems = readJSON(localStorage.getItem(STORAGE_KEY) || '[]', []);
    if (!Array.isArray(trayItems)) trayItems = [];
    trayItems = trayItems.slice(0, 4);
  };

  const saveTray = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(trayItems));
  };

  const getCurrentCardPriceMap = () => {
    const map = {};
    document.querySelectorAll('.product-card[data-product-id]').forEach((card) => {
      const pid = card.getAttribute('data-product-id');
      const price = parseNum(card.getAttribute('data-price'));
      if (pid && price !== null) map[pid] = price;
    });
    return map;
  };

  const renderTray = () => {
    const currentPrices = getCurrentCardPriceMap();
    trayItemsEl.innerHTML = '';

    trayItems.forEach((item) => {
      const current = currentPrices[item.id] ?? item.price;
      const node = document.createElement('div');
      node.className = 'tray-item';
      node.innerHTML = `
        <button type="button" class="btn-close btn-close-white position-absolute top-0 end-0 m-2 remove-tray-item" data-id="${item.id}" aria-label="Remove"></button>
        <div class="tray-item-title mb-1">${item.name}</div>
        <div class="small">Best: <strong>EUR ${Number(current || 0).toFixed(2)}</strong></div>
        <div class="small opacity-75">${item.unitPrice !== null ? `Unit EUR ${Number(item.unitPrice).toFixed(2)} ${item.unitLabel || ''}` : 'Unit n/a'}</div>
      `;
      trayItemsEl.appendChild(node);
    });

    tray.classList.toggle('active', trayItems.length > 0);
  };

  const refreshCompareButtons = () => {
    const ids = new Set(trayItems.map((x) => x.id));
    document.querySelectorAll('.btn-add-compare').forEach((btn) => {
      const id = btn.getAttribute('data-product-id');
      const active = ids.has(id);
      btn.classList.toggle('active', active);
      btn.innerHTML = active ? '<i class="bi bi-check2-circle"></i> Added' : '<i class="bi bi-columns-gap"></i> Compare';
    });
  };

  const upsertTrayItem = (item) => {
    const idx = trayItems.findIndex((x) => x.id === item.id);
    if (idx >= 0) {
      trayItems.splice(idx, 1);
    } else {
      if (trayItems.length >= 4) trayItems.shift();
      trayItems.push(item);
    }
    saveTray();
    renderTray();
    refreshCompareButtons();
  };

  const renderCompareTable = () => {
    compareBody.innerHTML = '';
    trayItems.forEach((item) => {
      let cheapestStore = '-';
      let cheapest = null;
      (item.stores || []).forEach((s) => {
        const p = parseNum(s.price);
        if (p !== null && (cheapest === null || p < cheapest)) {
          cheapest = p;
          cheapestStore = s.store || s.name || '-';
        }
      });

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><div class="fw-semibold">${item.name}</div></td>
        <td>${cheapest !== null ? `EUR ${cheapest.toFixed(2)}` : 'n/a'}</td>
        <td>${item.unitPrice !== null ? `EUR ${Number(item.unitPrice).toFixed(2)} ${item.unitLabel || ''}` : 'n/a'}</td>
        <td>${item.confidence || 'Unknown'}</td>
        <td>${cheapestStore}</td>
      `;
      compareBody.appendChild(tr);
    });

    if (!trayItems.length) {
      compareBody.innerHTML = '<tr><td colspan="5" class="text-muted">Add up to 4 products to compare.</td></tr>';
    }
  };

  const computeBestBasket = () => {
    if (!trayItems.length) {
      bestBasketPanel.innerHTML = '<p class="text-muted mb-0">Add products to the tray to compute the basket.</p>';
      return Promise.resolve();
    }

    const productIds = trayItems.map((x) => x.id).filter(Boolean);
    return fetch('/api/compare/best-basket', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ product_ids: productIds }),
    })
      .then(async (res) => {
        if (!res.ok) throw new Error('Failed best basket request');
        const data = await res.json();

        const options = Array.isArray(data.single_store_options) ? data.single_store_options : [];
        const mixed = data.mixed || { total: 0, breakdown: [] };

        let html = `
          <div class="card border-0 shadow-sm mb-3">
            <div class="card-body">
              <h6 class="fw-bold mb-2">Mixed-store optimum</h6>
              <p class="mb-2 text-muted">Best store selected per product.</p>
              <div class="fw-bold fs-5 mb-2">Total: EUR ${Number(mixed.total || 0).toFixed(2)}</div>
            </div>
          </div>
        `;

        if (!options.length) {
          html += '<div class="alert alert-info">No single store currently covers all selected products.</div>';
          bestBasketPanel.innerHTML = html;
          return;
        }

        const bestTotal = Number(options[0].total || 0);
        html += `
          <div class="card border-0 shadow-sm">
            <div class="card-body">
              <h6 class="fw-bold mb-3">Single-store basket ranking</h6>
              <div class="table-responsive">
                <table class="table table-striped align-middle mb-0">
                  <thead><tr><th>Store</th><th>Basket Price</th><th>Savings</th></tr></thead>
                  <tbody>
                    ${options.slice(0, 8).map((row, idx) => {
                      const total = Number(row.total || 0);
                      const savings = total - bestTotal;
                      const savingsText = idx === 0 ? 'BEST' : `+EUR ${savings.toFixed(2)}`;
                      const savingsClass = idx === 0 ? 'badge bg-success' : 'text-muted';
                      return `<tr><td><strong>${row.store}</strong></td><td>EUR ${total.toFixed(2)}</td><td><span class="${savingsClass}">${savingsText}</span></td></tr>`;
                    }).join('')}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        `;
        bestBasketPanel.innerHTML = html;
      })
      .catch(() => {
        bestBasketPanel.innerHTML = '<div class="alert alert-warning">Could not compute best basket right now. Try again in a moment.</div>';
      });
  };

  const getAlerts = () => readJSON(localStorage.getItem(ALERTS_KEY) || '[]', []);
  const saveAlerts = (alerts) => localStorage.setItem(ALERTS_KEY, JSON.stringify(alerts));

  const renderAlertsPanel = () => {
    const alerts = getAlerts();
    if (!alerts.length) {
      alertsPanel.innerHTML = '<p class="text-muted mb-0">No alerts yet. Use the Alert button on any card.</p>';
      return;
    }
    alertsPanel.innerHTML = `
      <div class="list-group">${alerts.map((a) => `
        <div class="list-group-item d-flex justify-content-between align-items-center">
          <div>
            <div class="fw-semibold">${a.name}</div>
            <small class="text-muted">Target: EUR ${Number(a.target).toFixed(2)}</small>
          </div>
          <button class="btn btn-sm btn-outline-danger remove-alert" data-id="${a.id}">Remove</button>
        </div>`).join('')}
      </div>
    `;
  };

  const checkTriggeredAlerts = () => {
    const alerts = getAlerts();
    if (!alerts.length) return;
    const currentMap = getCurrentCardPriceMap();
    const triggered = alerts.filter((a) => currentMap[a.id] !== undefined && currentMap[a.id] <= a.target);
    if (!triggered.length) return;

    const holderId = 'compare-alert-toast-holder';
    let holder = document.getElementById(holderId);
    if (!holder) {
      holder = document.createElement('div');
      holder.id = holderId;
      holder.className = 'toast-container position-fixed top-0 end-0 p-3';
      holder.style.zIndex = '1100';
      document.body.appendChild(holder);
    }

    triggered.forEach((t) => {
      const div = document.createElement('div');
      div.className = 'toast align-items-center text-bg-success border-0';
      div.setAttribute('role', 'status');
      div.innerHTML = `<div class="d-flex"><div class="toast-body"><strong>${t.name}</strong> reached your alert target.</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
      holder.appendChild(div);
      bootstrap.Toast.getOrCreateInstance(div, { delay: 4500 }).show();
    });
  };

  document.addEventListener('click', (e) => {
    const compareBtn = e.target.closest('.btn-add-compare');
    if (compareBtn) {
      e.preventDefault();
      const stores = readJSON(compareBtn.getAttribute('data-product-stores') || '[]', []);
      const item = {
        id: compareBtn.getAttribute('data-product-id'),
        name: compareBtn.getAttribute('data-product-name') || 'Product',
        price: parseNum(compareBtn.getAttribute('data-product-price')) || 0,
        unitPrice: parseNum(compareBtn.getAttribute('data-product-unit-price')),
        unitLabel: compareBtn.getAttribute('data-product-unit-label') || '',
        confidence: compareBtn.getAttribute('data-product-confidence') || 'Unknown',
        image: compareBtn.getAttribute('data-product-image') || '',
        stores,
      };
      if (item.id) upsertTrayItem(item);
      return;
    }

    const removeTrayBtn = e.target.closest('.remove-tray-item');
    if (removeTrayBtn) {
      const id = removeTrayBtn.getAttribute('data-id');
      trayItems = trayItems.filter((x) => x.id !== id);
      saveTray();
      renderTray();
      refreshCompareButtons();
      return;
    }

    const alertBtn = e.target.closest('.btn-set-alert');
    if (alertBtn) {
      pendingAlertItem = {
        id: alertBtn.getAttribute('data-product-id'),
        name: alertBtn.getAttribute('data-product-name') || 'Product',
        current: parseNum(alertBtn.getAttribute('data-product-price')) || 0,
      };
      alertProductName.textContent = `${pendingAlertItem.name} current best: EUR ${pendingAlertItem.current.toFixed(2)}`;
      alertTargetInput.value = pendingAlertItem.current > 0 ? Math.max(0.01, pendingAlertItem.current - 0.2).toFixed(2) : '';
      bsAlertModal && bsAlertModal.show();
      return;
    }

    const reportBtn = e.target.closest('.btn-report-price');
    if (reportBtn) {
      pendingReportItem = {
        id: reportBtn.getAttribute('data-product-id'),
        name: reportBtn.getAttribute('data-product-name') || 'Product',
        stores: readJSON(reportBtn.getAttribute('data-product-stores') || '[]', []),
      };
      reportProductName.textContent = pendingReportItem.name;
      reportFeedback.textContent = '';
      reportPriceInput.value = '';
      reportNoteInput.value = '';
      reportStoreSelect.innerHTML = '';
      const seen = new Set();
      pendingReportItem.stores.forEach((s) => {
        const name = (s.store || s.name || '').trim();
        if (!name || seen.has(name.toLowerCase())) return;
        seen.add(name.toLowerCase());
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        reportStoreSelect.appendChild(opt);
      });
      if (!reportStoreSelect.options.length) {
        const opt = document.createElement('option');
        opt.value = 'Unknown Store';
        opt.textContent = 'Unknown Store';
        reportStoreSelect.appendChild(opt);
      }
      bsReportModal && bsReportModal.show();
      return;
    }

    const removeAlertBtn = e.target.closest('.remove-alert');
    if (removeAlertBtn) {
      const id = removeAlertBtn.getAttribute('data-id');
      const next = getAlerts().filter((a) => a.id !== id);
      saveAlerts(next);
      renderAlertsPanel();
    }
  });

  saveAlertBtn && saveAlertBtn.addEventListener('click', () => {
    if (!pendingAlertItem) return;
    const target = parseNum(alertTargetInput.value);
    if (target === null || target <= 0) return;

    const alerts = getAlerts();
    const idx = alerts.findIndex((a) => a.id === pendingAlertItem.id);
    const record = {
      id: pendingAlertItem.id,
      name: pendingAlertItem.name,
      target: Number(target.toFixed(2)),
      created_at: new Date().toISOString(),
    };
    if (idx >= 0) alerts[idx] = record;
    else alerts.push(record);
    saveAlerts(alerts);
    renderAlertsPanel();
    bsAlertModal && bsAlertModal.hide();
  });

  submitReportBtn && submitReportBtn.addEventListener('click', async () => {
    if (!pendingReportItem) return;
    const observed_price = parseNum(reportPriceInput.value);
    if (observed_price === null || observed_price <= 0) {
      reportFeedback.textContent = 'Enter a valid price.';
      reportFeedback.className = 'text-danger d-block mt-2';
      return;
    }

    const payload = {
      product_id: pendingReportItem.id,
      store_name: reportStoreSelect.value,
      observed_price,
      note: (reportNoteInput.value || '').trim(),
    };

    try {
      submitReportBtn.disabled = true;
      const res = await fetch('/api/community-price-report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        reportFeedback.textContent = data.error || 'Failed to submit report.';
        reportFeedback.className = 'text-danger d-block mt-2';
      } else {
        reportFeedback.textContent = 'Thanks, your report was submitted.';
        reportFeedback.className = 'text-success d-block mt-2';
      }
    } catch (_) {
      reportFeedback.textContent = 'Network error while submitting report.';
      reportFeedback.className = 'text-danger d-block mt-2';
    } finally {
      submitReportBtn.disabled = false;
    }
  });

  openInsightsBtn && openInsightsBtn.addEventListener('click', async () => {
    renderCompareTable();
    await computeBestBasket();
    renderAlertsPanel();
    bsInsightsModal && bsInsightsModal.show();
  });

  bestBasketBtn && bestBasketBtn.addEventListener('click', async () => {
    await computeBestBasket();
    bsInsightsModal && bsInsightsModal.show();
    const tabBtn = document.querySelector('[data-bs-target="#tab-basket"]');
    tabBtn && bootstrap.Tab.getOrCreateInstance(tabBtn).show();
  });

  clearBtn && clearBtn.addEventListener('click', () => {
    trayItems = [];
    saveTray();
    renderTray();
    refreshCompareButtons();
  });

  const boot = async () => {
    await hydrateCompareCardsFromApi();
    loadTray();
    renderTray();
    refreshCompareButtons();
    renderAlertsPanel();
    checkTriggeredAlerts();
  };

  boot();
}
