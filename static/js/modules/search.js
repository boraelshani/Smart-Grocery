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

  if (!input || !resultsSection) return; // Exit if not on the search view where these apply

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
