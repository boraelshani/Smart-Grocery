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
