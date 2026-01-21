// ===============================================
// SMART GROCERY FRONTEND JAVASCRIPT
// Handles user interactions: shopping lists, favorites, filtering, search
// ===============================================

/**
 * MAIN ENTRY POINT
 * We use 'DOMContentLoaded' to ensure all HTML elements are loaded before running any scripts.
 * This prevents "element not found" errors.
 */
document.addEventListener('DOMContentLoaded', () => {
  // INITIALIZE: Run all setup functions when page loads
  initializeBootstrapComponents();    // Tooltips, Popovers
  setupNavbarScroll();                // Navbar color change on scroll
  setupSearchFunctionality();         // Real-time search or redirect
  setupShoppingListHandlers();        // "Add to List" buttons
  setupShoppingListInteractions();    // Checkbox toggling within the list page
  setupClaimButtons();                // "Claim Deal" functionality
  setupProductModalHandlers();        // Resetting modals when closed
  setupStoreSuggestions();            // Auto-complete in store inputs
  setupProfileEditHandlers();         // Edit Profile form toggling
  setupFeaturedDealsSearch();         // Search bar on Deals page
  setupCompareHandlers();             // Sorting logic on Compare page
  setupCompareFilters();              // Filtering logic on Compare page
  setupPaginationSmoothTransition();  // AJAX-like page switching (optional)
  setupLogoutConfirmation();          // Intercept logout to show confirmation modal
  setupStoreSelection();              // Store picker (Aldi vs Tesco) on product cards

  // Always hide product modal on page load (prevents unwanted popup loops on creating new items)
  // This is a safety cleanup.
  const productModalEl = document.getElementById('productModal');
  if (productModalEl) {
    const modalInstance = bootstrap.Modal.getOrCreateInstance(productModalEl);
    modalInstance.hide();
  }
});

// EVENT LISTENER: BROWSER BACK BUTTON
// Hide product modal on browser back navigation (prevents unwanted popup staying open)
window.addEventListener('pageshow', function (event) {
  const productModalEl = document.getElementById('productModal');
  if (productModalEl) {
    const modalInstance = bootstrap.Modal.getOrCreateInstance(productModalEl);
    modalInstance.hide();
  }
});

/**
 * NAVBAR SCROLL EFFECT
 * Adds a '.scrolled' CSS class to the navbar when the user scrolls down > 50px.
 * This allows us to change transparency/shadow via CSS.
 */
function setupNavbarScroll() {
  const nav = document.querySelector('.navbar-premium');
  if (!nav) return; // Exit if navbar doesn't exist on this page (e.g. 404 page)

  const handleScroll = () => {
    // Check vertical scroll position (Y-axis)
    if (window.scrollY > 50) {
      nav.classList.add('scrolled'); // Add opaque background/shadow
    } else {
      nav.classList.remove('scrolled'); // Revert to transparent/flat
    }
  };

  // Attach listener to window scroll event
  window.addEventListener('scroll', handleScroll);
  handleScroll(); // Initial check in case page loads scrolled down
}

// BOOTSTRAP: Activate tooltip popovers
// Bootstrap 5 requires manual initialization of tooltips (hover text)
function initializeBootstrapComponents() {
  // Select all elements with data-bs-toggle="tooltip"
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  // Create a new Tooltip instance for each
  tooltipTriggerList.map(function (tooltipTriggerEl) { return new bootstrap.Tooltip(tooltipTriggerEl); });
}

/**
 * LOGOUT CONFIRMATION INTERCEPTOR
 * Intercepts any click on a logout link and shows a custom confirmation modal
 * instead of immediately navigating away.
 */
function setupLogoutConfirmation() {
  // EVENT DELEGATION / CAPTURE PHASE
  // We listen on the 'document' for clicks, using 'true' for the capture phase.
  // This lets us intercept the event *before* it reaches the target link.
  document.addEventListener('click', (e) => {
    // EXCEPTION: If the user clicks inside the modal itself (e.g. "Yes" or "No"),
    // don't interfere. We check if the click target is a child of the modal.
    if (e.target.closest('#customLogoutModal')) {
      return;
    }

    // Check if the clicked element (or its parent) is an anchor tag linking to "/logout"
    const logoutBtn = e.target.closest('a[href*="/logout"]');
    if (logoutBtn) {
      // PROACTIVELY STOP EVERYTHING
      e.preventDefault();         // Stop the link from navigating to /logout
      e.stopPropagation();        // Stop event bubbling up to other handlers
      e.stopImmediatePropagation(); // Stop other listeners on this specific element
      
      // Show our custom UI instead
      showLogoutModal(logoutBtn.href);
      return false; 
    }
  }, true); 
}

/**
 * Dynamically creates and injects the Logout Modal into the DOM if it's missing.
 * This uses a "Lazy Load" pattern - we don't clutter the initial HTML with this modal.
 * 
 * @param {string} logoutUrl - The URL to go to if the user confirms "Yes".
 */
function showLogoutModal(logoutUrl) {
  // Check if modal DOM element already exists
  let modalElem = document.getElementById('customLogoutModal');
  
  // LAZY CREATION: Only create the HTML structure the first time it's needed.
  if (!modalElem) {
    // Template Literal with the Modal HTML
    const modalHtml = `
      <div class="modal fade" id="customLogoutModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered modal-sm">
          <div class="modal-content border-0 shadow-lg" style="border-radius: 20px;">
            <div class="modal-body text-center p-4">
              <div class="mb-3">
                <!-- Icon -->
                <i class="bi bi-door-open text-danger" style="font-size: 3rem;"></i>
              </div>
              <h5 class="fw-bold mb-2">Wait! Logging out?</h5>
              <p class="text-muted small mb-4">Are you sure you want to end your session?</p>
              <div class="d-grid gap-2">
                <!-- "Yes" button acts as the original link -->
                <a href="${logoutUrl}" class="btn btn-danger rounded-pill fw-bold py-2">Yes, Log Out</a>
                <!-- "No" button dismisses modal -->
                <button type="button" class="btn btn-light rounded-pill fw-semibold py-2" data-bs-dismiss="modal">Stay Logged In</button>
              </div>
            </div>
          </div>
        </div>
      </div>`;
    // Insert at end of <body>
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    modalElem = document.getElementById('customLogoutModal');
  } else {
    // Update the URL in case it's different (reuse the existing modal)
    const confirmBtn = modalElem.querySelector('a.btn-danger');
    if (confirmBtn) confirmBtn.href = logoutUrl;
  }

  // Use Bootstrap's JavaScript API to show the modal programmatically
  const modal = new bootstrap.Modal(modalElem);
  modal.show();
}

// Compare page: sort the rendered store list items by numeric price (client-side)
function setupCompareHandlers() {
  document.addEventListener('click', (e) => {
    // Check if clicked element was a Sort button
    const btn = e.target.closest('.sort-stores-btn');
    if (!btn) return;
    
    // Find context (specific product card)
    const card = btn.closest('.card');
    if (!card) return;
    const list = card.querySelector('.list-group');
    if (!list) return;

    // Helper: Parse currency strings "$1,234.50" -> 1234.50
    const items = Array.from(list.querySelectorAll('li'));
    function parsePriceFromText(text) {
      if (!text) return Number.POSITIVE_INFINITY;
      const m = String(text).match(/\d+[\d,.]*/); // Regex to find numbers
      if (!m) return Number.POSITIVE_INFINITY;
      const cleaned = m[0].replace(/,/g, ''); // Remove commas
      const n = Number(cleaned);
      return isNaN(n) ? Number.POSITIVE_INFINITY : n;
    }
    
    // Create temporary array of objects [DOM_Node, Price_Value]
    const mapped = items.map(li => {
      const priceText = li.textContent || li.innerText || '';
      return { node: li, price: parsePriceFromText(priceText) };
    });
    
    // Sort array by Price (Ascending)
    mapped.sort((a, b) => a.price - b.price);
    
    // Re-render: Clear existing list and append sorted nodes
    list.innerHTML = '';
    mapped.forEach((m, idx) => {
      // VISUAL ENHANCEMENT: Add 'Best Price' badge to the winner (first item)
      if (idx === 0) {
        // ensure a badge exists
        if (!m.node.querySelector('.best-price-badge')) {
          const span = document.createElement('span');
          span.className = 'badge bg-warning text-dark ms-2 best-price-badge';
          span.textContent = 'Best Price';
          // try to append to end of item
          m.node.appendChild(span);
        }
      } else {
        // Remove badge from losers
        const existing = m.node.querySelector('.best-price-badge'); if (existing) existing.remove();
      }
      list.appendChild(m.node);
    });
  });
}

/**
 * CLIENT-SIDE COMPARISON FILTERS
 * Allows users to filter distinct store cards without page reload.
 */
function setupStoreSelection() {
  document.addEventListener('click', function (e) {
    // EXCEPTION: If clicking the "Go to Store" button (external link), 
    // don't trigger selection logic.
    if (e.target.closest('.btn-go-store')) {
      e.stopPropagation();
      return;
    }

    // Check if clicked element is a Store Option (.store-item)
    const storeItem = e.target.closest('.store-item');
    if (storeItem) {
      const productCard = storeItem.closest('.product-card') || storeItem.closest('.card');
      if (productCard) {
        const isAlreadySelected = storeItem.classList.contains('selected');

        // 1. GLOBAL RESET (Optional UX choice)
        // Deselect ANY store-item on the ENTIRE page before selecting this one?
        // Currently configured to deselect others to show "Active" state clearly.
        try {
          document.querySelectorAll('.store-item.selected').forEach(selectedItem => {
            if (selectedItem === storeItem) return; // Skip current if we're just toggling

            // Find other cards and reset their UI state
            const otherCard = selectedItem.closest('.product-card') || selectedItem.closest('.card');
            selectedItem.classList.remove('selected');

            if (otherCard) {
              const otherAddBtn = otherCard.querySelector('.btn-premium-add');
              const otherPriceBadge = otherCard.querySelector('.price-badge');

              // Revert Button Data
              if (otherAddBtn) {
                // Restore original (lowest) price stored in data-initial-price
                otherAddBtn.dataset.price = otherAddBtn.getAttribute('data-initial-price') || '';
                otherAddBtn.dataset.store = ''; // Clear specific store selection
              }
              // Revert Price Badge
              if (otherPriceBadge) {
                const initialPrice = otherAddBtn ? otherAddBtn.getAttribute('data-initial-price') : '';
                if (initialPrice) {
                  const inner = otherPriceBadge.querySelector('i') ? '<i class="bi bi-tag-fill"></i> ' : '';
                  otherPriceBadge.innerHTML = inner + '€' + initialPrice;
                }
              }
            }
          });
        } catch (err) { console.error('Error in global store reset', err); }

        // 2. LOCAL CARD RESET
        // Deselect other stores within THIS same card
        const allLocalStoreItems = productCard.querySelectorAll('.store-item');
        allLocalStoreItems.forEach(item => item.classList.remove('selected'));

        const addBtn = productCard.querySelector('.btn-premium-add');
        const priceBadge = productCard.querySelector('.price-badge');
        const productImage = productCard.querySelector('.product-image');

        // 3. TOGGLE STATES
        if (isAlreadySelected) {
          // A. User clicked the same store again -> DESELECT (Revert to default)
          if (addBtn) {
            addBtn.dataset.price = addBtn.getAttribute('data-initial-price') || '';
            addBtn.dataset.store = '';
          }
          if (priceBadge) {
            const initialPrice = addBtn ? addBtn.getAttribute('data-initial-price') : '';
            if (initialPrice) {
              const inner = priceBadge.querySelector('i') ? '<i class="bi bi-tag-fill"></i> ' : '';
              priceBadge.innerHTML = inner + '€' + initialPrice;
            }
          }
          // Revert Image
          if (productImage && addBtn) {
            const originalImage = addBtn.getAttribute('data-image');
            if (originalImage) productImage.src = originalImage;
          }
        } else {
          // B. User clicked a new store -> SELECT IT
          storeItem.classList.add('selected');
          
          // Update "Add to List" button with selected store's price/name
          if (addBtn) {
            addBtn.dataset.price = storeItem.dataset.storePrice;
            addBtn.dataset.store = storeItem.dataset.storeName;
          }
          // Update Price Badge with visual pop animation
          if (priceBadge) {
            const inner = priceBadge.querySelector('i') ? '<i class="bi bi-tag-fill"></i> ' : '';
            priceBadge.innerHTML = inner + '€' + storeItem.dataset.storePrice;
            // Pop animation
            priceBadge.style.transform = 'scale(1.1)';
            setTimeout(() => { priceBadge.style.transform = 'scale(1)'; }, 200);
          }
          // Update Product Image to specific store version (if available)
          if (productImage && storeItem.dataset.image) {
            // Only swap if it's not a generic placeholder
            if (!storeItem.dataset.image.includes('placeholder.svg')) {
               productImage.src = storeItem.dataset.image;
            }
          }
        }
      }
      e.preventDefault();
      e.stopPropagation();
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
  const updateActiveFilters = (searchVal, categoryVal, storeVal, minVal, maxVal) => {
    if (!activeFiltersDiv) return;
    activeFiltersDiv.innerHTML = '';
    let hasFilters = false;

    // Helper: Create Pill
    const createFilterBadge = (text, onRemove) => {
      const badge = document.createElement('span');
      badge.className = 'badge bg-primary d-flex align-items-center gap-1 p-2';
      badge.style.borderRadius = '20px';
      badge.innerHTML = `${text} <i class="bi bi-x-circle ms-1" style="cursor:pointer;"></i>`;
      badge.querySelector('i').onclick = onRemove;
      return badge;
    };

    // Add Pill for Search
    if (searchVal) {
      hasFilters = true;
      activeFiltersDiv.appendChild(createFilterBadge('Search: ' + searchVal, () => {
        if (searchInput) { searchInput.value = ''; applyFilters(); }
      }));
    }

    // Add Pill for Category
    if (categoryVal) {
      hasFilters = true;
      activeFiltersDiv.appendChild(createFilterBadge('Category: ' + categoryVal, () => {
        if (categoryChipsRow) categoryChipsRow.querySelectorAll('.category-chip').forEach(ch => ch.classList.remove('active'));
        if (categorySelect) categorySelect.value = '';
        applyFilters();
      }));
    }

    // Add Pill for Store
    if (storeVal) {
      hasFilters = true;
      activeFiltersDiv.appendChild(createFilterBadge('Store: ' + storeVal, () => {
        if (storeFilter) { storeFilter.value = ''; applyFilters(); }
      }));
    }

    // Add Pill for Price
    if (!isNaN(minVal) || !isNaN(maxVal)) {
      hasFilters = true;
      let text = 'Price: ';
      if (!isNaN(minVal) && !isNaN(maxVal)) text += `€${minVal}-€${maxVal}`;
      else if (!isNaN(minVal)) text += `Min €${minVal}`;
      else text += `Max €${maxVal}`;

      activeFiltersDiv.appendChild(createFilterBadge(text, () => {
        if (minInput) minInput.value = '';
        if (maxInput) maxInput.value = '';
        applyFilters();
      }));
    }

    // Show/Hide "Clear All" button
    if (hasFilters) {
      activeFiltersDiv.style.display = 'flex';
      const clearAll = document.createElement('button');
      clearAll.className = 'btn btn-sm btn-outline-secondary rounded-pill ms-2';
      clearAll.innerHTML = '<i class="bi bi-x-circle"></i> Clear All';
      clearAll.onclick = clearFilters;
      activeFiltersDiv.appendChild(clearAll);
    } else {
      activeFiltersDiv.style.display = 'none';
    }
  };

  /**
   * RESET HANDLER
   * Clears all filters and restores full list.
   */
  const clearFilters = () => {
    if (searchInput) searchInput.value = '';
    if (storeFilter) storeFilter.value = '';
    if (categorySelect) categorySelect.value = '';
    if (categoryChipsRow) categoryChipsRow.querySelectorAll('.category-chip').forEach(ch => ch.classList.remove('active'));
    if (minInput) minInput.value = '';
    if (maxInput) maxInput.value = '';
    if (sortSelect) sortSelect.value = 'price-asc'; // Defaultsort
    
    // Show all
    allProducts.forEach(col => { if (col) col.style.display = ''; });
    updateActiveFilters('', '', '', NaN, NaN); // Clear pills
  };

  // ----------------------
  // EVENT LISTENERS
  // ----------------------
  collectStoresAndCategories();

  // URL Parameter Helper (Server-side Reload)
  const updateParamAndReload = (key, value) => {
    const url = new URL(window.location.href);
    if (value) url.searchParams.set(key, value);
    else url.searchParams.delete(key);
    url.searchParams.set('page', '1');
    window.location.href = url.toString();
  };

  // Search Input: Pressing Enter actually reloads page for deep search (server-side)
  // This varies from Client-side filter behavior above - preserving legacy hybrid behavior.
  searchInput && searchInput.addEventListener('keydown', (e) => { 
    if (e.key === 'Enter') { 
      e.preventDefault(); 
      updateParamAndReload('search', searchInput.value.trim()); 
    } 
  });
  
  // Search Button: Deep Search
  searchBtn && searchBtn.addEventListener('click', (e) => { 
    e.preventDefault(); 
    updateParamAndReload('search', searchInput ? searchInput.value.trim() : ''); 
  });
  
  // Sidebar "Apply" button: Client-side Filter
  applyBtn && applyBtn.addEventListener('click', (e) => { e.preventDefault(); applyFilters(); });
  
  // Sidebar "Clear" button: Hybrid Clear (Check URL vs DOM)
  clearBtn && clearBtn.addEventListener('click', (e) => { 
    e.preventDefault(); 
    const url = new URL(window.location.href);
    // If we have query params, we must reload the page to clear them
    if (url.searchParams.has('category') || url.searchParams.has('search')) {
      window.location.href = window.location.pathname; 
    } else {
      // Otherwise just clear the client-side DOM filters
      clearFilters(); 
    }
  });

  categorySelect && categorySelect.addEventListener('change', () => {
    updateParamAndReload('category', categorySelect.value);
  });

  storeFilter && storeFilter.addEventListener('change', () => { applyFilters(); });
  minInput && minInput.addEventListener('change', () => { applyFilters(); });
  maxInput && maxInput.addEventListener('change', () => { applyFilters(); });
  sortSelect && sortSelect.addEventListener('change', () => { applyFilters(); });
  
  // Chip Click Handler
  if (categoryChipsRow) {
    categoryChipsRow.addEventListener('click', (e) => {
      const btn = e.target.closest('.category-chip');
      if (!btn) return;
      const val = (btn.dataset.categoryChip || '').trim();
      updateParamAndReload('category', val);
    });
  }
}

// Smooth-ish transition when paging compare results (fade grid, then navigate)
function setupPaginationSmoothTransition() {
  const grid = document.getElementById('products-grid');
  if (!grid) return;
  const links = document.querySelectorAll('[data-pagination-link="true"]');
  if (!links.length) return;

  links.forEach(link => {
    link.addEventListener('click', (e) => {
      const href = link.getAttribute('href');
      if (!href || href === '#') return;
      e.preventDefault();
      grid.classList.add('fade-out');
      setTimeout(() => { window.location.href = href; }, 140);
    });
  });
}
/**
 * ===============================================
 * HOME PAGE SEARCH: MIXED MODE
 * ===============================================
 * This complex function handles two different search paradigms:
 * 1. SERVER-SIDE SEARCH (Async Fetch): Used when typing in the main input.
 *    - Hits `/api/search-products`
 *    - Renders entirely new HTML cards.
 * 2. CLIENT-SIDE FILTERING (DOM Manipulation): Used when clicking "Apply Filters" sidebar.
 *    - Iterates over existing DOM elements.
 *    - Toggles `display: none`.
 */
function setupSearchFunctionality() {
  // DOM ELEMENT REFERENCES
  // ----------------------
  const input = document.getElementById('home-search-input');
  const btn = document.getElementById('home-search-btn');
  const resultsSection = document.getElementById('search-results-section'); // Where JSON results go
  const resultsContainer = document.getElementById('search-results'); // The grid inside that section
  const productsGrid = document.getElementById('products-grid'); // The original Server-Side Rendered (SSR) grid
  
  // Filter Inputs
  const applyFiltersBtn = document.getElementById('apply-filters');
  const clearFiltersBtn = document.getElementById('clear-filters');
  const storeFilter = document.getElementById('store-filter');
  const minPrice = document.getElementById('min-price');
  const maxPrice = document.getElementById('max-price');
  const sortOrder = document.getElementById('sort-order');

  let allProducts = [];

  /**
   * SNAPSHOT INITIAL STATE
   * We grab a reference to all originally rendered product cards on page load.
   * This allows us to "Restore" the view when filters are cleared, 
   * rather than needing to reload the page.
   */
  const collectAllProducts = () => {
    if (!productsGrid) return;
    // Select all Bootstrap columns that contain cards
    allProducts = Array.from(productsGrid.querySelectorAll('[class*="col"]'));
  };

  /**
   * ASYNC SEARCH HANDLER
   * Triggered by: Main Search Button or Enter Key
   * Action: Fetches JSON from API -> Renders new HTML
   */
  async function doSearch() {
    if (!input) return;
    
    // 1. Validation
    const q = input.value.trim();
    if (!q) { 
      showNotification('Please enter a search term', 'info'); 
      return; 
    }

    try {
      // 2. Network Request
      // We use 'same-origin' to ensure cookies/session info is passed if needed
      const res = await fetch(`/api/search-products?q=${encodeURIComponent(q)}`, { credentials: 'same-origin' });
      const data = await res.json().catch(() => ({}));
      const items = data.items || [];

      // 3. Render Setup
      if (!resultsSection || !resultsContainer) return;
      resultsContainer.innerHTML = ''; // Clear previous results

      // 4. Empty State Handler
      if (!items.length) {
        resultsContainer.innerHTML = `<div class="col-12"><p class="text-muted">No matching products found.</p></div>`;
        resultsSection.style.display = 'block';
        return;
      }

      // 5. Result Rendering Loop
      // Converts raw JSON objects into Bootstrap Card HTML
      items.forEach(it => {
        // Data Normalization (Handle missing fields safely)
        const title = it.name || it.title || '';
        const price = it.price || (it.cheapest && it.cheapest.price) || '';
        const img = it.image || (it.images && it.images[0]) || 'https://via.placeholder.com/300x200';
        const store = (it.stores && it.stores[0] && it.stores[0].store) || '';
        const id = it.id || title;

        // Create Container Column
        const col = document.createElement('div'); 
        col.className = 'col-md-6 col-lg-4';

        // Template Literal: Product Card
        col.innerHTML = `
          <div class="card shadow-sm h-100">
            <!-- Product Thumbnail -->
            <img src="${img}" class="card-img-top product-thumb" alt="${escapeHtml(title)}">
            
            <div class="card-body d-flex flex-column">
              <h5 class="card-title">${escapeHtml(title)}</h5>
              <p class="card-text mb-1 badge bg-light text-dark align-self-start border">${escapeHtml(store)}</p>
              <p class="card-text text-primary fw-bold mb-3">${escapeHtml(price)}</p>
              
              <!-- Action Buttons (Push to bottom of flex container) -->
              <div class="mt-auto d-flex gap-2">
                <!-- View Details Modal Trigger -->
                <button class="btn btn-sm btn-info text-white view-details-btn" 
                        data-bs-toggle="modal" 
                        data-bs-target="#productModal" 
                        data-title="${escapeHtml(title)}" 
                        data-price="${escapeHtml(price)}" 
                        data-store="${escapeHtml(store)}" 
                        data-image="${escapeHtml(img)}">
                  <i class="bi bi-eye"></i> View Details
                </button>
                
                <!-- Add to List Trigger -->
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
        resultsContainer.appendChild(col);
      });

      // 6. View State Transition
      // Show the dynamic results, hide the static SSR grid
      resultsSection.style.display = 'block';
      if (productsGrid) productsGrid.style.display = 'none';

      // 7. Event Re-binding
      // Since we injected new HTML, previously bound event listeners (like for Modals) 
      // might need a refresh or we need manually delegate.
      // This helper re-scans the DOM for buttons.
      try { setupProductModalHandlers(); } catch (e) { }

    } catch (err) {
      console.error(err);
      showNotification('Search failed due to a network error.', 'danger');
    }
  }

  /**
   * CLIENT-SIDE FILTER HANDLER
   * Triggered by: "Apply Filters" button in sidebar.
   * Action: Hides DOM elements in the SSR grid based on criteria.
   */
  const applyHomFilters = () => {
    if (!productsGrid) return;

    // 1. Parse Inputs safely
    const minVal = minPrice ? parseFloat(minPrice.value) : NaN;
    const maxVal = maxPrice ? parseFloat(maxPrice.value) : NaN;
    const sortVal = sortOrder ? sortOrder.value : 'price-asc';
    
    // Robust Price Parser (Handles currency symbols)
    const parsePrice = (v) => { 
      const n = Number(String(v || '').replace(/[^0-9.\-]/g, '')); 
      return isNaN(n) ? 0 : n; 
    };

    const visible = []; // To store items that pass all tests

    // 2. Evaluation Loop
    allProducts.forEach(col => {
      if (!col) return;
      const card = col.querySelector('.card');
      if (!card) return;

      // Extract Data from DOM Attributes (fast) or Text Content (slow backup)
      const priceText = card.getAttribute('data-price') || card.querySelector('[class*="price"]')?.textContent || '0';
      const price = parsePrice(priceText);

      // Predicate: Does it match price range?
      let priceMatch = true;
      if (!isNaN(minVal)) priceMatch = priceMatch && (price >= minVal);
      if (!isNaN(maxVal)) priceMatch = priceMatch && (price <= maxVal);

      // 3. Layout Update
      if (priceMatch) {
        col.style.display = ''; // Show
        const name = (card.getAttribute('data-name') || card.querySelector('.card-title')?.textContent || '').toLowerCase();
        visible.push({ col, price, name });
      } else {
        col.style.display = 'none'; // Hide
      }
    });

    // 4. Sorting Logic
    if (visible.length) {
      if (sortVal === 'price-asc' || sortVal === 'price-desc') {
        visible.sort((a, b) => sortVal === 'price-asc' ? a.price - b.price : b.price - a.price);
      } else if (sortVal === 'name-asc' || sortVal === 'name-desc') {
        visible.sort((a, b) => sortVal === 'name-asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name));
      }
      
      // 5. DOM Reordering
      // appendChild moves an existing node rather than cloning it, 
      // preserving listeners and state.
      visible.forEach(v => productsGrid.appendChild(v.col));
    }
  };

  /**
   * RESET HANDLER
   * Restores input fields and visual grid state to default.
   */
  const clearHomeFilters = () => {
    if (minPrice) minPrice.value = '';
    if (maxPrice) maxPrice.value = '';
    if (sortOrder) sortOrder.value = 'price-asc';
    if (storeFilter) storeFilter.value = '';
    if (input) input.value = '';

    // Show all originally cached products
    allProducts.forEach(col => { if (col) col.style.display = ''; });
    
    // Hide search results, show main grid
    if (resultsSection) resultsSection.style.display = 'none';
    if (productsGrid) productsGrid.style.display = '';
  };

  // ----------------------
  // EVENT BINDING
  // ----------------------
  // Run startup routine
  collectAllProducts();

  // Bind Search Actions
  if (btn) btn.addEventListener('click', doSearch);
  if (input) input.addEventListener('keydown', (e) => { 
    if (e.key === 'Enter') { 
      e.preventDefault(); 
      doSearch(); 
    } 
  });

  // Bind Sidebar Actions
  if (applyFiltersBtn) applyFiltersBtn.addEventListener('click', (e) => { 
    e.preventDefault(); 
    applyHomFilters(); 
  });
  if (clearFiltersBtn) clearFiltersBtn.addEventListener('click', (e) => { 
    e.preventDefault(); 
    clearHomeFilters(); 
  });
}

function noop() { }

/**
 * ===============================================
 * STORE SUGGESTIONS / STORE FINDER LOGIC
 * ===============================================
 * Handles the "Stores" page interactivity:
 * 1. Filtering the list of store buttons (Sidebar)
 * 2. Fetching products specific to a selected store (Async)
 * 3. Rendering those products in a grid (Dynamic HTML)
 */
function setupStoreSuggestions() {
  // DOM ELEMENT REFERENCES
  // ----------------------
  const input = document.getElementById('stores-search-input'); // Sidebar filter input
  const grid = document.getElementById('stores-grid');          // Container for sidebar buttons
  const list = document.getElementById('store-products-list');  // Main content area for products
  const empty = document.getElementById('store-products-empty');// "No products" placeholder
  const title = document.getElementById('store-products-title');// Header ("Aldi", "Lidl", etc)
  const subtitle = document.getElementById('store-products-subtitle'); // Item count text
  const loading = document.getElementById('store-products-loading');   // Spinner

  // Safety Check: If we aren't on the Stores page, exit.
  if (!grid) {
    // console.log('setupStoreSuggestions: grid element not found, skipping setup');
    return;
  }

  // Collection of all store sidebar buttons
  const cards = Array.from(grid.querySelectorAll('.store-card-btn'));
  console.log('setupStoreSuggestions: Found', cards.length, 'store cards');

  /**
   * RENDERER: DYNAMIC HTML GENERATION
   * Converts a list of JSON product objects into the main grid view.
   * 
   * @param {Array} items - List of product objects
   * @param {string} storeName - Name of the currently active store
   */
  const renderProducts = (items = [], storeName = '') => {
    if (!list) return;
    list.innerHTML = ''; // Clear previous view

    // Empty State Handling
    if (!items.length) {
      if (empty) empty.style.display = 'block';
      list.style.display = 'none';
      if (subtitle) subtitle.textContent = 'No products or deals found for this store.';
      return;
    }

    // Success State Handling
    if (empty) empty.style.display = 'none';
    list.style.display = '';
    if (subtitle) subtitle.textContent = `${items.length} item${items.length === 1 ? '' : 's'} from ${storeName}`;

    // Item HTML Template Generator
    const toHtml = (item) => {
      // 1. Data Normalization
      const name = item.name || item.title || 'Product';
      
      // Attempt to find localized price for THIS store specifically
      const price = item.price || (item.matched_stores && item.matched_stores[0] && item.matched_stores[0].price) || '';
      
      // 2. Image Selection Logic
      // Hierarchy: Store-specific image > Generic Item Image > Placeholder
      let img = 'https://via.placeholder.com/320x200';
      if (Array.isArray(item.matched_stores) && item.matched_stores.length && item.matched_stores[0].image) {
        img = item.matched_stores[0].image;
      } else if (item.image) {
        img = item.image;
      } else if (item.images && item.images[0]) {
        img = item.images[0];
      }

      // 3. Store Tags Generation
      // Creates badges for where else this product might be found
      const storeTags = [];
      if (Array.isArray(item.matched_stores) && item.matched_stores.length) {
        item.matched_stores.forEach(s => {
          const label = (s.store || s.name || '').trim();
          const priceLabel = s.price ? ` · ${s.price}` : '';
          if (label) storeTags.push(`${label}${priceLabel}`);
        });
      } else if (item.store) {
        storeTags.push(item.store);
      }
      const storeBadges = storeTags.map(t => `<span class="badge bg-light text-dark border">${escapeHtml(t)}</span>`).join(' ');
      
      const source = item.source === 'featured_deal' ? 'Featured Deal' : 'Product';
      
      // 4. Final HTML Output
      return `
        <div class="col-md-6 col-lg-4 mb-4">
          <div class="store-product-card h-100 d-flex flex-column card shadow-sm border-0">
            <!-- Product Image -->
            <div class="position-relative">
              <img src="${img}" alt="${escapeHtml(name)}" class="product-image w-100" style="height: 200px; object-fit: contain; padding: 1rem;">
              <span class="position-absolute top-0 end-0 m-2 badge ${item.source === 'featured_deal' ? 'bg-success' : 'bg-primary'}">
                ${source}
              </span>
            </div>
            
            <!-- Card Body -->
            <div class="p-3 d-flex flex-column flex-grow-1 bg-white">
              <div class="d-flex justify-content-between align-items-start gap-2">
                <h6 class="mb-1 fw-bold text-dark">${escapeHtml(name)}</h6>
              </div>
              
              ${price ? `<div class="text-primary fw-bold fs-5 mb-2">€${escapeHtml(String(price))}</div>` : ''}
              
              <!-- Store Badges -->
              <div class="d-flex flex-wrap gap-1 mb-3">${storeBadges}</div>
              
              <div class="mt-auto d-flex justify-content-between align-items-center">
                <small class="text-muted">${escapeHtml(item.category || 'General')}</small>
                <button class="btn btn-sm btn-outline-primary rounded-pill px-3">View</button>
              </div>
            </div>
          </div>
        </div>`;
    };

    // Inject all items at once for performance
    list.innerHTML = items.map(toHtml).join('');
  };

  /**
   * ASYNC DATA FETCHING
   * Retrieves products for the clicked store.
   * 
   * @param {string} storeName - "Tesco", "Aldi", etc.
   */
  const fetchStore = async (storeName) => {
    if (!storeName) return;
    
    // UI Loading State
    if (loading) loading.style.display = 'inline-block';
    if (empty) empty.style.display = 'none';
    if (list) list.style.display = 'none';
    if (subtitle) subtitle.textContent = 'Loading products...';

    try {
      // API Call
      const res = await fetch(`/api/store/${encodeURIComponent(storeName)}/products`, { credentials: 'same-origin' });
      if (!res.ok) throw new Error('Request failed');
      
      const data = await res.json();
      const items = [...(data.products || [])];
      
      // Render Results
      if (!items.length) {
        if (subtitle) subtitle.textContent = `No products found for ${storeName}`;
        if (empty) empty.style.display = 'block';
        return;
      }
      renderProducts(items, storeName);
      
    } catch (err) {
      console.error(err);
      renderProducts([], storeName);
      showNotification && showNotification('Could not load products for this store', 'danger');
    } finally {
      // Cleanup Loading State
      if (loading) loading.style.display = 'none';
    }
  };

  /**
   * UI HELPER: ACTIVE STATE TOGGLE
   * Highlights the selected sidebar button.
   */
  const activateCard = (btn) => {
    cards.forEach(c => c.classList.remove('active'));
    if (btn) btn.classList.add('active');
  };

  // ----------------------
  // EVENT LISTENERS
  // ----------------------
  
  // 1. Sidebar Selection (Delegated Event)
  grid.addEventListener('click', (e) => {
    const btn = e.target.closest('.store-card-btn');
    if (!btn) return;
    
    e.preventDefault();
    const storeName = btn.getAttribute('data-store-name');
    console.log('Store clicked:', storeName);
    
    if (!storeName) return;
    
    activateCard(btn);
    if (title) title.textContent = storeName;
    
    fetchStore(storeName); // Trigger load
  });

  // 2. Sidebar Search/Filter Logic
  const filterGrid = (q) => {
    const query = (q || '').toLowerCase();
    let visible = 0;
    
    cards.forEach(btn => {
      const name = (btn.getAttribute('data-store-name') || '').toLowerCase();
      const location = (btn.textContent || '').toLowerCase();
      // Important: We toggle the parent wrapper (.col-12) to hide the whole row gap
      const col = btn.closest('.col-12'); 
      if (!col) return;

      if (!query || name.includes(query) || location.includes(query)) {
        col.style.display = '';
        visible += 1;
      } else {
        col.style.display = 'none';
      }
    });

    if (visible === 0) {
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




// Simple fetch helper
async function apiPostJson(url, body) {
  const res = await fetch(url, {
    method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
  });
  return res.json().catch(() => ({}));
}

function refreshShoppingListUI() {
  const path = window.location.pathname || '';
  // Only reload on the shopping list page where a full refresh is desired
  if (path.includes('shopping_list') || path.endsWith('/shopping-list')) {
    window.location.reload();
  }
}

function showNotification(message, type = 'info') {
  if (!message) return;

  const TOAST_DURATION_MS = 3600;

  // Toast container (top-right stack)
  let container = document.getElementById('sg-toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'sg-toast-container';
    container.style.position = 'fixed';
    container.style.top = '18px';
    container.style.right = '18px';
    container.style.zIndex = '9999';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.maxWidth = '320px';
    document.body.appendChild(container);
  }

  // Purple-forward palette variants
  const palettes = {
    success: { bg: '#f2ebff', border: '#7a5af8', text: '#2f1b6d' },
    danger: { bg: '#fbebf1', border: '#d63384', text: '#6b103f' },
    warning: { bg: '#f6edff', border: '#b388ff', text: '#3f2a73' },
    info: { bg: '#ede7ff', border: '#6f42c1', text: '#2f1b6d' },
    default: { bg: '#f1ecff', border: '#8a63f5', text: '#2f1b6d' }
  };
  const palette = palettes[type] || palettes.default;

  const toast = document.createElement('div');
  toast.style.background = palette.bg;
  toast.style.border = `1px solid ${palette.border}`;
  toast.style.color = palette.text;
  toast.style.borderRadius = '12px';
  toast.style.boxShadow = '0 8px 30px rgba(0,0,0,0.12)';
  toast.style.padding = '12px 14px';
  toast.style.fontWeight = '600';
  toast.style.display = 'flex';
  toast.style.alignItems = 'center';
  toast.style.justifyContent = 'space-between';
  toast.style.opacity = '0';
  toast.style.transform = 'translateY(-6px)';
  toast.style.transition = 'all 0.2s ease';

  const textSpan = document.createElement('span');
  textSpan.textContent = message;
  textSpan.style.flex = '1';

  const closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.innerHTML = '&times;';
  closeBtn.style.background = 'transparent';
  closeBtn.style.border = 'none';
  closeBtn.style.color = palette.text;
  closeBtn.style.fontSize = '18px';
  closeBtn.style.lineHeight = '1';
  closeBtn.style.marginLeft = '10px';
  closeBtn.style.cursor = 'pointer';
  closeBtn.setAttribute('aria-label', 'Close notification');
  closeBtn.addEventListener('click', () => removeToast());

  toast.appendChild(textSpan);
  toast.appendChild(closeBtn);
  container.appendChild(toast);

  // Entrance animation
  requestAnimationFrame(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
  });

  const removeToast = () => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(-6px)';
    setTimeout(() => toast.remove(), 160);
  };

  setTimeout(removeToast, TOAST_DURATION_MS);
}

function formatPrice(price) { if (typeof price === 'string') price = price.replace(/[^0-9.]/g, ''); return Number(price) || 0; }

// Global variable to store pending item
let pendingItemToAdd = null;

// Global list selector function - shows modal for user to select which list to add item to
window.showListSelector = async function (item) {
  // If item is a DOM element (button), extract its data attributes
  if (item instanceof HTMLElement) {
    const btn = item;
    const name = btn.getAttribute('data-name') || btn.getAttribute('data-title') || 'Item';
    const price = btn.getAttribute('data-price') || '';
    const originalPrice = btn.getAttribute('data-original-price') || '';
    const store = btn.getAttribute('data-store') || '';
    const image = btn.getAttribute('data-image') || '';
    const id = btn.getAttribute('data-id') || null;

    const dealId = btn.getAttribute('data-deal-id') || null;
    const offerJson = btn.getAttribute('data-offer-json') || '';
    const tierJson = btn.getAttribute('data-tier-json') || '';
    const offerType = btn.getAttribute('data-offer-type') || '';
    const offerX = btn.getAttribute('data-offer-x') || '';
    const offerY = btn.getAttribute('data-offer-y') || '';

    // Build offer payload if present
    let offerPayload = null;
    try { if (offerJson) offerPayload = JSON.parse(offerJson); } catch (err) { }
    
    // Build tier payload if present
    let discountTiers = null;
    try { if (tierJson) discountTiers = JSON.parse(tierJson); } catch (err) { }

    if (!offerPayload && offerType === 'buyXgetY' && offerX && offerY) {
      const xNum = parseInt(offerX, 10) || 0;
      const yNum = parseInt(offerY, 10) || 0;
      if (xNum && yNum) offerPayload = { type: 'buyXgetY', x: xNum, y: yNum };
    }

    // Determine the base price to use. 
    // For multibuy deals, we MUST use the original (full) unit price for the calculation to work on the list.
    let basePriceToStore = price;
    if (offerPayload && (offerPayload.type === 'buyXgetY' || offerType === 'buyXgetY') && originalPrice) {
      basePriceToStore = originalPrice;
    }

    item = { name, price: basePriceToStore, store, image, id };
    if (dealId) item.deal_id = dealId;
    if (offerPayload) item.offer = offerPayload;
    if (discountTiers) item.discount_tiers = discountTiers;
    
    const priceVal = formatPrice(basePriceToStore);
    if (!isNaN(priceVal) && priceVal > 0) item.price_val = priceVal;
  }

  pendingItemToAdd = item;

  try {
    // Fetch user's shopping lists
    const response = await fetch('/api/get-lists');
    const data = await response.json();

    if (!data.success || !data.lists || data.lists.length === 0) {
      showNotification('No shopping lists available. Please create one first.', 'warning');
      return;
    }

    // Build modal content
    const modalBody = document.getElementById('globalListSelectorBody');
    if (!modalBody) {
      // Fallback to direct add if modal doesn't exist
      return await apiPostJson('/api/list/add-item', { item });
    }

    modalBody.innerHTML = '';

    // PREVIEW HEADER: Show what we are adding
    const itemPreview = document.createElement('div');
    itemPreview.className = 'text-center mb-4';
    
    let imgHtml = '';
    if (item.image && item.image !== 'undefined' && item.image !== '' && !item.image.includes('placeholder')) {
      imgHtml = `<img src="${item.image}" class="shadow-sm" style="width: 80px; height: 80px; object-fit: contain; background: white; border-radius: 20px; padding: 6px; box-shadow: 0 8px 25px rgba(0,0,0,0.15); margin-bottom: 15px;">`;
    } else {
      imgHtml = `<div class="mx-auto shadow-sm" style="width: 70px; height: 70px; background: rgba(255,255,255,0.2); border-radius: 20px; display: flex; align-items: center; justify-content: center; margin-bottom: 15px; border: 1px solid rgba(255,255,255,0.3);"><i class="bi bi-cart-plus-fill fs-2 text-white"></i></div>`;
    }

    itemPreview.innerHTML = `
      ${imgHtml}
      <h4 class="fw-800 text-white mb-2" style="font-weight: 800; letter-spacing: -0.5px;">${escapeHtml(item.name || 'New Item')}</h4>
      <div class="d-flex justify-content-center gap-2 align-items-center">
        ${item.price ? `<span class="badge bg-white text-primary fw-bold px-3 py-2 rounded-pill shadow-sm" style="font-size: 0.95rem;">€${item.price}</span>` : ''}
        ${item.store ? `<span class="badge bg-dark bg-opacity-25 text-white border border-white border-opacity-25 px-3 py-2 rounded-pill">${escapeHtml(item.store)}</span>` : ''}
      </div>
    `;
    modalBody.appendChild(itemPreview);

    // LIST OPTIONS
    const listContainer = document.createElement('div');
    listContainer.className = 'd-flex flex-column gap-2';
    modalBody.appendChild(listContainer);

    data.lists.forEach(list => {
      const itemCount = list.items ? list.items.length : 0;
      const card = document.createElement('div');
      card.className = 'list-selector-option btn-smooth';
      
      // Calculate total if available (optional enhancement)
      // We can add a subtle gradient to the icon based on list name length (just for distinctiveness)
      const hue = (list.name.length * 25) % 360; 

      card.innerHTML = `
        <div class="card-body p-3 d-flex align-items-center w-100">
          <div class="list-selector-icon me-3 shadow-sm flex-shrink-0" style="width: 50px; height: 50px; background: linear-gradient(135deg, hsl(${hue}, 70%, 60%), hsl(${hue}, 70%, 45%));">
            <i class="bi bi-bag-heart-fill fs-4"></i>
          </div>
          <div class="list-info flex-grow-1 text-start" style="min-width: 0;">
            <div class="list-title text-dark fw-bold mb-1 text-truncate" style="font-size: 1.05rem;">${escapeHtml(list.name)}</div>
            <div class="list-subtitle text-muted small d-flex align-items-center gap-2">
                <span class="badge bg-light text-secondary border rounded-pill px-2">${itemCount} items</span>
                <small class="text-truncate">${list.created_at ? list.created_at.substring(0,10) : ''}</small>
            </div>
          </div>
          <div class="list-action-icon rounded-circle bg-primary bg-opacity-10 text-primary d-flex align-items-center justify-content-center flex-shrink-0" style="width: 40px; height: 40px;">
            <i class="bi bi-plus-lg fw-bold"></i>
          </div>
        </div>
      `;

      card.addEventListener('click', () => addItemToSelectedList(list.id));
      listContainer.appendChild(card);
    });

    // Show modal
    const modalEl = document.getElementById('globalListSelectorModal');
    if (modalEl) {
      // Check if bootstrap is available
      if (typeof bootstrap === 'undefined' || !bootstrap.Modal) {
        console.warn('Bootstrap Modal not available, falling back to direct add');
        return apiPostJson('/api/list/add-item', { item });
      }
      
      let modal = bootstrap.Modal.getInstance(modalEl);
      if (!modal) {
        modal = new bootstrap.Modal(modalEl);
      }
      modal.show();
    }
  } catch (err) {
    console.error('Error showing list selector:', err);
    // Fallback: add to active list directly
    try {
      if (pendingItemToAdd) {
        const fallbackRes = await apiPostJson('/api/list/add-item', { item: pendingItemToAdd });
        if (fallbackRes && (fallbackRes.success === true || fallbackRes.success)) {
           showNotification('Added to shopping list', 'success');
           refreshShoppingListUI();
        } else {
           showNotification('Error adding to shopping list', 'danger');
        }
      }
    } catch(e) {}
  }
};

// Add item to the selected list
async function addItemToSelectedList(listId) {
  if (!pendingItemToAdd) {
    showNotification('No item to add', 'danger');
    return;
  }

  try {
    const response = await apiPostJson('/api/list/add-item', { item: pendingItemToAdd, list_id: listId });

    if (response && response.success) {
      showNotification(`${pendingItemToAdd.name || 'Item'} added to shopping list`, 'success');

      // Hide modal
      const modalEl = document.getElementById('globalListSelectorModal');
      if (modalEl) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }

      // Refresh shopping list UI if on that page
      if (typeof refreshShoppingListUI === 'function') {
        refreshShoppingListUI();
      }

      pendingItemToAdd = null;
    } else {
      showNotification(response?.error || 'Could not add item to list', 'danger');
    }
  } catch (err) {
    console.error('Error adding item:', err);
    showNotification('Error adding item to list', 'danger');
  }
}

// Central helper to add an item to the shopping list, always showing list selector
async function addItemToShoppingList(item) {
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

  // Fallback: add to active list directly
  try {
    return await apiPostJson('/api/list/add-item', { item });
  } catch (err) {
    return { success: false, error: 'request_failed' };
  }
}

// Toggle Favorite
window.toggleFavorite = async function(event, arg1, arg2) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }

  let btn, productId;
  // Handle different call signatures
  // 1. toggleFavorite(event, this) -> arg1 is element
  // 2. toggleFavorite(event, '123', this) -> arg1 is id, arg2 is element
  if (arg1 instanceof HTMLElement) {
    btn = arg1;
    productId = btn.getAttribute('data-product-id') || btn.getAttribute('data-id');
  } else {
    productId = arg1;
    btn = arg2;
  }

  if (!productId || !btn) {
    console.error('Missing product ID or button element', { productId, btn });
    showNotification('Error: Cannot toggle favorite', 'danger');
    return;
  }

  // Optimistic UI update
  const heartIcon = btn.querySelector('i');
  const wasActive = btn.classList.contains('active');
  
  if (wasActive) {
    btn.classList.remove('active');
    if (heartIcon) {
      heartIcon.classList.remove('bi-heart-fill');
      heartIcon.classList.add('bi-heart');
    }
  } else {
    btn.classList.add('active');
    if (heartIcon) {
      heartIcon.classList.remove('bi-heart');
      heartIcon.classList.add('bi-heart-fill');
    }
    
    // Add animation effect
    btn.style.transform = 'scale(1.2)';
    setTimeout(() => {
      btn.style.transform = 'scale(1)';
    }, 200);
  }

  try {
    const response = await fetch('/api/toggle-favorite', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ product_id: productId })
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || 'Failed to toggle favorite');
    }

    // Server confirmed, update UI if needed (e.g. show notification)
    if (data.action === 'added') {
      showNotification('Added to favorites', 'success');
    } else {
      showNotification('Removed from favorites', 'info');
    }
    
    // Sync other buttons for same product
    document.querySelectorAll(`.btn-favorite[data-product-id="${productId}"], .btn-favorite[data-id="${productId}"]`).forEach(otherBtn => {
      if (otherBtn === btn) return;
      if (data.is_favorite) {
        otherBtn.classList.add('active');
        const icon = otherBtn.querySelector('i');
        if (icon) {
          icon.classList.remove('bi-heart');
          icon.classList.add('bi-heart-fill');
        }
      } else {
        otherBtn.classList.remove('active');
        const icon = otherBtn.querySelector('i');
        if (icon) {
          icon.classList.remove('bi-heart-fill');
          icon.classList.add('bi-heart');
        }
      }
    });

  } catch (err) {
    console.error('Error toggling favorite:', err);
    showNotification('Error updating favorites. Are you logged in?', 'danger');
    
    // Revert UI on error
    if (wasActive) {
      btn.classList.add('active');
      if (heartIcon) {
        heartIcon.classList.remove('bi-heart');
        heartIcon.classList.add('bi-heart-fill');
      }
    } else {
      btn.classList.remove('active');
      if (heartIcon) {
        heartIcon.classList.remove('bi-heart-fill');
        heartIcon.classList.add('bi-heart');
      }
    }
  }
};

// Escape HTML to safely insert into innerHTML
function escapeHtml(unsafe) {
  if (unsafe === null || unsafe === undefined) return '';
  return String(unsafe).replace(/[&<>'"]/g, function (m) { return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]); });
}

let productModalHandlerBound = false;

// Handlers for the new TSX-like markup
function setupShoppingListHandlers() {
  // remove buttons
  document.querySelectorAll('.remove-item-btn').forEach(btn => btn.addEventListener('click', async (e) => {
    const name = btn.getAttribute('data-name') || btn.getAttribute('data-id'); if (!name) return;
    const r = await apiPostJson('/shopping-list/remove', { item: name }); if (r && r.success) { showNotification('Item removed', 'info'); refreshShoppingListUI(); } else showNotification('Could not remove item', 'danger');
  }));

  // checkbox toggles
  document.querySelectorAll('.checkbox-item').forEach(cb => cb.addEventListener('change', () => {
    const row = cb.closest('.item-row'); if (!row) return; if (cb.checked) row.classList.add('purchased'); else row.classList.remove('purchased'); debounceSaveOrder();
  }));
}

// Claim buttons: attach handlers to claim featured deals and add to user's shopping list
function setupClaimButtons() {
  document.querySelectorAll('.claim-deal-btn').forEach(btn => btn.addEventListener('click', async (e) => {
    e.stopPropagation(); // Prevent card click redirect
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

    // Send both price (discounted) and original_price; backend will choose based on offer type
    const discounted_price_val = Number(String(price).replace(/[^0-9.]/g, '')) || 0;
    const original_price_val = Number(String(originalPrice).replace(/[^0-9.]/g, '')) || discounted_price_val;

    let offerPayload = null;
    try { if (offerJson) offerPayload = JSON.parse(offerJson); } catch (err) { offerPayload = null; }
    if (!offerPayload && offerType === 'buyXgetY' && offerX && offerY) {
      const xNum = parseInt(offerX, 10) || 0;
      const yNum = parseInt(offerY, 10) || 0;
      if (xNum && yNum) offerPayload = { type: 'buyXgetY', x: xNum, y: yNum };
    }
    if (!offerPayload && offerStr) {
      const m = offerStr.match(/(\d+)\s*\+\s*(\d+)/);
      if (m) offerPayload = { type: 'buyXgetY', x: parseInt(m[1], 10) || 0, y: parseInt(m[2], 10) || 0 };
    }

    // Instead of claiming directly, show list selector
    const item = {
      name: title,
      price: discounted_price_val || original_price_val,
      price_val: discounted_price_val || original_price_val,
      image: image,
      offer: offerPayload || offerStr || null,
      deal_id: id
    };

    try {
      const res = await addItemToShoppingList(item);
      if (res && res.deferred) {
        // List selector will be shown
        return;
      }
      if (res && res.success) {
        showNotification('Deal added to your list', 'success');
        refreshShoppingListUI();
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

// Global function to handle add to cart button clicks
window.handleAddToCart = async function (event, name, price, image, store) {
  if (event) {
    event.stopPropagation();
    if (event.preventDefault) event.preventDefault();
  }

  // Support both (event, name, price, image, store) and (event, element)
  let item;
  if (name instanceof HTMLElement) {
    const btn = name;
    // Check if we are in store selection mode (e.g. Compare Prices page)
    const productCard = btn.closest('.product-card');
    let storeSelected = false; // Flag to track if we handled the store selection logic

    if (productCard) {
        const hasStoreOptions = productCard.querySelector('.store-item');
        if (hasStoreOptions) {
            const selectedStoreItem = productCard.querySelector('.store-item.selected');
            if (!selectedStoreItem) {
                showNotification('Please select a store first', 'warning');
                return;
            }
            
            // Extract data with selected store overrides
            const itemName = btn.getAttribute('data-name') || btn.getAttribute('data-title') || 'Item';
            // Prefer store-specific price, fallback to base price
            let itemPrice = selectedStoreItem.getAttribute('data-store-price') || btn.getAttribute('data-price') || '';
            const itemStore = selectedStoreItem.getAttribute('data-store-name') || btn.getAttribute('data-store') || '';
            const itemImage = btn.getAttribute('data-image') || '';
            const itemId = btn.getAttribute('data-id') || null;
            
            // Extract offer data
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
            
            if (!offerPayload && offerType === 'buyXgetY' && offerX && offerY) {
                offerPayload = { type: 'buyXgetY', x: parseInt(offerX), y: parseInt(offerY) };
            }

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
            storeSelected = true;
        }
    }
    
    // If not handled by store logic, just use the element
    if (!storeSelected) {
        item = name; 
    }
  } else {
    item = { name, price, store, image };
    const priceVal = formatPrice(price);
    if (!isNaN(priceVal) && priceVal > 0) item.price_val = priceVal;
  }

  try {
    const res = await addItemToShoppingList(item);
    if (res && res.deferred) {
      return;
    }
    if (res && (res.success || res.success === true)) {
      showNotification('Added to shopping list', 'success');
      refreshShoppingListUI();
    } else if (res && res.error) {
      showNotification(res.error, 'danger');
    } else {
      showNotification('Could not add to list', 'danger');
    }
  } catch (err) {
    console.error('Error adding to cart:', err);
    showNotification('Error adding to list. Are you logged in?', 'danger');
  }
};

// Product modal: populate modal with clicked product details and wire Add to Cart
function setupProductModalHandlers() {
  // Use event delegation for dynamically added elements. Bind the listener only once.
  if (productModalHandlerBound) return;
  productModalHandlerBound = true;

  document.addEventListener('click', async (e) => {
    const target = e.target;
    if (!target) return;

    // View Details button clicked: try to fetch full product details from server by id or name
    const viewBtn = target.closest('.view-details-btn, .btn-premium-view');
    if (viewBtn) {
      const pid = viewBtn.getAttribute('data-id') || viewBtn.getAttribute('data-product-id') || null;
      const titleAttr = viewBtn.getAttribute('data-title') || '';
      const targetSelector = viewBtn.getAttribute('data-bs-target') || '#productModal';
      const modal = document.querySelector(targetSelector);
      if (!modal) return;

      async function populateModalFromDoc(doc) {
        const title = doc.name || doc.title || titleAttr || 'Product';
        const price = doc.price || (doc.cheapest && doc.cheapest.price) || '';
        const store = doc.store || (doc.cheapest && doc.cheapest.store) || (doc.stores && doc.stores[0] && doc.stores[0].store) || '';
        let image = doc.image || (doc.images && doc.images[0]) || viewBtn.getAttribute('data-image') || 'https://via.placeholder.com/300x200';
        // If `image` is a short id (no protocol and not an absolute path), convert to CDN URL.
        if (image && !/^https?:\/\//i.test(image) && !image.startsWith('/')) {
          image = `https://images.example.com/${image}`;
        }
        modal.querySelector('.modal-title') && (modal.querySelector('.modal-title').textContent = title + ' Details');
        const img = modal.querySelector('.modal-body img'); if (img) img.src = image;
        if (img) { img.style.width = '700px'; img.style.height = '700px'; img.style.objectFit = 'cover'; }
        const body = modal.querySelector('.modal-body');
        if (body) {
          body.querySelector('h6') && (body.querySelector('h6').textContent = title);
          // clear body info area below header and then set rich content
          // We'll try to insert structured info if available
          const infoHtml = [];
          if (doc.identification_mark) infoHtml.push(`<p><strong>Identification Mark:</strong> ${escapeHtml(doc.identification_mark)}</p>`);
          if (doc.country_of_origin) infoHtml.push(`<p><strong>Country/Place of Origin:</strong> ${escapeHtml(doc.country_of_origin)}</p>`);
          if (doc.storage_instructions) infoHtml.push(`<p><strong>Storage Instructions:</strong><br>${escapeHtml(doc.storage_instructions)}</p>`);
          if (doc.usage_instructions) infoHtml.push(`<p><strong>Usage Instructions:</strong><br>${escapeHtml(doc.usage_instructions)}</p>`);
          if (doc.origin_country) infoHtml.push(`<p><strong>Country:</strong> ${escapeHtml(doc.origin_country)}</p>`);
          if (doc.product_labeling) infoHtml.push(`<p><strong>Product Labeling:</strong> ${escapeHtml(doc.product_labeling)}</p>`);
          // fallback short summary
          if (doc.description && infoHtml.length === 0) infoHtml.push(`<p>${escapeHtml(doc.description)}</p>`);

          // Add pricing/store summary at top
          infoHtml.unshift(`<p><strong>Best Price:</strong> ${escapeHtml(price)}</p>`, `<p><strong>Available at:</strong> ${escapeHtml(store)}</p>`);

          // Replace body paragraphs (keep first h6 and image in place)
          // Remove existing paragraphs except the h6 and img
          const bodyChildren = Array.from(body.children).filter(ch => !ch.matches('img') && ch.tagName.toLowerCase() !== 'h6');
          bodyChildren.forEach(ch => ch.remove());
          const insertDiv = document.createElement('div'); insertDiv.innerHTML = infoHtml.join('\n');
          body.appendChild(insertDiv);
        }
        const addBtn = modal.querySelector('.add-to-cart-btn');
        if (addBtn) {
          addBtn.setAttribute('data-name', title);
          addBtn.setAttribute('data-price', price);
          addBtn.setAttribute('data-store', store);
          addBtn.setAttribute('data-image', image);
        }
      }

      // Try to fetch richer data from API
      (async () => {
        try {
          let url = '/api/product';
          if (pid) url += `?id=${encodeURIComponent(pid)}`; else url += `?name=${encodeURIComponent(titleAttr)}`;
          const r = await fetch(url, { credentials: 'same-origin' });
          const j = await r.json().catch(() => ({}));
          const doc = j.item || j;
          if (doc && Object.keys(doc).length) {
            await populateModalFromDoc(doc);
          } else {
            // fallback to data attrs
            const fallback = {
              name: titleAttr,
              price: viewBtn.getAttribute('data-price') || '',
              store: viewBtn.getAttribute('data-store') || '',
              image: viewBtn.getAttribute('data-image') || ''
            };
            await populateModalFromDoc(fallback);
          }
        } catch (err) {
          // fallback
          const fallback = {
            name: titleAttr,
            price: viewBtn.getAttribute('data-price') || '',
            store: viewBtn.getAttribute('data-store') || '',
            image: viewBtn.getAttribute('data-image') || ''
          };
          await populateModalFromDoc(fallback);
        }
      })();
      return;
    }

    // Add to Cart button (works both inside and outside modals)
    if (target.classList && (target.classList.contains('add-to-cart-btn') || target.closest('.add-to-cart-btn'))) {
      e.stopPropagation(); // Prevent triggering parent div's click handler
      const btn = target.classList.contains('add-to-cart-btn') ? target : target.closest('.add-to-cart-btn');
      const modalRoot = btn.closest('.modal');
      const name = btn.getAttribute('data-name') || btn.getAttribute('data-title') || (modalRoot?.querySelector('h6')?.textContent || 'Item');
      const price = btn.getAttribute('data-price') || '';
      const store = btn.getAttribute('data-store') || '';
      const image = btn.getAttribute('data-image') || (modalRoot?.querySelector('img')?.src || '');
      const item = { name, price, store, image };
      const priceVal = formatPrice(price);
      if (!isNaN(priceVal) && priceVal > 0) item.price_val = priceVal;
      try {
        const res = await addItemToShoppingList(item);
        if (res && res.deferred) {
          // List selector will be shown, don't show additional notification
          return;
        }
        if (res && (res.success || res.success === true)) {
          showNotification('Added to shopping list', 'success');
          // Close modal if button was inside one
          if (modalRoot) {
            try { const modalEl = bootstrap.Modal.getInstance(modalRoot); if (modalEl) modalEl.hide(); } catch (e) { }
          }
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

    // Add to List button in search results or elsewhere (including Compare Page)
    if (target.classList && (target.classList.contains('add-to-list-btn') || target.closest('.add-to-list-btn') ||
      target.classList.contains('btn-premium-add') || target.closest('.btn-premium-add') ||
      target.classList.contains('btn-premium-action') || target.closest('.btn-premium-action') ||
      target.classList.contains('btn-premium-hero-add') || target.closest('.btn-premium-hero-add'))) {
      e.stopPropagation(); // Stop redirection
      e.preventDefault();

      const btn = target.classList.contains('add-to-list-btn') ? target :
        (target.closest('.add-to-list-btn') || target.closest('.btn-premium-add') || target.closest('.btn-premium-action') || target);
      const name = btn.getAttribute('data-name') || btn.getAttribute('data-title') || 'Item';
      const offerJson = btn.getAttribute('data-offer-json') || '';
      const offerType = btn.getAttribute('data-offer-type') || '';
      const offerX = btn.getAttribute('data-offer-x') || '';
      const offerY = btn.getAttribute('data-offer-y') || '';
      const originalPrice = btn.getAttribute('data-original-price') || '';
      const dealId = btn.getAttribute('data-id') || btn.getAttribute('data-deal-id') || null;

      // Determine effective price and store based on selection state (if in compare page context)
      // Check if this button is inside a product card with a selected store item
      let price = btn.getAttribute('data-price') || '';
      let store = btn.getAttribute('data-store') || '';
      const productCard = btn.closest('.product-card');

      if (productCard) {
        // If we are in a compare card context, we MUST check if a store is selected
        // look for .store-item.selected inside this card
        const selectedStoreItem = productCard.querySelector('.store-item.selected');

        // If there are store options available but none selected, prompt user
        const hasStoreOptions = productCard.querySelector('.store-item');
        if (hasStoreOptions && !selectedStoreItem) {
          showNotification('Please select a store first', 'warning');
          return;
        }

        // If a store is selected, use its specific price and name
        if (selectedStoreItem) {
          store = selectedStoreItem.getAttribute('data-store-name');
          const storePrice = selectedStoreItem.getAttribute('data-store-price');
          if (storePrice) price = storePrice;
        }
      }

      const id = btn.getAttribute('data-id') || null;
      const img = btn.getAttribute('data-image') || '';

      // Build offer payload if present
      let offerPayload = null;
      try { if (offerJson) offerPayload = JSON.parse(offerJson); } catch (err) { offerPayload = null; }
      if (!offerPayload && offerType === 'buyXgetY' && offerX && offerY) {
        const xNum = parseInt(offerX, 10) || 0;
        const yNum = parseInt(offerY, 10) || 0;
        if (xNum && yNum) offerPayload = { type: 'buyXgetY', x: xNum, y: yNum };
      }

      // Create item object and show list selector
      // For multibuy deals, we MUST use the original (full) unit price for the calculation to work on the list.
      let priceToUse = price;
      if (offerPayload && (offerPayload.type === 'buyXgetY' || offerType === 'buyXgetY') && originalPrice) {
        priceToUse = originalPrice;
      }

      const item = { name, price: priceToUse, id };
      if (img) item.image = img;
      if (store) item.store = store;
      if (dealId) item.deal_id = dealId;
      if (offerPayload) item.offer = offerPayload;
      const priceVal = formatPrice(priceToUse);
      if (!isNaN(priceVal) && priceVal > 0) item.price_val = priceVal;

      // Prefer list selector when available; otherwise add to the active list directly
      try {
        const res = await addItemToShoppingList(item);
        if (res && res.deferred) {
          // List selector will be shown
          return;
        }
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

// Profile edit handlers: open modal, submit updates to server and update UI
function setupProfileEditHandlers() {
  const editBtn = document.getElementById('edit-profile-btn');
  const saveBtn = document.getElementById('save-profile-btn');
  const phoneEl = document.getElementById('profile-phone');
  const addressEl = document.getElementById('profile-address');
  const phoneInput = document.getElementById('profile-phone-input');
  const addressInput = document.getElementById('profile-address-input');
  if (!editBtn || !saveBtn) return;

  editBtn.addEventListener('click', () => {
    // populate inputs with current values
    const phoneText = phoneEl ? phoneEl.textContent.trim() : '';
    const addressText = addressEl ? addressEl.textContent.trim() : '';

    const currentPhone = phoneText.toLowerCase().includes('not provided') ? '' : phoneText;
    const currentAddress = addressText.toLowerCase().includes('not provided') ? '' : addressText;

    // Try to extract country code and phone number
    const countryCodeSelect = document.getElementById('profile-country-code');
    if (currentPhone && phoneInput && countryCodeSelect) {
      // Match common country codes
      const match = currentPhone.match(/^(\+\d{1,3})(.*)/);
      if (match) {
        countryCodeSelect.value = match[1]; // Country code
        phoneInput.value = match[2]; // Phone number
      } else {
        phoneInput.value = currentPhone;
      }
    } else if (phoneInput) {
      phoneInput.value = '';
    }

    if (addressInput) addressInput.value = currentAddress;
  });

  saveBtn.addEventListener('click', async () => {
    const countryCodeSelect = document.getElementById('profile-country-code');
    const countryCode = countryCodeSelect ? countryCodeSelect.value : '+43';
    const phoneNumber = phoneInput ? phoneInput.value.trim() : '';
    const phone = phoneNumber ? countryCode + phoneNumber : '';
    const address = addressInput ? addressInput.value.trim() : '';
    try {
      const res = await fetch('/profile/update', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ phone, address }) });
      const j = await res.json().catch(() => ({}));
      if (res.ok && j && j.success) {
        // update UI
        if (phoneEl) phoneEl.textContent = phone || 'Not provided';
        if (addressEl) addressEl.textContent = address || 'Not provided';
        // hide modal
        try { const modal = bootstrap.Modal.getInstance(document.getElementById('profileModal')); if (modal) modal.hide(); } catch (e) { }
        showNotification('Profile updated', 'success');
      } else {
        showNotification(j.error || 'Could not update profile', 'danger');
      }
    } catch (err) {
      showNotification('Server error updating profile', 'danger');
    }
  });
}

// Featured Deals search: filter products locally on the page
function setupFeaturedDealsSearch() {
  const input = document.getElementById('featured-search-input');
  const btn = document.getElementById('featured-search-btn');
  // Find the products grid on Featured Deals page (look for grid with products that have data-name)
  let dealsGrid = document.getElementById('products-grid');
  // If on home page, look for the main products grid
  if (!dealsGrid) {
    dealsGrid = document.querySelector('section.container .row.g-4');
  }

  const applyFiltersBtn = document.getElementById('apply-filters');
  const clearFiltersBtn = document.getElementById('clear-filters');
  const minPrice = document.getElementById('min-price');
  const maxPrice = document.getElementById('max-price');
  const sortOrder = document.getElementById('sort-order');
  const categorySelect = document.getElementById('category-filter');
  const storeSelect = document.getElementById('store-filter');
  const categoryChipsRow = document.querySelector('.category-chip-row');

  if (!input || !dealsGrid) return;

  let allDeals = [];

  const collectAllDeals = () => {
    allDeals = Array.from(dealsGrid.querySelectorAll('[data-name]'));

    // Populate store filter dropdown
    if (storeSelect) {
      const stores = new Set();
      allDeals.forEach(col => {
        const s = col.getAttribute('data-store');
        if (s) stores.add(s);
      });

      // Preserve "All Stores"
      storeSelect.innerHTML = '<option value="">All Stores</option>';
      Array.from(stores).sort().forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.toLowerCase();
        opt.textContent = s.charAt(0).toUpperCase() + s.slice(1);
        storeSelect.appendChild(opt);
      });
    }
  };

  const parsePrice = (v) => {
    const n = Number(String(v || '').replace(/[^0-9.\-]/g, ''));
    return isNaN(n) ? 0 : n;
  };

  const doSearch = () => {
    const q = input.value.trim().toLowerCase();
    const minVal = minPrice ? parseFloat(minPrice.value) : NaN;
    const maxVal = maxPrice ? parseFloat(maxPrice.value) : NaN;
    const sortVal = sortOrder ? sortOrder.value : 'price-asc';
    const activeChip = categoryChipsRow ? categoryChipsRow.querySelector('.category-chip.active') : null;
    const chipVal = activeChip ? (activeChip.dataset.categoryChip || '').trim() : '';
    const selectCategoryVal = categorySelect ? (categorySelect.value || '').trim() : '';
    const categoryVal = chipVal || selectCategoryVal;
    const storeVal = storeSelect ? (storeSelect.value || '').trim().toLowerCase() : '';

    const visible = [];
    allDeals.forEach(col => {
      if (!col) return;

      const productName = (col.getAttribute('data-name') || '').toLowerCase();
      const priceText = col.getAttribute('data-price') || '0';
      const price = parsePrice(priceText);
      const categoryAttr = (col.getAttribute('data-category') || '').toLowerCase();
      const storeAttr = (col.getAttribute('data-store') || '').toLowerCase();

      // search match
      let searchMatch = true;
      if (q) {
        searchMatch = productName.includes(q);
      }

      // category match
      let categoryMatch = true;
      if (categoryVal) {
        categoryMatch = categoryAttr === categoryVal.toLowerCase();
      }

      // price match
      let priceMatch = true;
      if (!isNaN(minVal)) priceMatch = priceMatch && (price >= minVal);
      if (!isNaN(maxVal)) priceMatch = priceMatch && (price <= maxVal);

      // store match
      let storeMatch = true;
      if (storeVal) {
        storeMatch = storeAttr === storeVal;
      }

      if (searchMatch && priceMatch && categoryMatch && storeMatch) {
        col.style.display = '';
        visible.push({ col, price, name: productName });
      } else {
        col.style.display = 'none';
      }
    });

    // sort
    if (visible.length) {
      if (sortVal === 'price-asc' || sortVal === 'price-desc') {
        visible.sort((a, b) => sortVal === 'price-asc' ? a.price - b.price : b.price - a.price);
      } else if (sortVal === 'name-asc' || sortVal === 'name-desc') {
        visible.sort((a, b) => sortVal === 'name-asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name));
      }
      visible.forEach(v => dealsGrid.appendChild(v.col));
    }
  };

  // Handle server-side navigation for search/filters
  const handleServerDealsSearch = () => {
    const q = input.value.trim();
    const activeChip = categoryChipsRow ? categoryChipsRow.querySelector('.category-chip.active') : null;
    const categoryVal = activeChip ? (activeChip.dataset.categoryChip || '').trim() : '';

    const params = new URLSearchParams();
    if (q) params.set('search', q);
    if (categoryVal) params.set('category', categoryVal);
    params.set('page', '1'); // always reset to first page on new search

    window.location.href = window.location.pathname + '?' + params.toString();
  };

  const clearFeaturedFilters = () => {
    window.location.href = window.location.pathname;
  };

  collectAllDeals();
  input && input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleServerDealsSearch();
    }
  });
  input && input.addEventListener('input', () => { doSearch(); });
  if (applyFiltersBtn) applyFiltersBtn.addEventListener('click', (e) => { e.preventDefault(); handleServerDealsSearch(); });
  if (clearFiltersBtn) clearFiltersBtn.addEventListener('click', (e) => { e.preventDefault(); clearFeaturedFilters(); });
  if (categorySelect) categorySelect.addEventListener('change', () => {
    handleServerDealsSearch();
  });
  if (storeSelect) storeSelect.addEventListener('change', () => {
    doSearch(); // Store filtering remains client-side for now as it's not in the route query yet
  });
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

function setupShoppingListInteractions() {
  const list = document.getElementById('shopping-list') || document.querySelector('.list-rows'); if (!list) return;

  // drag/drop
  let dragSrc = null;
  list.addEventListener('dragstart', (e) => { const r = e.target.closest('.item-row'); if (!r) return; dragSrc = r; e.dataTransfer.effectAllowed = 'move'; });
  list.addEventListener('dragover', (e) => e.preventDefault());
  list.addEventListener('drop', (e) => { e.preventDefault(); const target = e.target.closest('.item-row'); if (!target || !dragSrc || target === dragSrc) return; list.insertBefore(dragSrc, target); postCurrentListOrder(); });

  // clear purchased
  document.getElementById('clear-purchased')?.addEventListener('click', () => {
    const rows = Array.from(list.querySelectorAll('.item-row.purchased'));
    rows.forEach(r => { const name = r.getAttribute('data-name'); apiPostJson('/shopping-list/remove', { item: name }).then(res => { if (res && res.success) refreshShoppingListUI(); }); });
  });

  // clear all
  document.getElementById('clear-all')?.addEventListener('click', () => {
    if (!confirm('Clear all items from your shopping list?')) return;
    apiPostJson('/shopping-list/clear', {}).then(res => { if (res && res.success) { showNotification('All items cleared', 'info'); refreshShoppingListUI(); } else showNotification('Could not clear items', 'danger'); }).catch(() => showNotification('Server error', 'danger'));
  });

  // save order
  document.getElementById('save-order')?.addEventListener('click', () => { postCurrentListOrder().then(r => { if (r && r.success) showNotification('Order saved', 'success'); }); });

  // quantity increment/decrement handling (delegated)
  list.addEventListener('click', (e) => {
    const inc = e.target.closest('.qty-incr');
    const dec = e.target.closest('.qty-decr');
    if (inc || dec) {
      const btn = inc || dec;
      const row = btn.closest('.item-row'); if (!row) return;
      const badge = row.querySelector('.qty-badge');
      let qty = Number(row.getAttribute('data-qty') || 1) || 1;
      qty = qty + (inc ? 1 : -1);
      if (qty < 1) qty = 1;
      row.setAttribute('data-qty', String(qty));
      if (badge) badge.textContent = String(qty);
      // update per-row displayed price using effective unit price
      const unit = formatPrice(row.getAttribute('data-price') || (row.querySelector('.item-price')?.textContent || '0'));
      const offerObj = parseOfferFromRow(row);
      const effectiveUnit = effectiveUnitPrice(unit, offerObj);
      const priceEl = row.querySelector('.item-price');
      if (priceEl) priceEl.textContent = `€${(effectiveUnit * qty).toFixed(2)}`;
      debounceSaveOrder();
      computeTotals();
    }
  });

  computeTotals();
}

async function postCurrentListOrder() {
  const rows = Array.from(document.querySelectorAll('.item-row'));
  const items = rows.map(r => ({
    name: r.getAttribute('data-name'),
    purchased: r.classList.contains('purchased'),
    qty: Number(r.getAttribute('data-qty') || 1),
    // price here is the unit price (not total); server will persist this value
    price: formatPrice(r.getAttribute('data-price') || (r.querySelector('.item-price')?.textContent || '0'))
  }));
  return apiPostJson('/shopping-list/update', { items });
}

let _saveTimer = null; function debounceSaveOrder(delay = 700) { if (_saveTimer) clearTimeout(_saveTimer); _saveTimer = setTimeout(() => postCurrentListOrder(), delay); }

const parseOfferFromRow = (row) => {
  const offerJson = row.getAttribute('data-offer-json');
  if (offerJson) {
    try { const obj = JSON.parse(offerJson); if (obj && obj.type) return obj; } catch (e) { }
  }
  const offerType = row.getAttribute('data-offer-type') || '';
  const ox = parseInt(row.getAttribute('data-offer-x') || '0', 10) || 0;
  const oy = parseInt(row.getAttribute('data-offer-y') || '0', 10) || 0;
  if (offerType === 'buyXgetY' && ox && oy) return { type: 'buyXgetY', x: ox, y: oy };

  const offerStr = row.getAttribute('data-offer') || '';
  const m = offerStr.match(/(\d+)\s*\+\s*(\d+)/);
  if (m) return { type: 'buyXgetY', x: parseInt(m[1], 10) || 0, y: parseInt(m[2], 10) || 0 };
  return null;
};

function effectiveUnitPrice(basePrice, offerObj) {
  if (!offerObj || offerObj.type !== 'buyXgetY') return basePrice;
  const x = parseInt(offerObj.x || 0, 10) || 0;
  const y = parseInt(offerObj.y || 0, 10) || 0;
  if (!x || !y) return basePrice;
  return (x * basePrice) / (x + y);
}

// computeTotals: sum effective unit price * qty (planned vs remaining)
function computeTotals() {
  const rows = Array.from(document.querySelectorAll('.item-row'));
  let planned = 0;
  let remaining = 0;
  let completed = 0;

  rows.forEach((row) => {
    const baseUnit = formatPrice(row.getAttribute('data-price') || (row.querySelector('.item-price')?.textContent || '0'));
    const qty = Number(row.getAttribute('data-qty') || 1);
    const offerObj = parseOfferFromRow(row);
    const effective = effectiveUnitPrice(baseUnit, offerObj);
    const itemTotal = effective * qty;

    planned += itemTotal;
    if (row.classList.contains('completed')) {
      completed += 1;
    } else {
      remaining += itemTotal;
    }
  });

  const plannedEl = document.getElementById('planned-total'); if (plannedEl) plannedEl.textContent = `€${planned.toFixed(2)}`;
  const remainingEl = document.getElementById('remaining-total'); if (remainingEl) remainingEl.textContent = `€${remaining.toFixed(2)}`;
  const legacyTotalEl = document.getElementById('total-value'); if (legacyTotalEl) legacyTotalEl.textContent = `€${planned.toFixed(2)}`;
  const legacyPriceEl = document.getElementById('total-price'); if (legacyPriceEl) legacyPriceEl.textContent = planned.toFixed(2);
  const completedEl = document.getElementById('completed-count'); if (completedEl) completedEl.textContent = completed;
}

// minimal cart counter kept for compatibility
class CartCounter {
  constructor() { this.cartItems = []; this.loadFromStorage(); this.updateDisplay(); } addItem(name, price) { const it = { name, price, id: Date.now() }; this.cartItems.push(it); this.saveToStorage(); this.updateDisplay(); return it.id; } removeItem(id) { this.cartItems = this.cartItems.filter(i => i.id !== id); this.saveToStorage(); this.updateDisplay(); } getCount() { return this.cartItems.length; } getTotal() { return this.cartItems.reduce((s, i) => s + Number(i.price || 0), 0); } clearCart() { this.cartItems = []; this.saveToStorage(); this.updateDisplay(); } updateDisplay() { const b = document.getElementById('cart-counter'); if (b) { b.textContent = this.getCount(); b.style.display = this.getCount() > 0 ? 'inline-block' : 'none'; } const t = document.getElementById('cart-total'); if (t) t.textContent = `€${this.getTotal().toFixed(2)}`; } saveToStorage() { localStorage.setItem('smartGroceryCart', JSON.stringify(this.cartItems)); } loadFromStorage() { try { this.cartItems = JSON.parse(localStorage.getItem('smartGroceryCart')) || [] } catch (e) { this.cartItems = [] } }
}
const cart = new CartCounter();

// Legacy toggleFavorite removed (duplicate)

// Alias for home page compatibility
const favoriteProduct = (event, productId) => {
  event.stopPropagation();
  event.preventDefault();
  const btn = event.target.closest('.favorite-btn');

  // If quickFavorite exists (on home page), use that instead
  if (typeof quickFavorite !== 'undefined') {
    quickFavorite(event, productId, btn);
  } else if (btn) {
    if (window.toggleFavorite) window.toggleFavorite(event, productId, btn);
  }
};

window.smartGrocery = { showNotification, formatPrice, cart, toggleFavorite: window.toggleFavorite };
