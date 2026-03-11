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
