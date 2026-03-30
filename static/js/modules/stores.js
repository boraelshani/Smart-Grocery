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
