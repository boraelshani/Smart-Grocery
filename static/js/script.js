// ===============================================
// SMART GROCERY FRONTEND JAVASCRIPT
// Handles user interactions: shopping lists, favorites, filtering, search
// ===============================================

/**
 * MAIN ENTRY POINT
 * We use 'DOMContentLoaded' to ensure all HTML elements are loaded before running any scripts.
 * This prevents "element not found" errors.
 */
document.addEventListener('DOMContentLoaded', () => { // Page ready event
  // INITIALIZE: Run all setup functions when page loads
  initializeBootstrapComponents();    // Enable Bootstrap tooltips/popovers globally
  setupNavbarScroll();                // Change navbar visibility based on page scroll
  setupSearchFunctionality();         // Initialize the search bar logic
  setupShoppingListHandlers();        // Link "Add to List" buttons to backend APIs
  setupShoppingListInteractions();    // Enable checkbox/purchased toggling in list view
  setupClaimButtons();                // Initialize "Claim Deal" logic for featured items
  setupProductModalHandlers();        // Ensure modal state is reset on close events
  setupStoreSuggestions();            // Enable AJAX autocomplete for store input fields
  setupProfileEditHandlers();         // Toggle visibility for user profile edit forms
  setupFeaturedDealsSearch();         // Initialize filtering for the deals dashboard
  setupCompareHandlers();             // Enable price sorting on the comparison grid
  setupCompareFilters();              // Initialize hybrid (client+server) filtering
  setupPaginationSmoothTransition();  // (Optional) Soft loading for paginated views
  setupLogoutConfirmation();          // Hijack logout links to show confirmation modal
  setupStoreSelection();              // Initialize store-specific pricing logic on cards

  // Always hide product modal on page load (prevents unwanted popup loops on creating new items)
  // This is a safety cleanup for stale modal states in the browser cache.
  const productModalEl = document.getElementById('productModal'); // Find modal by ID
  if (productModalEl) { // Check if it exists in current view
    const modalInstance = bootstrap.Modal.getOrCreateInstance(productModalEl); // Get wrapper
    modalInstance.hide(); // Force closure
  }
});

// EVENT LISTENER: BROWSER BACK BUTTON
// Hide product modal on browser back navigation (prevents unwanted popup staying open)
window.addEventListener('pageshow', function (event) { // Triggered on navigation
  const productModalEl = document.getElementById('productModal'); // Grab reference
  if (productModalEl) { // Verify element presence
    const modalInstance = bootstrap.Modal.getOrCreateInstance(productModalEl); // Instantiate
    modalInstance.hide(); // Clear visual overlay
  }
});

/**
 * NAVBAR SCROLL EFFECT
 * Adds a '.scrolled' CSS class to the navbar when the user scrolls down > 50px.
 * This allows us to change transparency/shadow via CSS.
 */
function setupNavbarScroll() { // Visibility handler
  const nav = document.querySelector('.navbar-premium'); // Locate premium navbar component
  if (!nav) return; // Exit silently if navbar is missing (e.g., error pages)

  const handleScroll = () => { // Animation logic
    // Check vertical scroll position (Y-axis) relative to top of viewport
    if (window.scrollY > 50) { // Threshold for effect
      nav.classList.add('scrolled'); // Apply background and border styles
    } else { // Return to top position
      nav.classList.remove('scrolled'); // Restore original transparency
    }
  };

  // Attach listener to window scroll event for reactive updates
  window.addEventListener('scroll', handleScroll); // Listen to motion
  handleScroll(); // Execute once on load to catch pre-scrolled pages
}

// BOOTSTRAP: Activate tooltip popovers
// Bootstrap 5 requires manual initialization of tooltips (hover text)
function initializeBootstrapComponents() { // Feature activation
  // Select all DOM elements that have the custom tooltip data attribute
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]')); // Convert to array
  // Initialize a new Bootstrap Tooltip class for every matched element
  tooltipTriggerList.map(function (tooltipTriggerEl) { return new bootstrap.Tooltip(tooltipTriggerEl); }); // Map creation
}

/**
 * LOGOUT CONFIRMATION INTERCEPTOR
 * Intercepts any click on a logout link and shows a custom confirmation modal
 * instead of immediately navigating away.
 */
function setupLogoutConfirmation() { // UX safety feature
  // EVENT DELEGATION / CAPTURE PHASE
  // We listen on the 'document' for clicks, using 'true' for the capture phase.
  // This lets us intercept the event *before* it reaches the target link.
  document.addEventListener('click', (e) => { // Global click listener
    // EXCEPTION: If the user clicks inside the modal itself (e.g. "Yes" or "No"),
    // don't interfere with the modal's internal logic.
    if (e.target.closest('#customLogoutModal')) { // Nested check
      return; // Handled by Bootstrap
    }

    // Check if the clicked element (or its parent) is an anchor tag linking to "/logout"
    const logoutBtn = e.target.closest('a[href*="/logout"]'); // Pattern match
    if (logoutBtn) { // Found a logout trigger?
      // PROACTIVELY STOP EVERYTHING
      e.preventDefault();         // Halt navigation to the /logout route
      e.stopPropagation();        // Stop event bubbles to other handlers
      e.stopImmediatePropagation(); // Ensure no other scripts fire on this click
      
      // Show our custom UI confirmation instead of immediate logout
      showLogoutModal(logoutBtn.href); // Trigger modal with original target URL
      return false; // Final safeguard
    }
  }, true); // Use capture phase for high priority insertion
}

/**
 * Dynamically creates and injects the Logout Modal into the DOM if it's missing.
 * This uses a "Lazy Load" pattern - we don't clutter the initial HTML with this modal.
 * 
 * @param {string} logoutUrl - The URL to go to if the user confirms "Yes".
 */
function showLogoutModal(logoutUrl) { // UI Generator
  // Check if modal DOM element already exists in the current document
  let modalElem = document.getElementById('customLogoutModal'); // Tag lookup
  
  // LAZY CREATION: Only create the HTML structure the first time it's needed during the session.
  if (!modalElem) { // First time trigger?
    // Template Literal defining the Modal HTML with Bootstrap classes and custom styling
    const modalHtml = `
      <div class="modal fade" id="customLogoutModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered modal-sm">
          <div class="modal-content border-0 shadow-lg" style="border-radius: 20px;">
            <div class="modal-body text-center p-4">
              <div class="mb-3">
                <!-- Visual Icon with branding color -->
                <i class="bi bi-door-open text-danger" style="font-size: 3rem;"></i>
              </div>
              <h5 class="fw-bold mb-2">Wait! Logging out?</h5>
              <p class="text-muted small mb-4">Are you sure you want to end your session?</p>
              <div class="d-grid gap-2">
                <!-- "Yes" button acts as the original link redirecting to the server endpoint -->
                <a href="${logoutUrl}" class="btn btn-danger rounded-pill fw-bold py-2">Yes, Log Out</a>
                <!-- "No" button dismisses modal via data-bs attributes -->
                <button type="button" class="btn btn-light rounded-pill fw-semibold py-2" data-bs-dismiss="modal">Stay Logged In</button>
              </div>
            </div>
          </div>
        </div>
      </div>`;
    // Append the modal string to the end of the body to make it part of the DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml); // Live injection
    modalElem = document.getElementById('customLogoutModal'); // Cache reference
  } else { // Modal already exists?
    // Update the confirmation URL dynamically to handle different logout scenarios if they exist
    const confirmBtn = modalElem.querySelector('a.btn-danger'); // Find trigger
    if (confirmBtn) confirmBtn.href = logoutUrl; // Sync URL
  }

  // Use Bootstrap's JavaScript API to show the modal programmatically by passing the DOM node
  const modal = new bootstrap.Modal(modalElem); // Instantiate JS wrapper
  modal.show(); // Trigger visibility
}

// Compare page: sort the rendered store list items by numeric price (client-side)
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
function setupSearchFunctionality() { // Search hub
  // DOM ELEMENT REFERENCES: Cache pointers for interaction
  // ----------------------
  const input = document.getElementById('home-search-input'); // Main text box
  const btn = document.getElementById('home-search-btn'); // Primary search button
  const resultsSection = document.getElementById('search-results-section'); // Async results container
  const resultsContainer = document.getElementById('search-results'); // Grid slot for async items
  const productsGrid = document.getElementById('products-grid'); // Original static SSR products
  
  // High-performance Sidebar filter components
  const applyFiltersBtn = document.getElementById('apply-filters'); // Trigger
  const clearFiltersBtn = document.getElementById('clear-filters'); // Reset
  const storeFilter = document.getElementById('store-filter'); // Dropdown
  const minPrice = document.getElementById('min-price'); // Number input
  const maxPrice = document.getElementById('max-price'); // Number input
  const sortOrder = document.getElementById('sort-order'); // Sort select

  let allProducts = []; // Memory cache for SSR items

  /**
   * SNAPSHOT INITIAL STATE
   * We grab a reference to all originally rendered product cards on page load.
   * This allows us to "Restore" the view when filters are cleared without reloading.
   */
  const collectAllProducts = () => { // Initial scan
    if (!productsGrid) return; // Exit if grid isn't on this page
    // Select all Bootstrap columns that contain cards and convert to native Array
    allProducts = Array.from(productsGrid.querySelectorAll('[class*="col"]')); // Snapshot
  };

  /**
   * ASYNC SEARCH HANDLER
   * Triggered by: Main Search Button or Enter Key
   * Action: Fetches JSON from API -> Sanitizes -> Renders new HTML snippets
   */
  async function doSearch() { // Network search
    if (!input) return; // Guard
    
    // 1. Validation Logic
    const q = input.value.trim(); // Cleanup string
    if (!q) { // Empty query?
      showNotification('Please enter a search term', 'info'); // UI Warning
      return; // Stop
    }

    try { // Network safety
      // 2. Network Request: Call internal Flask API for broad database search
      // We use 'same-origin' to ensure cookies/session info is passed if needed
      const res = await fetch(`/api/search-products?q=${encodeURIComponent(q)}`, { credentials: 'same-origin' });
      const data = await res.json().catch(() => ({})); // Parse body
      const items = data.items || []; // Extract items array

      // 3. Render Setup: Locate slots
      if (!resultsSection || !resultsContainer) return; // Page logic check
      resultsContainer.innerHTML = ''; // Clear previous searches

      // 4. Empty State Handler: Feedback for zero results
      if (!items.length) { // No items?
        resultsContainer.innerHTML = `<div class="col-12"><p class="text-muted">No matching products found.</p></div>`;
        resultsSection.style.display = 'block'; // Show empty msg
        return; // Exit
      }

      // 5. Result Rendering Loop: Manual template injection
      // Converts raw JSON objects into responsive Bootstrap Card structures
      items.forEach(it => { // iterate results
        // Data Normalization (Handle missing or nested fields safely)
        const title = it.name || it.title || ''; // Handle naming variations
        const price = it.price || (it.cheapest && it.cheapest.price) || ''; // Get best price
        const img = it.image || (it.images && it.images[0]) || 'https://via.placeholder.com/300x200'; // asset fallback
        const store = (it.stores && it.stores[0] && it.stores[0].store) || ''; // Primary store
        const id = it.id || title; // Identifier

        // Create Container Column for grid layout
        const col = document.createElement('div'); // Create wrapper
        col.className = 'col-md-6 col-lg-4'; // Apply grid breakpoints

        // Template Literal: Building the product card string
        col.innerHTML = `
          <div class="card shadow-sm h-100">
            <!-- Product Thumbnail Slot -->
            <img src="${img}" class="card-img-top product-thumb" alt="${escapeHtml(title)}">
            
            <div class="card-body d-flex flex-column">
              <h5 class="card-title">${escapeHtml(title)}</h5>
              <p class="card-text mb-1 badge bg-light text-dark align-self-start border">${escapeHtml(store)}</p>
              <p class="card-text text-primary fw-bold mb-3">${escapeHtml(price)}</p>
              
              <!-- Action Buttons (Positioned at bottom via flex-grow logic) -->
              <div class="mt-auto d-flex gap-2">
                <!-- Details Trigger: Hydrates the product modal -->
                <button class="btn btn-sm btn-info text-white view-details-btn" 
                        data-bs-toggle="modal" 
                        data-bs-target="#productModal" 
                        data-title="${escapeHtml(title)}" 
                        data-price="${escapeHtml(price)}" 
                        data-store="${escapeHtml(store)}" 
                        data-image="${escapeHtml(img)}">
                  <i class="bi bi-eye"></i> View Details
                </button>
                
                <!-- Add to List Trigger: Links to User List logic -->
                <button class="btn btn-sm btn-primary add-to-list-btn" 
                        data-id="${escapeHtml(id)}" 
                        data-name="${escapeHtml(title)}" 
                        data-price="${escapeHtml(price)}" 
                        data-image="${escapeHtml(img)}" 
                        data-store="${escapeHtml(store)}">
                  <i class="bi bi-plus-lg"></i> Add
                </button>
              </div>
            </div>
          </div>
        `;
        resultsContainer.appendChild(col); // Inject into DOM
      });

      // 6. View State Transition: Swap visible grids
      resultsSection.style.display = 'block'; // Reveal dynamic results
      if (productsGrid) productsGrid.style.display = 'none'; // Hide static items

      // 7. Event Re-binding (Critical)
      // Since we injected new HTML, previously bound event listeners are lost.
      // This helper re-scans the DOM to ensure buttons react to clicks.
      try { setupProductModalHandlers(); } catch (e) { } // Refresh listeners

    } catch (err) { // Handle failure
      console.error(err); // Log trace
      showNotification('Search failed due to a network error.', 'danger'); // User feedback
    }
  }

  /**
   * CLIENT-SIDE FILTERING LOGIC
   * Operates on the "allProducts" snapshot of the original SSR grid.
   * Note: The typo "applyHomFilters" is preserved from original source.
   */
  const applyHomFilters = () => { // Sidebar filter handler
    if (!productsGrid) return; // Guard

    // 1. Gather Criteria and Parse Types
    const minVal = minPrice ? parseFloat(minPrice.value) : NaN; // Low bound
    const maxVal = maxPrice ? parseFloat(maxPrice.value) : NaN; // High bound
    const sortVal = sortOrder ? sortOrder.value : 'price-asc'; // Selection
    
    // Robust Price Parser (Handles currency symbols and non-numeric garbage)
    const parsePrice = (v) => { // cleanup function
      const n = Number(String(v || '').replace(/[^0-9.\-]/g, '')); // Regex strip
      return isNaN(n) ? 0 : n; // Force zero if empty
    };

    const visible = []; // Collector for items that pass predicate tests

    // 2. Evaluation Loop: Iterate through the cached SSR elements
    allProducts.forEach(col => { // check every card
      if (!col) return; // skip nulls
      const card = col.querySelector('.card'); // drill to card
      if (!card) return; // skip if no card ui

      // Extract Data from DOM Attributes (fast) or Text Content (slow backup)
      // data-price attribute is preferred for precision
      const priceText = card.getAttribute('data-price') || card.querySelector('[class*="price"]')?.textContent || '0';
      const price = parsePrice(priceText); // Convert to number

      // Predicate: Does it match price range?
      let priceMatch = true; // initial state
      if (!isNaN(minVal)) priceMatch = priceMatch && (price >= minVal); // Floor check
      if (!isNaN(maxVal)) priceMatch = priceMatch && (price <= maxVal); // Ceiling check

      // 3. Layout Update: Toggle visibility based on matching logic
      if (priceMatch) { // Matches criteria?
        col.style.display = ''; // Show (reset to default display)
        // Extract name for alphabetical sorting
        const name = (card.getAttribute('data-name') || card.querySelector('.card-title')?.textContent || '').toLowerCase();
        visible.push({ col, price, name }); // Store reference and metadata
      } else {
        col.style.display = 'none'; // Hide (Remove from visual flow)
      }
    });

    // 4. Sorting Logic: Re-order the 'visible' array
    if (visible.length) { // Only sort if we have items
      if (sortVal === 'price-asc' || sortVal === 'price-desc') { // Numerical sort
        visible.sort((a, b) => sortVal === 'price-asc' ? a.price - b.price : b.price - a.price);
      } else if (sortVal === 'name-asc' || sortVal === 'name-desc') { // String sort
        visible.sort((a, b) => sortVal === 'name-asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name));
      }
      
      // 5. DOM Reordering
      // Logic: appendChild moves an existing node rather than cloning it, 
      // thus preserving event listeners and internal state automatically.
      visible.forEach(v => productsGrid.appendChild(v.col)); // Re-inject in order
    }
  };

  /**
   * RESET HANDLER
   * Restores input fields and visual grid state to default values.
   */
  const clearHomeFilters = () => { // Global reset
    if (minPrice) minPrice.value = ''; // Reset price floor
    if (maxPrice) maxPrice.value = ''; // Reset price ceiling
    if (sortOrder) sortOrder.value = 'price-asc'; // Default sort
    if (storeFilter) storeFilter.value = ''; // Reset store dropdown
    if (input) input.value = ''; // Reset global search box

    // Show all originally cached products
    allProducts.forEach(col => { if (col) col.style.display = ''; });
    
    // View State management: Hide dynamic results, show the main static grid
    if (resultsSection) resultsSection.style.display = 'none';
    if (productsGrid) productsGrid.style.display = '';
  };

  // ----------------------
  // EVENT BINDINGS: SEARCH/FILTER HUB
  // ----------------------
  // Run startup routine to cache the cards
  collectAllProducts();

  // Bind Search Actions: Listen for clicks or keyboard events
  if (btn) btn.addEventListener('click', doSearch); // Button click
  if (input) input.addEventListener('keydown', (e) => { // Keyboard monitor
    if (e.key === 'Enter') { // Enter key pressed?
      e.preventDefault(); // Stop form submission
      doSearch(); // Execute async network search
    } 
  });

  // Bind Sidebar Actions: Filter application and clearing
  if (applyFiltersBtn) applyFiltersBtn.addEventListener('click', (e) => { // Filter btn
    e.preventDefault(); // Stop navigation
    applyHomFilters(); // Run DOM filter logic
  });
  if (clearFiltersBtn) clearFiltersBtn.addEventListener('click', (e) => { // Clear btn
    e.preventDefault(); // Stop navigation
    clearHomeFilters(); // Restore defaults
  });
}

/**
 * NO-OPERATION
 * Placeholder function for callbacks that require an executable but don't need logic.
 */
function noop() { }

/**
 * ===============================================
 * STORE SUGGESTIONS / STORE FINDER LOGIC
 * ===============================================
 * Handles interactivity for the "Stores" page where users browse retailers.
 * 1. SIDEBAR FILTERING: Real-time text filter for the store list buttons.
 * 2. SYNC LOAD: Updates UI state (titles, icons) on selection.
 * 3. ASYNC HYDRATION: Fetches and renders product/deal JSON for the selected store.
 */
function setupStoreSuggestions() { // Store hub
  // DOM ELEMENT REFERENCES: Local page layout
  // ----------------------
  const input = document.getElementById('stores-search-input'); // Sidebar search field
  const grid = document.getElementById('stores-grid');          // Flex container for store buttons
  const list = document.getElementById('store-products-list');  // Grid where cards are injected
  const empty = document.getElementById('store-products-empty');// Placeholder for zero matches
  const title = document.getElementById('store-products-title');// Heading showing active Store
  const subtitle = document.getElementById('store-products-subtitle'); // Product count metadata
  const loading = document.getElementById('store-products-loading');   // Spinner SVG/Icon

  // Safety Gate: Ensure we are actually on the store-specific page view
  if (!grid) {
    // console.log('setupStoreSuggestions: grid element not found, skipping setup');
    return; // Silent exit for other pages
  }

  // Collection: Convert NodeList of all sidebar buttons to a searchable Array
  const cards = Array.from(grid.querySelectorAll('.store-card-btn'));
  console.log('setupStoreSuggestions: Found', cards.length, 'store cards');

  /**
   * RENDERER: DYNAMIC HTML GENERATION
   * Converts raw API JSON data into styled Bootstrap Product Cards.
   * 
   * @param {Array} items - List of product objects from backend
   * @param {string} storeName - Human-readable name of the active retailer
   */
  const renderProducts = (items = [], storeName = '') => { // UI Builder
    if (!list) return; // Guard
    list.innerHTML = ''; // Wipe previous results to avoid stacking

    // 1. Empty State Logic: Handle cases where a store has no indexed products
    if (!items.length) {
      if (empty) empty.style.display = 'block'; // Show "Sad basket" icon
      list.style.display = 'none'; // Hide grid container
      if (subtitle) subtitle.textContent = 'No products or deals found for this store.';
      return; // Stop rendering
    }

    // 2. Success State Logic: Reveal the products grid
    if (empty) empty.style.display = 'none'; // Clear empty state
    list.style.display = ''; // Reset display to default (flex/grid)
    if (subtitle) subtitle.textContent = `${items.length} item${items.length === 1 ? '' : 's'} from ${storeName}`;

    // 3. Item HTML Template Generator: Logic for single product mapping
    const toHtml = (item) => { // Inner mapping function
      // Data Normalization: Handle inconsistencies between featured deals vs standard products
      const name = item.name || item.title || 'Product';
      
      // Attempt to find localized price for THIS store specifically (important for comparisons)
      const price = item.price || (item.matched_stores && item.matched_stores[0] && item.matched_stores[0].price) || '';
      
      // Image Selection Strategy:
      // Priority 1: Store-specific crop
      // Priority 2: Global generic product image
      // Priority 3: Placeholder service
      let img = 'https://via.placeholder.com/320x200';
      if (Array.isArray(item.matched_stores) && item.matched_stores.length && item.matched_stores[0].image) {
        img = item.matched_stores[0].image;
      } else if (item.image) {
        img = item.image;
      } else if (item.images && item.images[0]) {
        img = item.images[0];
      }

      // Store Availability Tags:
      // Shows where else you can buy this or highlights the current store
      const storeTags = [];
      if (Array.isArray(item.matched_stores) && item.matched_stores.length) {
        item.matched_stores.forEach(s => {
          const label = (s.store || s.name || '').trim(); // Name of store
          const priceLabel = s.price ? ` · €${s.price}` : ''; // Price at that store
          if (label) storeTags.push(`${label}${priceLabel}`);
        });
      } else if (item.store) {
        storeTags.push(item.store); // Fallback to root store property
      }
      
      // Map strings to HTML badge elements
      const storeBadges = storeTags.map(t => `<span class="badge bg-light text-dark border">${escapeHtml(t)}</span>`).join(' ');
      
      // Badge logic: Highlight if this is a "Featured Deal" vs regular inventory
      const source = item.source === 'featured_deal' ? 'Featured Deal' : 'Product';
      
      // Return the Final Card Component String
      return `
        <div class="col-md-6 col-lg-4 mb-4">
          <div class="store-product-card h-100 d-flex flex-column card shadow-sm border-0">
            <!-- Product Media Area -->
            <div class="position-relative">
              <img src="${img}" alt="${escapeHtml(name)}" class="product-image w-100" style="height: 200px; object-fit: contain; padding: 1rem;">
              <!-- Source Badge: Success (Green) for deals, Primary (Blue) for standard -->
              <span class="position-absolute top-0 end-0 m-2 badge ${item.source === 'featured_deal' ? 'bg-success' : 'bg-primary'}">
                ${source}
              </span>
            </div>
            
            <!-- Card Body Content -->
            <div class="p-3 d-flex flex-column flex-grow-1 bg-white">
              <div class="d-flex justify-content-between align-items-start gap-2">
                <h6 class="mb-1 fw-bold text-dark">${escapeHtml(name)}</h6>
              </div>
              
              <!-- Localized Price: Uses euro symbol prefix -->
              ${price ? `<div class="text-primary fw-bold fs-5 mb-2">€${escapeHtml(String(price))}</div>` : ''}
              
              <!-- Store Badges: Horizontal scrollable/wrapped tags -->
              <div class="d-flex flex-wrap gap-1 mb-3">${storeBadges}</div>
              
              <!-- Footer: Meta info and view trigger -->
              <div class="mt-auto d-flex justify-content-between align-items-center">
                <small class="text-muted">${escapeHtml(item.category || 'General')}</small>
                <button class="btn btn-sm btn-outline-primary rounded-pill px-3">View</button>
              </div>
            </div>
          </div>
        </div>`;
    };

    // Performance Optimization: 
    // We map all items to strings, join them, and set innerHTML ONCE.
    // This minimizes expensive browser reflows/paints compared to individual appends.
    list.innerHTML = items.map(toHtml).join('');
  };

  /**
   * ASYNC DATA FETCHING WRAPPER
   * Makes the network request to the store-specific API endpoint.
   * 
   * @param {string} storeName - Primary identifier for search filter (e.g., "Lidl")
   */
  const fetchStore = async (storeName) => { // Network handler
    if (!storeName) return; // Guard
    
    // UI LOADING STATE: Visual feedback during network latency
    if (loading) loading.style.display = 'inline-block'; // Reveal spinner
    if (empty) empty.style.display = 'none'; // Hide negative state
    if (list) list.style.display = 'none'; // Hide previous data
    if (subtitle) subtitle.textContent = 'Loading products...';

    try {
      // API Execution: Hits the store products route
      const res = await fetch(`/api/store/${encodeURIComponent(storeName)}/products`, { credentials: 'same-origin' });
      if (!res.ok) throw new Error('Request failed'); // Basic error bubbling
      
      const data = await res.json(); // Transform body
      const items = [...(data.products || [])]; // Spread into new array for safety
      
      // 1. Result Analysis
      if (!items.length) {
        if (subtitle) subtitle.textContent = `No products found for ${storeName}`;
        if (empty) empty.style.display = 'block'; // Fallback view
        return;
      }

      // 2. Refresh UI
      renderProducts(items, storeName); // Start the HTML injection
      
    } catch (err) { // Network/JSON parse failures
      console.error(err); // Log for developers
      renderProducts([], storeName); // Show empty state UI
      // Notify user via the system alert helper
      if (typeof showNotification === 'function') {
        showNotification('Could not load products for this store', 'danger');
      }
    } finally {
      // FINALIZATION: Always hide the spinner regardless of success/error
      if (loading) loading.style.display = 'none';
    }
  };

  /**
   * UI HELPER: BUTTON ACTIVE STATE
   * Manages the visual selection styling in the sidebar list.
   */
  const activateCard = (btn) => { // CSS Toggle
    cards.forEach(c => c.classList.remove('active')); // Reset all
    if (btn) btn.classList.add('active'); // Apply to clicked
  };

  // ----------------------
  // EVENT LISTENERS: INTERACTIONS
  // ----------------------
  
  // 1. Sidebar Item Selection (Using Event Delegation)
  // Instead of 20 individual listeners, we listen to the parent grid click.
  grid.addEventListener('click', (e) => { // High-level listener
    const btn = e.target.closest('.store-card-btn'); // Traverse up to the button
    if (!btn) return; // Ignore clicks on background/padding
    
    e.preventDefault(); // Stop default button behavior
    const storeName = btn.getAttribute('data-store-name'); // Read metadata
    console.log('Store selected:', storeName);
    
    if (!storeName) return; // Logic guard
    
    activateCard(btn); // Visual update
    if (title) title.textContent = storeName; // Title update
    
    fetchStore(storeName); // Trigger the network fetch
  });

  // 2. Sidebar Search/Filter Logic: Real-time list narrowing
  const filterGrid = (q) => { // Search helper
    const query = (q || '').toLowerCase(); // Normalization
    let visibleCount = 0; // Performance tracking
    
    cards.forEach(btn => { // Scan buttons
      const name = (btn.getAttribute('data-store-name') || '').toLowerCase();
      const location = (btn.textContent || '').toLowerCase();
      
      // Important: We toggle the parent wrapper column (.col-12) to collapse layout gaps cleanly
      const col = btn.closest('.col-12'); 
      if (!col) return;

      // Filter Predicate: Match name OR location text
      if (!query || name.includes(query) || location.includes(query)) {
        col.style.display = ''; // Reset CSS display
        visibleCount += 1;
      } else {
        col.style.display = 'none';
      }
    });

    if (visibleCount === 0) {
      // Optional: show empty state for sidebar
    }
  };

  // Bind Search Input
  input?.addEventListener('input', () => filterGrid(input.value.trim()));
  input?.addEventListener('keydown', (e) => { 
    if (e.key === 'Enter') { e.preventDefault(); filterGrid(input.value.trim()); } 
  });

  // 3. Initial Load: Auto-select first store
  if (cards.length) {
    cards[0].click();
  }
}

/**
 * GENERIC API HELPER
 * Wrapper around fetch to handle POST requests with JSON payloads consistently.
 * Automatically includes credentials and sets content-type.
 * 
 * @param {string} url - Target endpoint
 * @param {Object} body - Data to stringify
 * @returns {Promise<Object>} - Parsed JSON response or empty object on failure
 */
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
            if (!selectedStoreItem) { // If nothing clicked yet
                showNotification('Please select a store first', 'warning'); // Direct the user
                return; // Stop flow
            }
            
            // Extract attributes with specific Store Overrides
            const itemName = btn.getAttribute('data-name') || btn.getAttribute('data-title') || 'Item';
            // Prefer the price specific to the selected store badge
            let itemPrice = selectedStoreItem.getAttribute('data-store-price') || btn.getAttribute('data-price') || '';
            const itemStore = selectedStoreItem.getAttribute('data-store-name') || btn.getAttribute('data-store') || '';
            const itemImage = btn.getAttribute('data-image') || '';
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
function setupProfileEditHandlers() { // Settings hub
  const editBtn = document.getElementById('edit-profile-btn');
  const saveBtn = document.getElementById('save-profile-btn');
  const phoneEl = document.getElementById('profile-phone'); // Current UI display
  const addressEl = document.getElementById('profile-address'); // Current UI display
  const phoneInput = document.getElementById('profile-phone-input'); // Modal field
  const addressInput = document.getElementById('profile-address-input'); // Modal field
  
  if (!editBtn || !saveBtn) return; // Silent exit if not on profile page

  // 1. MODAL ENTRY: Hydrate inputs with existing text from the page
  editBtn.addEventListener('click', () => {
    const phoneText = phoneEl ? phoneEl.textContent.trim() : '';
    const addressText = addressEl ? addressEl.textContent.trim() : '';

    // Handle "Not provided" placeholder text safely
    const currentPhone = phoneText.toLowerCase().includes('not provided') ? '' : phoneText;
    const currentAddress = addressText.toLowerCase().includes('not provided') ? '' : addressText;

    // Split phone number into Country Code and Digits
    const countryCodeSelect = document.getElementById('profile-country-code');
    if (currentPhone && phoneInput && countryCodeSelect) {
      // Regex match: + (numbers) (rest)
      const match = currentPhone.match(/^(\+\d{1,3})(.*)/);
      if (match) {
        countryCodeSelect.value = match[1]; // Set dropdown (+353, +44, etc)
        phoneInput.value = match[2]; // Set raw number
      } else {
        phoneInput.value = currentPhone; // Fallback
      }
    } else if (phoneInput) {
      phoneInput.value = '';
    }

    if (addressInput) addressInput.value = currentAddress;
  });

  // 2. MODAL SUBMIT: Send JSON to Profile Update API
  saveBtn.addEventListener('click', async () => {
    const countryCodeSelect = document.getElementById('profile-country-code');
    const countryCode = countryCodeSelect ? countryCodeSelect.value : '+43';
    const phoneNumber = phoneInput ? phoneInput.value.trim() : '';
    const phone = phoneNumber ? countryCode + phoneNumber : ''; // Recombine
    const address = addressInput ? addressInput.value.trim() : '';

    try {
      // Request execution
      const res = await fetch('/profile/update', { 
        method: 'POST', 
        credentials: 'same-origin', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ phone, address }) 
      });
      
      const j = await res.json().catch(() => ({}));
      
      if (res.ok && j && j.success) { // Server Success 200
        // Update the UI labels without a page refresh
        if (phoneEl) phoneEl.textContent = phone || 'Not provided';
        if (addressEl) addressEl.textContent = address || 'Not provided';
        
        // Hide modal via Bootstrap API
        try { 
          const modal = bootstrap.Modal.getInstance(document.getElementById('profileModal')); 
          if (modal) modal.hide(); 
        } catch (e) { }
        
        showNotification('Profile updated', 'success');
      } else { // Validation failure
        showNotification(j.error || 'Could not update profile', 'danger');
      }
    } catch (err) { // Network failure
      showNotification('Server error updating profile', 'danger');
    }
  });
}

/**
 * FEATURED DEALS SEARCH (LOCAL FILTERING)
 * Optimizes performance by filtering promotional deals already loaded on the page.
 */
function setupFeaturedDealsSearch() { // Deals filter
  const input = document.getElementById('featured-search-input'); // search bar
  const btn = document.getElementById('featured-search-btn'); // click trigger
  
  // Grid Selection: Target the "Featured" container specifically
  let dealsGrid = document.getElementById('products-grid');
  if (!dealsGrid) { // Fallback for various templates
    dealsGrid = document.querySelector('section.container .row.g-4');
  }

  // Sidebar Filter Inputs
  const applyFiltersBtn = document.getElementById('apply-filters');
  const clearFiltersBtn = document.getElementById('clear-filters');
  const minPrice = document.getElementById('min-price');
  const maxPrice = document.getElementById('max-price');
  const sortOrder = document.getElementById('sort-order');
  const categorySelect = document.getElementById('category-filter');
  const storeSelect = document.getElementById('store-filter');
  const categoryChipsRow = document.querySelector('.category-chip-row');

  if (!input || !dealsGrid) return; // Exit if elements are missing

  let allDeals = []; // Memory cache

  /**
   * STARTUP: SNAPSHOT DEALS
   * Scans the page once to collect all deal elements and their metadata.
   */
  const collectAllDeals = () => { // Initial scan
    allDeals = Array.from(dealsGrid.querySelectorAll('[data-name]')); // grab cards

    // HYDRATE STORE FILTER: 
    // Dynamically builds the dropdown list based on which stores actually have deals today.
    if (storeSelect) {
      const stores = new Set(); // deduplicate
      allDeals.forEach(col => {
        const s = col.getAttribute('data-store');
        if (s) stores.add(s);
      });

      // UI Rebuild: Inject sorted store list into <select>
      storeSelect.innerHTML = '<option value="">All Stores</option>';
      Array.from(stores).sort().forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.toLowerCase();
        opt.textContent = s.charAt(0).toUpperCase() + s.slice(1);
        storeSelect.appendChild(opt);
      });
    }
  };

  // Helper: Strip currency from price strings
  const parsePrice = (v) => {
    const n = Number(String(v || '').replace(/[^0-9.\-]/g, ''));
    return isNaN(n) ? 0 : n;
  };

  /**
   * DOM FILTERING ENGINE
   * Evaluates Search Query, Category Chips, Price Range, and Store selection simultaneously.
   */
  const doSearch = () => { // Filter logic
    // 1. GAIN CRITERIA: Read state from all sidebar inputs
    const q = input.value.trim().toLowerCase(); // text search
    const minVal = minPrice ? parseFloat(minPrice.value) : NaN; // floor
    const maxVal = maxPrice ? parseFloat(maxPrice.value) : NaN; // ceiling
    const sortVal = sortOrder ? sortOrder.value : 'price-asc'; // order
    
    // Category Detection: Check both visual chips and the standard select dropdown
    const activeChip = categoryChipsRow ? categoryChipsRow.querySelector('.category-chip.active') : null;
    const chipVal = activeChip ? (activeChip.dataset.categoryChip || '').trim() : '';
    const selectCategoryVal = categorySelect ? (categorySelect.value || '').trim() : '';
    const categoryVal = chipVal || selectCategoryVal;
    
    const storeVal = storeSelect ? (storeSelect.value || '').trim().toLowerCase() : '';

    const visible = []; // Collector

    // 2. CRITERIA EVALUATION LOOP
    allDeals.forEach(col => {
      if (!col) return;

      // Extract raw data from attributes
      const productName = (col.getAttribute('data-name') || '').toLowerCase();
      const priceText = col.getAttribute('data-price') || '0';
      const price = parsePrice(priceText);
      const categoryAttr = (col.getAttribute('data-category') || '').toLowerCase();
      const storeAttr = (col.getAttribute('data-store') || '').toLowerCase();

      // PREDICATE TESTS
      let searchMatch = !q || productName.includes(q); // Title contains query?
      let categoryMatch = !categoryVal || categoryAttr === categoryVal.toLowerCase(); // Category matches?
      let priceMatch = (isNaN(minVal) || price >= minVal) && (isNaN(maxVal) || price <= maxVal); // In range?
      let storeMatch = !storeVal || storeAttr === storeVal; // Store matches?

      // 3. UI UPDATE
      if (searchMatch && priceMatch && categoryMatch && storeMatch) {
        col.style.display = ''; // Show element
        visible.push({ col, price, name: productName }); // store for sorting
      } else {
        col.style.display = 'none'; // Hide element
      }
    });

    // 4. CLIENT-SIDE SORTING logic
    if (visible.length) {
      if (sortVal === 'price-asc' || sortVal === 'price-desc') {
        visible.sort((a, b) => sortVal === 'price-asc' ? a.price - b.price : b.price - a.price);
      } else if (sortVal === 'name-asc' || sortVal === 'name-desc') {
        visible.sort((a, b) => sortVal === 'name-asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name));
      }
      // Reorder the DOM based on sorted 'visible' array
      visible.forEach(v => dealsGrid.appendChild(v.col));
    }
  };

  /**
   * SERVER DEALS SEARCH (Navigation)
   * Hard redirects the browser to refresh data from the server-side Jinja templates.
   */
  const handleServerDealsSearch = () => { // Hard refresh
    const q = input.value.trim();
    const activeChip = categoryChipsRow ? categoryChipsRow.querySelector('.category-chip.active') : null;
    const categoryVal = activeChip ? (activeChip.dataset.categoryChip || '').trim() : '';

    // Build URL Parameters
    const params = new URLSearchParams();
    if (q) params.set('search', q);
    if (categoryVal) params.set('category', categoryVal);
    params.set('page', '1'); // Always reset pagination on a new search

    // Update Browser location
    window.location.href = window.location.pathname + '?' + params.toString();
  };

  // 1. Initial Data Capture
  collectAllDeals();

  // 2. Event Listeners
  input && input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleServerDealsSearch(); // Search refresh
    }
  });

  input && input.addEventListener('input', () => { 
    doSearch(); // Instant local filtering
  });

  if (applyFiltersBtn) applyFiltersBtn.addEventListener('click', (e) => { 
    e.preventDefault(); 
    handleServerDealsSearch(); // Reload with filters
  });

  if (clearFiltersBtn) clearFiltersBtn.addEventListener('click', (e) => { 
    e.preventDefault(); 
    window.location.href = window.location.pathname; // Hard reset
  });

  if (categorySelect) categorySelect.addEventListener('change', () => {
    handleServerDealsSearch(); // Dropdown reload
  });

  if (storeSelect) storeSelect.addEventListener('change', () => {
    doSearch(); // Filter currently visible cards
  });

  // 3. Category Chip Delegation
  if (categoryChipsRow) {
    categoryChipsRow.addEventListener('click', (e) => {
      const btnEl = e.target.closest('.category-chip');
      if (!btnEl) return;
      categoryChipsRow.querySelectorAll('.category-chip').forEach(ch => ch.classList.remove('active'));
      btnEl.classList.add('active');
      handleServerDealsSearch(); 
    });
  }
}

/**
 * SHOPPING LIST INTERACTIONS
 * Manages row-level interactivity: Drag-and-drop, quantity management, and bulk actions.
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
