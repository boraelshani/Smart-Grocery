// Smart Grocery JavaScript (TSX-like shopping list interactions)

document.addEventListener('DOMContentLoaded', () => {
  initializeBootstrapComponents();
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
});

// Bootstrap helpers
function initializeBootstrapComponents() {
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (tooltipTriggerEl) { return new bootstrap.Tooltip(tooltipTriggerEl); });
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
    mapped.sort((a,b) => a.price - b.price);
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
        stores.forEach(s => { if (s && (s.store || s.name)) set.add((s.store||s.name).trim()); });
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
          storeMatch = stores.some(s => { const n = (s.store||s.name||'').toString().trim(); return n.toLowerCase() === storeVal.toLowerCase(); });
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
        visible.sort((a,b) => sortVal === 'price-asc' ? a.price - b.price : b.price - a.price);
      } else if (sortVal === 'name-asc' || sortVal === 'name-desc') {
        visible.sort((a,b) => sortVal === 'name-asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name));
      }
      // re-append in sorted order
      visible.forEach(v => productsRow.appendChild(v.col));
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
                <button class="btn btn-sm btn-primary add-to-list-btn" data-id="${escapeHtml(id)}" data-name="${escapeHtml(title)}" data-price="${escapeHtml(price)}" data-image="${escapeHtml(img)}">Add to List</button>
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
      try { setupProductModalHandlers(); } catch(e) {}
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
        visible.sort((a,b) => sortVal === 'price-asc' ? a.price - b.price : b.price - a.price);
      } else if (sortVal === 'name-asc' || sortVal === 'name-desc') {
        visible.sort((a,b) => sortVal === 'name-asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name));
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

function noop() {}

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
  input?.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); filterGrid(input.value.trim()); }});

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

function refreshShoppingListUI() { window.location.reload(); }

function showNotification(message, type = 'info') {
  const el = document.createElement('div'); el.className = `alert alert-${type} alert-dismissible fade show`; el.style.position='fixed'; el.style.top='20px'; el.style.right='20px'; el.style.zIndex=9999; el.style.minWidth='260px'; el.innerHTML = `${message}<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>`; document.body.appendChild(el);
  setTimeout(()=>{ try{ new bootstrap.Alert(el).close(); }catch(e){} }, 3500);
}

function formatPrice(price) { if (typeof price === 'string') price = price.replace(/[^0-9.]/g,''); return Number(price)||0; }

// Escape HTML to safely insert into innerHTML
function escapeHtml(unsafe) {
  if (unsafe === null || unsafe === undefined) return '';
  return String(unsafe).replace(/[&<>'"]/g, function(m) { return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]); });
}

let productModalHandlerBound = false;

// Handlers for the new TSX-like markup
function setupShoppingListHandlers() {
  // remove buttons
  document.querySelectorAll('.remove-item-btn').forEach(btn => btn.addEventListener('click', async (e) => {
    const name = btn.getAttribute('data-name') || btn.getAttribute('data-id'); if (!name) return;
    const r = await apiPostJson('/shopping-list/remove', { item: name }); if (r && r.success) { showNotification('Item removed','info'); refreshShoppingListUI(); } else showNotification('Could not remove item','danger');
  }));

  // checkbox toggles
  document.querySelectorAll('.checkbox-item').forEach(cb => cb.addEventListener('change', () => {
    const row = cb.closest('.item-row'); if (!row) return; if (cb.checked) row.classList.add('purchased'); else row.classList.remove('purchased'); debounceSaveOrder();
  }));
}

// Claim buttons: attach handlers to claim featured deals and add to user's shopping list
function setupClaimButtons() {
  document.querySelectorAll('.claim-deal-btn').forEach(btn => btn.addEventListener('click', async (e) => {
    const id = btn.getAttribute('data-id') || btn.getAttribute('data-title');
    const title = btn.getAttribute('data-title') || '';
    const price = btn.getAttribute('data-price') || '';
    if (!id) return showNotification('Missing deal id', 'danger');
    try {
      const res = await apiPostJson('/api/claim-deal', { deal_id: id, title, price });
      if (res && (res.success || res.added)) {
        showNotification('Deal claimed and added to your list', 'success');
        // refresh the shopping list view if present
        refreshShoppingListUI();
      } else if (res && res.error) {
        showNotification(res.error, 'danger');
      } else {
        showNotification('Could not claim deal', 'danger');
      }
    } catch (err) {
      showNotification('Error contacting server', 'danger');
    }
  }));
}

// Product modal: populate modal with clicked product details and wire Add to Cart
function setupProductModalHandlers() {
  // Use event delegation for dynamically added elements. Bind the listener only once.
  if (productModalHandlerBound) return;
  productModalHandlerBound = true;

  document.addEventListener('click', async (e) => {
    const target = e.target;
    if (!target) return;

    // View Details button clicked: try to fetch full product details from server by id or name
    const viewBtn = target.closest('.view-details-btn');
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
        if (img) { img.style.width='700px'; img.style.height='700px'; img.style.objectFit='cover'; }
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

    // Add to Cart button inside modal
    if (target.classList && target.classList.contains('add-to-cart-btn')) {
      const modalRoot = target.closest('.modal');
      const name = target.getAttribute('data-name') || target.getAttribute('data-title') || (modalRoot?.querySelector('h6')?.textContent || 'Item');
      const price = target.getAttribute('data-price') || '';
      const store = target.getAttribute('data-store') || '';
      const image = target.getAttribute('data-image') || modalRoot?.querySelector('img')?.src || '';
      const item = { name, price, store, image };
      try {
        const res = await apiPostJson('/shopping-list/add', { item });
        if (res && (res.success || res.success === true)) {
          showNotification('Added to shopping list', 'success');
          try { const modalEl = bootstrap.Modal.getInstance(modalRoot); if (modalEl) modalEl.hide(); } catch(e){}
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

    // Add to List button in search results or elsewhere
    if (target.classList && target.classList.contains('add-to-list-btn')) {
      const name = target.getAttribute('data-name') || target.getAttribute('data-title') || 'Item';
      const price = target.getAttribute('data-price') || '';
      const id = target.getAttribute('data-id') || null;
      const img = target.getAttribute('data-image') || '';
      
      // Create item object and show list selector
      const item = { name, price, id };
      if (img) item.image = img;
      
      // Call showListSelector if available (from shopping_list.html)
      if (window.showListSelector) {
        window.showListSelector(item);
      } else {
        // Fallback: add to active list directly
        try {
          const res = await apiPostJson('/api/list/add-item', { item });
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
    if (phoneEl && phoneInput) phoneInput.value = phoneEl.textContent === 'Not provided' ? '' : phoneEl.textContent;
    if (addressEl && addressInput) addressInput.value = addressEl.textContent === 'Not provided' ? '' : addressEl.textContent;
  });

  saveBtn.addEventListener('click', async () => {
    const phone = phoneInput ? phoneInput.value.trim() : '';
    const address = addressInput ? addressInput.value.trim() : '';
    try {
      const res = await fetch('/profile/update', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ phone, address }) });
      const j = await res.json().catch(() => ({}));
      if (res.ok && j && j.success) {
        // update UI
        if (phoneEl) phoneEl.textContent = phone || 'Not provided';
        if (addressEl) addressEl.textContent = address || 'Not provided';
        // hide modal
        try { const modal = bootstrap.Modal.getInstance(document.getElementById('profileModal')); if (modal) modal.hide(); } catch (e) {}
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
  
  if (!input || !btn || !dealsGrid) return;

  let allDeals = [];

  const collectAllDeals = () => {
    allDeals = Array.from(dealsGrid.querySelectorAll('[data-name]'));
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

    const visible = [];
    allDeals.forEach(col => {
      if (!col) return;
      
      const productName = (col.getAttribute('data-name') || '').toLowerCase();
      const priceText = col.getAttribute('data-price') || '0';
      const price = parsePrice(priceText);

      // search match
      let searchMatch = true;
      if (q) {
        searchMatch = productName.includes(q);
      }

      // price match
      let priceMatch = true;
      if (!isNaN(minVal)) priceMatch = priceMatch && (price >= minVal);
      if (!isNaN(maxVal)) priceMatch = priceMatch && (price <= maxVal);

      if (searchMatch && priceMatch) {
        col.style.display = '';
        visible.push({ col, price, name: productName });
      } else {
        col.style.display = 'none';
      }
    });

    // sort
    if (visible.length) {
      if (sortVal === 'price-asc' || sortVal === 'price-desc') {
        visible.sort((a,b) => sortVal === 'price-asc' ? a.price - b.price : b.price - a.price);
      } else if (sortVal === 'name-asc' || sortVal === 'name-desc') {
        visible.sort((a,b) => sortVal === 'name-asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name));
      }
      visible.forEach(v => dealsGrid.appendChild(v.col));
    }
  };

  const clearFeaturedFilters = () => {
    if (input) input.value = '';
    if (minPrice) minPrice.value = '';
    if (maxPrice) maxPrice.value = '';
    if (sortOrder) sortOrder.value = 'price-asc';
    allDeals.forEach(col => { if (col) col.style.display = ''; });
  };

  collectAllDeals();
  btn && btn.addEventListener('click', (e) => { e.preventDefault(); doSearch(); });
  input && input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); doSearch(); } });
  input && input.addEventListener('input', () => { doSearch(); });
  if (applyFiltersBtn) applyFiltersBtn.addEventListener('click', (e) => { e.preventDefault(); doSearch(); });
  if (clearFiltersBtn) clearFiltersBtn.addEventListener('click', (e) => { e.preventDefault(); clearFeaturedFilters(); });
}

function setupShoppingListInteractions() {
  const list = document.getElementById('shopping-list') || document.querySelector('.list-rows'); if (!list) return;

  // drag/drop
  let dragSrc = null;
  list.addEventListener('dragstart', (e) => { const r = e.target.closest('.item-row'); if (!r) return; dragSrc = r; e.dataTransfer.effectAllowed='move'; });
  list.addEventListener('dragover', (e) => e.preventDefault());
  list.addEventListener('drop', (e) => { e.preventDefault(); const target = e.target.closest('.item-row'); if (!target || !dragSrc || target===dragSrc) return; list.insertBefore(dragSrc, target); postCurrentListOrder(); });

  // clear purchased
  document.getElementById('clear-purchased')?.addEventListener('click', () => {
    const rows = Array.from(list.querySelectorAll('.item-row.purchased'));
    rows.forEach(r => { const name = r.getAttribute('data-name'); apiPostJson('/shopping-list/remove', { item: name }).then(res => { if (res && res.success) refreshShoppingListUI(); }); });
  });

  // clear all
  document.getElementById('clear-all')?.addEventListener('click', () => {
    if (!confirm('Clear all items from your shopping list?')) return;
    apiPostJson('/shopping-list/clear', {}).then(res => { if (res && res.success) { showNotification('All items cleared', 'info'); refreshShoppingListUI(); } else showNotification('Could not clear items', 'danger'); }).catch(()=> showNotification('Server error', 'danger'));
  });

  // save order
  document.getElementById('save-order')?.addEventListener('click', () => { postCurrentListOrder().then(r => { if (r && r.success) showNotification('Order saved','success'); }); });

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
      // update per-row displayed price (unit * qty)
      const unit = formatPrice(row.getAttribute('data-price') || (row.querySelector('.item-price')?.textContent||'0'));
      const priceEl = row.querySelector('.item-price');
      if (priceEl) priceEl.textContent = `$${(unit * qty).toFixed(2)}`;
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
    price: formatPrice(r.getAttribute('data-price') || (r.querySelector('.item-price')?.textContent||'0'))
  }));
  return apiPostJson('/shopping-list/update', { items });
}

let _saveTimer = null; function debounceSaveOrder(delay=700){ if(_saveTimer) clearTimeout(_saveTimer); _saveTimer = setTimeout(()=>postCurrentListOrder(), delay); }

// computeTotals: sum unit_price * qty for each row
function computeTotals(){
  const rows = Array.from(document.querySelectorAll('.item-row'));
  let total = 0;
  rows.forEach(r => {
    const unit = formatPrice(r.getAttribute('data-price') || (r.querySelector('.item-price')?.textContent||'0'));
    const qty = Number(r.getAttribute('data-qty') || 1);
    total += unit * (isNaN(qty) ? 1 : qty);
  });
  const el = document.getElementById('total-value'); if(el) el.textContent = `$${total.toFixed(2)}`;
}

// minimal cart counter kept for compatibility
class CartCounter{ constructor(){ this.cartItems=[]; this.loadFromStorage(); this.updateDisplay(); } addItem(name, price){ const it={name,price,id:Date.now()}; this.cartItems.push(it); this.saveToStorage(); this.updateDisplay(); return it.id;} removeItem(id){ this.cartItems=this.cartItems.filter(i=>i.id!==id); this.saveToStorage(); this.updateDisplay(); } getCount(){ return this.cartItems.length;} getTotal(){ return this.cartItems.reduce((s,i)=>s+Number(i.price||0),0);} clearCart(){ this.cartItems=[]; this.saveToStorage(); this.updateDisplay(); } updateDisplay(){ const b=document.getElementById('cart-counter'); if(b){ b.textContent=this.getCount(); b.style.display=this.getCount()>0?'inline-block':'none'; } const t=document.getElementById('cart-total'); if(t) t.textContent=`$${this.getTotal().toFixed(2)}`; } saveToStorage(){ localStorage.setItem('smartGroceryCart', JSON.stringify(this.cartItems)); } loadFromStorage(){ try{ this.cartItems=JSON.parse(localStorage.getItem('smartGroceryCart'))||[] }catch(e){ this.cartItems=[] } }
}
const cart = new CartCounter();

window.smartGrocery = { showNotification, formatPrice, cart };
