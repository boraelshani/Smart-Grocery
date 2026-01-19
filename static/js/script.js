// ===============================================
// SMART GROCERY FRONTEND JAVASCRIPT
// Handles user interactions: shopping lists, favorites, filtering, search
// ===============================================

document.addEventListener('DOMContentLoaded', () => {
  // INITIALIZE: Run all setup functions when page loads
  initializeBootstrapComponents();
  setupNavbarScroll();
  setupSearchFunctionality();
  setupShoppingListHandlers();
  setupShoppingListInteractions();
  setupClaimButtons();
  setupProductModalHandlers();
  setupStoreSuggestions();
  setupProfileEditHandlers();
  setupFeaturedDealsSearch();
  setupCompareHandlers();
  setupCompareFilters();
  setupPaginationSmoothTransition();
  setupLogoutConfirmation();

  // Always hide product modal on page load (prevents unwanted popup on back)
  const productModalEl = document.getElementById('productModal');
  if (productModalEl) {
    const modalInstance = bootstrap.Modal.getOrCreateInstance(productModalEl);
    modalInstance.hide();
  }
});

// Hide product modal on browser back navigation (prevents unwanted popup)
window.addEventListener('pageshow', function (event) {
  const productModalEl = document.getElementById('productModal');
  if (productModalEl) {
    const modalInstance = bootstrap.Modal.getOrCreateInstance(productModalEl);
    modalInstance.hide();
  }
});

function setupNavbarScroll() {
  const nav = document.querySelector('.navbar-premium');
  if (!nav) return;

  const handleScroll = () => {
    if (window.scrollY > 50) {
      nav.classList.add('scrolled');
    } else {
      nav.classList.remove('scrolled');
    }
  };

  window.addEventListener('scroll', handleScroll);
  handleScroll(); // Initial check
}

// BOOTSTRAP: Activate tooltip popovers
function initializeBootstrapComponents() {
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (tooltipTriggerEl) { return new bootstrap.Tooltip(tooltipTriggerEl); });
}

function setupLogoutConfirmation() {
  // Use a capture phase listener on the document to intercept logout clicks
  document.addEventListener('click', (e) => {
    // If the click is inside our custom logout modal, let it happen naturally
    if (e.target.closest('#customLogoutModal')) {
      return;
    }

    const logoutBtn = e.target.closest('a[href*="/logout"]');
    if (logoutBtn) {
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();
      
      showLogoutModal(logoutBtn.href);
      return false;
    }
  }, true); 
}

function showLogoutModal(logoutUrl) {
  // Check if modal already exists
  let modalElem = document.getElementById('customLogoutModal');
  if (!modalElem) {
    const modalHtml = `
      <div class="modal fade" id="customLogoutModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered modal-sm">
          <div class="modal-content border-0 shadow-lg" style="border-radius: 20px;">
            <div class="modal-body text-center p-4">
              <div class="mb-3">
                <i class="bi bi-door-open text-danger" style="font-size: 3rem;"></i>
              </div>
              <h5 class="fw-bold mb-2">Wait! Logging out?</h5>
              <p class="text-muted small mb-4">Are you sure you want to end your session?</p>
              <div class="d-grid gap-2">
                <a href="${logoutUrl}" class="btn btn-danger rounded-pill fw-bold py-2">Yes, Log Out</a>
                <button type="button" class="btn btn-light rounded-pill fw-semibold py-2" data-bs-dismiss="modal">Stay Logged In</button>
              </div>
            </div>
          </div>
        </div>
      </div>`;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    modalElem = document.getElementById('customLogoutModal');
  } else {
    // Update the URL in case it's different
    const confirmBtn = modalElem.querySelector('a.btn-danger');
    if (confirmBtn) confirmBtn.href = logoutUrl;
  }

  const modal = new bootstrap.Modal(modalElem);
  modal.show();
}

// Compare page: sort the rendered store list items by numeric price (client-side)
function setupCompareHandlers() {
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.sort-stores-btn');
    if (!btn) return;
    const card = btn.closest('.card');
    if (!card) return;
    const list = card.querySelector('.list-group');
    if (!list) return;
    const items = Array.from(list.querySelectorAll('li'));
    function parsePriceFromText(text) {
      if (!text) return Number.POSITIVE_INFINITY;
      const m = String(text).match(/\d+[\d,.]*/);
      if (!m) return Number.POSITIVE_INFINITY;
      const cleaned = m[0].replace(/,/g, '');
      const n = Number(cleaned);
      return isNaN(n) ? Number.POSITIVE_INFINITY : n;
    }
    // map items to [node, price]
    const mapped = items.map(li => {
      const priceText = li.textContent || li.innerText || '';
      return { node: li, price: parsePriceFromText(priceText) };
    });
    mapped.sort((a, b) => a.price - b.price);
    // clear existing list and append sorted nodes
    list.innerHTML = '';
    mapped.forEach((m, idx) => {
      // add a 'Best Price' badge to the first item
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
        const existing = m.node.querySelector('.best-price-badge'); if (existing) existing.remove();
      }
      list.appendChild(m.node);
    });
  });
}

// Client-side filters, search and sorting for the Compare page
// Store selection mechanic for compare page
document.addEventListener('click', function (e) {
  // If clicking the redirection button, don't trigger selection
  if (e.target.closest('.btn-go-store')) {
    e.stopPropagation();
    return;
  }

  const storeItem = e.target.closest('.store-item');
  if (storeItem) {
    const productCard = storeItem.closest('.product-card') || storeItem.closest('.card');
    if (productCard) {
      const isAlreadySelected = storeItem.classList.contains('selected');

      // GLOBAL RESET: Deselect ANY store-item on the entire page first
      document.querySelectorAll('.store-item.selected').forEach(selectedItem => {
        if (selectedItem === storeItem) return; // Skip current if we're just toggling

        const otherCard = selectedItem.closest('.product-card') || selectedItem.closest('.card');
        selectedItem.classList.remove('selected');

        if (otherCard) {
          const otherAddBtn = otherCard.querySelector('.btn-premium-add');
          const otherPriceBadge = otherCard.querySelector('.price-badge');

          if (otherAddBtn) {
            otherAddBtn.dataset.price = otherAddBtn.getAttribute('data-initial-price') || '';
            otherAddBtn.dataset.store = '';
          }
          if (otherPriceBadge) {
            const initialPrice = otherAddBtn ? otherAddBtn.getAttribute('data-initial-price') : '';
            if (initialPrice) {
              const inner = otherPriceBadge.querySelector('i') ? '<i class="bi bi-tag-fill"></i> ' : '';
              otherPriceBadge.innerHTML = inner + '€' + initialPrice;
            }
          }
        }
      });

      // Local Card Reset (standard toggle behavior)
      const allLocalStoreItems = productCard.querySelectorAll('.store-item');
      allLocalStoreItems.forEach(item => item.classList.remove('selected'));

      const addBtn = productCard.querySelector('.btn-premium-add');
      const priceBadge = productCard.querySelector('.price-badge');

      if (isAlreadySelected) {
        // Deselect current
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
      } else {
        // Select new
        storeItem.classList.add('selected');
        if (addBtn) {
          addBtn.dataset.price = storeItem.dataset.storePrice;
          addBtn.dataset.store = storeItem.dataset.storeName;
        }
        if (priceBadge) {
          const inner = priceBadge.querySelector('i') ? '<i class="bi bi-tag-fill"></i> ' : '';
          priceBadge.innerHTML = inner + '€' + storeItem.dataset.storePrice;
          priceBadge.style.transform = 'scale(1.1)';
          setTimeout(() => { priceBadge.style.transform = 'scale(1)'; }, 200);
        }
      }
    }
    e.preventDefault();
    e.stopPropagation();
  }
});
function setupCompareFilters() {
  const productsRow = document.getElementById('products-grid') || document.querySelector('section.container .row.g-4');
  if (!productsRow) return;

  const searchInput = document.getElementById('product-search-input');
  const searchBtn = document.getElementById('product-search-btn');
  const storeSelect = document.getElementById('store-filter');
  const categorySelect = document.getElementById('category-filter');
  const categoryChipsRow = document.querySelector('.category-chip-row');
  const minInput = document.getElementById('min-price');
  const maxInput = document.getElementById('max-price');
  const sortSelect = document.getElementById('sort-order');
  const applyBtn = document.getElementById('apply-filters');
  const clearBtn = document.getElementById('clear-filters');

  // Store all original product cards
  let allProducts = [];

  // collect available stores from rendered cards
  const collectStoresAndCategories = () => {
    const productDivs = Array.from(productsRow.querySelectorAll('[data-stores]'));
    allProducts = productDivs;
    const set = new Set();
    productDivs.forEach(div => {
      try {
        const stores = JSON.parse(div.getAttribute('data-stores') || '[]');
        stores.forEach(s => { if (s && (s.store || s.name)) set.add((s.store || s.name).trim()); });
      } catch (e) { }
    });
    if (storeSelect) {
      const existing = new Set(Array.from(storeSelect.options).map(o => o.value));
      set.forEach(name => { if (!existing.has(name)) { const opt = document.createElement('option'); opt.value = name; opt.textContent = name; storeSelect.appendChild(opt); } });
    }
    // Leave categories as rendered by the server so chips stay visible and active highlighting remains.
  };

  const parsePrice = (v) => { if (v === null || v === undefined || v === '') return Number.POSITIVE_INFINITY; const n = Number(String(v).toString().replace(/[^0-9.\-]/g, '')); return isNaN(n) ? Number.POSITIVE_INFINITY : n; };

  const applyFilters = () => {
    const searchVal = searchInput ? searchInput.value.trim().toLowerCase() : '';
    const activeChip = categoryChipsRow ? categoryChipsRow.querySelector('.category-chip.active') : null;
    const chipVal = activeChip ? (activeChip.dataset.categoryChip || '').trim() : '';
    const selectCategoryVal = categorySelect ? (categorySelect.value || '').trim() : '';
    const categoryVal = chipVal || selectCategoryVal;
    const storeVal = storeSelect ? storeSelect.value : '';
    const minVal = minInput ? parseFloat(minInput.value) : NaN;
    const maxVal = maxInput ? parseFloat(maxInput.value) : NaN;
    const sortVal = sortSelect ? sortSelect.value : 'price-asc';

    // determine visible products
    const visible = [];
    allProducts.forEach(col => {
      if (!col) return;
      const priceAttr = col.getAttribute('data-price') || '';
      const price = parsePrice(priceAttr);
      const productName = (col.getAttribute('data-name') || '').toLowerCase();

      // search match
      let searchMatch = true;
      if (searchVal) {
        searchMatch = productName.includes(searchVal);
      }

      // store match
      let storeMatch = true;
      if (storeVal) {
        try {
          const stores = JSON.parse(col.getAttribute('data-stores') || '[]');
          storeMatch = stores.some(s => { const n = (s.store || s.name || '').toString().trim(); return n.toLowerCase() === storeVal.toLowerCase(); });
        } catch (e) { storeMatch = false; }
      }

      // category match
      let categoryMatch = true;
      if (categoryVal) {
        const cat = (col.getAttribute('data-category') || '').trim().toLowerCase();
        categoryMatch = cat === categoryVal.toLowerCase();
      }

      // price range match
      let priceMatch = true;
      if (!isNaN(minVal)) priceMatch = priceMatch && (price >= minVal);
      if (!isNaN(maxVal)) priceMatch = priceMatch && (price <= maxVal);

      if (searchMatch && storeMatch && categoryMatch && priceMatch) {
        col.style.display = '';
        visible.push({ col, price, name: productName });
      } else {
        col.style.display = 'none';
      }
    });

    // sort visible columns
    if (visible.length) {
      if (sortVal === 'price-asc' || sortVal === 'price-desc') {
        visible.sort((a, b) => sortVal === 'price-asc' ? a.price - b.price : b.price - a.price);
      } else if (sortVal === 'name-asc' || sortVal === 'name-desc') {
        visible.sort((a, b) => sortVal === 'name-asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name));
      }
      // re-append in sorted order
      visible.forEach(v => productsRow.appendChild(v.col));
    }

    // Update active filter badges
    updateActiveFilters(searchVal, categoryVal, storeVal, minVal, maxVal);
  };

  const activeFiltersDiv = document.getElementById('active-filters');

  const updateActiveFilters = (searchVal, categoryVal, storeVal, minVal, maxVal) => {
    if (!activeFiltersDiv) return;
    activeFiltersDiv.innerHTML = '';
    let hasFilters = false;

    const createFilterBadge = (text, onRemove) => {
      const badge = document.createElement('span');
      badge.className = 'badge bg-primary d-flex align-items-center gap-1 p-2';
      badge.style.borderRadius = '20px';
      badge.innerHTML = text + ' <i class="bi bi-x-circle ms-1" style="cursor:pointer;"></i>';
      badge.querySelector('i').onclick = onRemove;
      return badge;
    };

    if (searchVal) {
      hasFilters = true;
      activeFiltersDiv.appendChild(createFilterBadge('Search: ' + searchVal, () => {
        if (searchInput) { searchInput.value = ''; applyFilters(); }
      }));
    }

    if (categoryVal) {
      hasFilters = true;
      activeFiltersDiv.appendChild(createFilterBadge('Category: ' + categoryVal, () => {
        if (categoryChipsRow) categoryChipsRow.querySelectorAll('.category-chip').forEach(ch => ch.classList.remove('active'));
        if (categorySelect) categorySelect.value = '';
        applyFilters();
      }));
    }

    if (storeVal) {
      hasFilters = true;
      activeFiltersDiv.appendChild(createFilterBadge('Store: ' + storeVal, () => {
        if (storeSelect) { storeSelect.value = ''; applyFilters(); }
      }));
    }

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

  const clearFilters = () => {
    if (searchInput) searchInput.value = '';
    if (storeSelect) storeSelect.value = '';
    if (categorySelect) categorySelect.value = '';
    if (categoryChipsRow) categoryChipsRow.querySelectorAll('.category-chip').forEach(ch => ch.classList.remove('active'));
    if (minInput) minInput.value = '';
    if (maxInput) maxInput.value = '';
    if (sortSelect) sortSelect.value = 'price-asc';
    allProducts.forEach(col => { if (col) col.style.display = ''; });
  };

  collectStoresAndCategories();

  // Add search event listeners to apply filters on search
  searchInput && searchInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); applyFilters(); } });
  searchBtn && searchBtn.addEventListener('click', (e) => { e.preventDefault(); applyFilters(); });
  searchInput && searchInput.addEventListener('input', () => { applyFilters(); });

  applyBtn && applyBtn.addEventListener('click', (e) => { e.preventDefault(); applyFilters(); });
  clearBtn && clearBtn.addEventListener('click', (e) => { e.preventDefault(); clearFilters(); });
  categorySelect && categorySelect.addEventListener('change', () => {
    if (categoryChipsRow) categoryChipsRow.querySelectorAll('.category-chip').forEach(ch => ch.classList.remove('active'));
    applyFilters();
  });
  storeSelect && storeSelect.addEventListener('change', () => { applyFilters(); });
  minInput && minInput.addEventListener('change', () => { applyFilters(); });
  maxInput && maxInput.addEventListener('change', () => { applyFilters(); });
  sortSelect && sortSelect.addEventListener('change', () => { applyFilters(); });
  if (categoryChipsRow) {
    categoryChipsRow.addEventListener('click', (e) => {
      const btn = e.target.closest('.category-chip');
      if (!btn) return;
      categoryChipsRow.querySelectorAll('.category-chip').forEach(ch => ch.classList.remove('active'));
      btn.classList.add('active');
      if (categorySelect) categorySelect.value = '';
      applyFilters();
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
function setupSearchFunctionality() {
  const input = document.getElementById('home-search-input');
  const btn = document.getElementById('home-search-btn');
  const resultsSection = document.getElementById('search-results-section');
  const resultsContainer = document.getElementById('search-results');
  const productsGrid = document.getElementById('products-grid');
  const applyFiltersBtn = document.getElementById('apply-filters');
  const clearFiltersBtn = document.getElementById('clear-filters');
  const storeFilter = document.getElementById('store-filter');
  const minPrice = document.getElementById('min-price');
  const maxPrice = document.getElementById('max-price');
  const sortOrder = document.getElementById('sort-order');

  let allProducts = [];

  // collect all initial products
  const collectAllProducts = () => {
    if (!productsGrid) return;
    allProducts = Array.from(productsGrid.querySelectorAll('[class*="col"]'));
  };

  async function doSearch() {
    if (!input) return;
    const q = input.value.trim();
    if (!q) { showNotification('Please enter a search term', 'info'); return; }
    try {
      const res = await fetch(`/api/search-products?q=${encodeURIComponent(q)}`, { credentials: 'same-origin' });
      const data = await res.json().catch(() => ({}));
      const items = data.items || [];
      // render results
      if (!resultsSection || !resultsContainer) return;
      resultsContainer.innerHTML = '';
      if (!items.length) {
        resultsContainer.innerHTML = `<div class="col-12"><p class="text-muted">No matching products found.</p></div>`;
        resultsSection.style.display = 'block';
        return;
      }
      items.forEach(it => {
        const title = it.name || it.title || '';
        const price = it.price || (it.cheapest && it.cheapest.price) || '';
        const img = it.image || (it.images && it.images[0]) || 'https://via.placeholder.com/300x200';
        const store = (it.stores && it.stores[0] && it.stores[0].store) || '';
        const id = it.id || title;
        const col = document.createElement('div'); col.className = 'col-md-6 col-lg-4';
        col.innerHTML = `
              <div class="card shadow-sm">
                <img src="${img}" class="card-img-top product-thumb" alt="${title}">
            <div class="card-body">
              <h5 class="card-title">${title}</h5>
              <p class="card-text mb-1">${store}</p>
              <p class="card-text text-muted mb-2">${price}</p>
              <div class="d-flex gap-2">
                <button class="btn btn-sm btn-info view-details-btn" data-bs-toggle="modal" data-bs-target="#productModal" data-title="${escapeHtml(title)}" data-price="${escapeHtml(price)}" data-store="${escapeHtml(store)}" data-image="${escapeHtml(img)}">View Details</button>
                <button class="btn btn-sm btn-primary add-to-list-btn" data-id="${escapeHtml(id)}" data-name="${escapeHtml(title)}" data-price="${escapeHtml(price)}" data-image="${escapeHtml(img)}" data-store="${escapeHtml(store)}">Add to List</button>
              </div>
            </div>
          </div>
        `;
        resultsContainer.appendChild(col);
      });
      resultsSection.style.display = 'block';
      if (productsGrid) productsGrid.style.display = 'none';
      // after rendering, attach view-details behavior and claim buttons
      // view-details handled by setupProductModalHandlers (it binds existing elements on DOMContentLoaded), so we need to re-run attaching for newly created elements
      // attach event for view-details and claim buttons
      document.querySelectorAll('.view-details-btn').forEach(el => el.removeEventListener('click', noop));
      // small rebind: call setupProductModalHandlers to rebind handlers to new elements
      try { setupProductModalHandlers(); } catch (e) { }
    } catch (err) {
      showNotification('Search failed', 'danger');
    }
  }

  const applyHomFilters = () => {
    if (!productsGrid) return;
    const minVal = minPrice ? parseFloat(minPrice.value) : NaN;
    const maxVal = maxPrice ? parseFloat(maxPrice.value) : NaN;
    const sortVal = sortOrder ? sortOrder.value : 'price-asc';
    const parsePrice = (v) => { const n = Number(String(v || '').replace(/[^0-9.\-]/g, '')); return isNaN(n) ? 0 : n; };

    const visible = [];
    allProducts.forEach(col => {
      if (!col) return;
      const card = col.querySelector('.card');
      if (!card) return;
      const priceText = card.getAttribute('data-price') || card.querySelector('[class*="price"]')?.textContent || '0';
      const price = parsePrice(priceText);

      let priceMatch = true;
      if (!isNaN(minVal)) priceMatch = priceMatch && (price >= minVal);
      if (!isNaN(maxVal)) priceMatch = priceMatch && (price <= maxVal);

      if (priceMatch) {
        col.style.display = '';
        const name = (card.getAttribute('data-name') || card.querySelector('.card-title')?.textContent || '').toLowerCase();
        visible.push({ col, price, name });
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
      visible.forEach(v => productsGrid.appendChild(v.col));
    }
  };

  const clearHomeFilters = () => {
    if (minPrice) minPrice.value = '';
    if (maxPrice) maxPrice.value = '';
    if (sortOrder) sortOrder.value = 'price-asc';
    if (storeFilter) storeFilter.value = '';
    if (input) input.value = '';
    allProducts.forEach(col => { if (col) col.style.display = ''; });
    if (resultsSection) resultsSection.style.display = 'none';
    if (productsGrid) productsGrid.style.display = '';
  };

  collectAllProducts();
  if (btn) btn.addEventListener('click', doSearch);
  if (input) input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); doSearch(); } });
  if (applyFiltersBtn) applyFiltersBtn.addEventListener('click', (e) => { e.preventDefault(); applyHomFilters(); });
  if (clearFiltersBtn) clearFiltersBtn.addEventListener('click', (e) => { e.preventDefault(); clearHomeFilters(); });
}

function noop() { }

// Store suggestions for stores page: fetch stores and show dropdown on focus/hover
function setupStoreSuggestions() {
  const input = document.getElementById('stores-search-input');
  const grid = document.getElementById('stores-grid');
  const list = document.getElementById('store-products-list');
  const empty = document.getElementById('store-products-empty');
  const title = document.getElementById('store-products-title');
  const subtitle = document.getElementById('store-products-subtitle');
  const loading = document.getElementById('store-products-loading');
  if (!grid) {
    console.log('setupStoreSuggestions: grid element not found, skipping setup');
    return;
  }

  const cards = Array.from(grid.querySelectorAll('.store-card-btn'));
  console.log('setupStoreSuggestions: Found', cards.length, 'store cards');

  const renderProducts = (items = [], storeName = '') => {
    if (!list) return;
    list.innerHTML = '';
    if (!items.length) {
      if (empty) empty.style.display = 'block';
      list.style.display = 'none';
      if (subtitle) subtitle.textContent = 'No products or deals found for this store.';
      return;
    }
    if (empty) empty.style.display = 'none';
    list.style.display = '';
    if (subtitle) subtitle.textContent = `${items.length} item${items.length === 1 ? '' : 's'} from ${storeName}`;

    const toHtml = (item) => {
      const name = item.name || item.title || 'Product';
      const price = item.price || (item.matched_stores && item.matched_stores[0] && item.matched_stores[0].price) || '';
      // Prefer store-specific image from matched_stores, fallback to item.image
      let img = 'https://via.placeholder.com/320x200';
      if (Array.isArray(item.matched_stores) && item.matched_stores.length && item.matched_stores[0].image) {
        img = item.matched_stores[0].image;
      } else if (item.image) {
        img = item.image;
      } else if (item.images && item.images[0]) {
        img = item.images[0];
      }
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
      const source = item.source === 'featured_deal' ? 'Featured Deal' : 'Product';
      const storeBadges = storeTags.map(t => `<span class="badge bg-light text-dark border">${escapeHtml(t)}</span>`).join(' ');
      return `
        <div class="col-md-6">
          <div class="store-product-card h-100 d-flex flex-column">
            <img src="${img}" alt="${escapeHtml(name)}" class="product-image">
            <div class="p-3 d-flex flex-column flex-grow-1">
              <div class="d-flex justify-content-between align-items-start gap-2">
                <h6 class="mb-1 fw-bold">${escapeHtml(name)}</h6>
                <span class="badge ${item.source === 'featured_deal' ? 'bg-success' : 'bg-primary'}">${source}</span>
              </div>
              ${price ? `<div class="text-success fw-semibold mb-2">${escapeHtml(String(price))}</div>` : ''}
              <div class="d-flex flex-wrap gap-1 mb-2">${storeBadges}</div>
              <div class="text-muted small mt-auto">${escapeHtml(item.category || '')}</div>
            </div>
          </div>
        </div>`;
    };

    list.innerHTML = items.map(toHtml).join('');
  };

  const fetchStore = async (storeName) => {
    if (!storeName) return;
    if (loading) loading.style.display = 'inline-block';
    if (empty) empty.style.display = 'none';
    if (list) list.style.display = 'none';
    if (subtitle) subtitle.textContent = 'Loading products...';
    try {
      const res = await fetch(`/api/store/${encodeURIComponent(storeName)}/products`, { credentials: 'same-origin' });
      if (!res.ok) throw new Error('Request failed');
      const data = await res.json();
      const items = [...(data.products || [])];
      if (!items.length) {
        if (subtitle) subtitle.textContent = `No products found for ${storeName}`;
        if (empty) empty.style.display = 'block';
        return;
      }
      renderProducts(items, storeName);
    } catch (err) {
      renderProducts([], storeName);
      showNotification && showNotification('Could not load products for this store', 'danger');
    } finally {
      if (loading) loading.style.display = 'none';
    }
  };

  const activateCard = (btn) => {
    cards.forEach(c => c.classList.remove('active'));
    if (btn) btn.classList.add('active');
  };

  grid.addEventListener('click', (e) => {
    const btn = e.target.closest('.store-card-btn');
    if (!btn) return;
    e.preventDefault();
    const storeName = btn.getAttribute('data-store-name');
    console.log('Store clicked:', storeName);
    if (!storeName) return;
    activateCard(btn);
    if (title) title.textContent = storeName;
    fetchStore(storeName);
  });

  const filterGrid = (q) => {
    const query = (q || '').toLowerCase();
    let visible = 0;
    cards.forEach(btn => {
      const name = (btn.getAttribute('data-store-name') || '').toLowerCase();
      const location = (btn.textContent || '').toLowerCase();
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
      showNotification && showNotification('No stores found matching your search', 'info');
    }
  };

  input?.addEventListener('input', () => filterGrid(input.value.trim()));
  input?.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); filterGrid(input.value.trim()); } });

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
    const offerType = btn.getAttribute('data-offer-type') || '';
    const offerX = btn.getAttribute('data-offer-x') || '';
    const offerY = btn.getAttribute('data-offer-y') || '';

    // Build offer payload if present
    let offerPayload = null;
    try { if (offerJson) offerPayload = JSON.parse(offerJson); } catch (err) { }
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

    data.lists.forEach(list => {
      const itemCount = list.items ? list.items.length : 0;
      const card = document.createElement('div');
      card.className = 'list-selector-option';

      card.innerHTML = `
        <div class="card-body">
          <div class="list-selector-icon">
            <i class="bi bi-bag-heart-fill"></i>
          </div>
          <div class="list-info">
            <div class="list-title">${escapeHtml(list.name)}</div>
            <div class="list-subtitle">${itemCount} item${itemCount !== 1 ? 's' : ''}</div>
          </div>
          <div class="list-action-icon">
            <i class="bi bi-plus-lg"></i>
          </div>
        </div>
      `;

      card.addEventListener('click', () => addItemToSelectedList(list.id));
      modalBody.appendChild(card);
    });

    // Show modal
    const modalEl = document.getElementById('globalListSelectorModal');
    if (modalEl) {
      let modal = bootstrap.Modal.getInstance(modalEl);
      if (!modal) {
        modal = new bootstrap.Modal(modalEl);
      }
      modal.show();
    }
  } catch (err) {
    console.error('Error showing list selector:', err);
    showNotification('Error loading shopping lists', 'danger');
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
    item = name; // Let addItemToShoppingList/showListSelector handle the element
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
      target.classList.contains('btn-premium-hero-add') || target.closest('.btn-premium-hero-add'))) {
      e.stopPropagation(); // Stop redirection
      e.preventDefault();

      const btn = target.classList.contains('add-to-list-btn') ? target :
        (target.closest('.add-to-list-btn') || target.closest('.btn-premium-add') || target);
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

// Toggle favorite product
async function toggleFavorite(event, productId, buttonElement) {
  if (event) {
    if (event.preventDefault) event.preventDefault();
    if (event.stopPropagation) event.stopPropagation();
  }

  let finalId = productId;
  let targetBtn = buttonElement;

  if (productId instanceof HTMLElement) {
    targetBtn = productId;
    finalId = targetBtn.getAttribute('data-product-id') || targetBtn.getAttribute('data-id');
  } else if (!buttonElement && typeof productId === 'string') {
    // If only one param is passed and it's a string, it's the ID.
    // We try to find the button if possible, but the old behavior was (event, id, btn)
  }
  
  if (!finalId) return;
  
  try {
    const response = await fetch('/api/toggle-favorite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_id: finalId })
    });

    if (response.ok) {
      const data = await response.json();

      if (targetBtn) {
        const btn = typeof targetBtn === 'string' ? document.querySelector(targetBtn) : targetBtn;
        if (btn) {
          // Set active state based on server response
          if (data.is_favorite || data.action === 'added' || data.status === 'added') {
            btn.classList.add('active');
          } else {
            btn.classList.remove('active');
          }

          // Update icon
          const icon = btn.querySelector('i');
          if (icon) {
            if (btn.classList.contains('active')) {
              icon.classList.remove('bi-heart');
              icon.classList.add('bi-heart-fill');
            } else {
              icon.classList.remove('bi-heart-fill');
              icon.classList.add('bi-heart');
            }
          }

          // If on profile page and removing favorite, animate removal
          if (data && (data.action === 'removed' || data.status === 'removed')) {
            const card = btn.closest('.favorite-card');
            if (card) {
              card.style.transition = 'all 0.25s ease';
              card.style.opacity = '0';
              card.style.transform = 'translateX(-10px)';
              setTimeout(() => {
                card.remove();
              }, 250);
            }
          }
        }
      }
    } else {
      showNotification('Please login to favorite products', 'warning');
    }
  } catch (error) {
    console.error('Error toggling favorite:', error);
  }
}

                // Check if there are any favorite cards left
                const favoritesList = document.getElementById('favorites-list');
                const remainingCards = document.querySelectorAll('.favorite-card').length;

                if (remainingCards === 0 && favoritesList) {
                  // Show empty state message
                  favoritesList.innerHTML = `
                    <div class="text-center empty-favorites">
                      <i class="bi bi-heart display-6 text-muted"></i>
                      <h6 class="mt-2 mb-1 text-muted">No favorites yet</h6>
                      <p class="text-muted mb-2">Start adding products to see them here.</p>
                      <a href="/compare-prices" class="btn btn-primary btn-sm"><i class="bi bi-search"></i> Browse Products</a>
                    </div>
                  `;
                }
              }, 250);
            }
          }
        }
      }

      showNotification(
        data && data.action === 'added' ? 'Added to favorites!' : 'Removed from favorites',
        'success'
      );
    } else {
      showNotification('Failed to update favorite', 'danger');
    }
  } catch (error) {
    console.error('Error toggling favorite:', error);
    showNotification('Error updating favorite', 'danger');
  }
}

// Alias for home page compatibility
const favoriteProduct = (event, productId) => {
  event.stopPropagation();
  event.preventDefault();
  const btn = event.target.closest('.favorite-btn');

  // If quickFavorite exists (on home page), use that instead
  if (typeof quickFavorite !== 'undefined') {
    quickFavorite(event, productId, btn);
  } else if (btn) {
    toggleFavorite(event, productId, btn);
  }
};

window.smartGrocery = { showNotification, formatPrice, cart, toggleFavorite };
