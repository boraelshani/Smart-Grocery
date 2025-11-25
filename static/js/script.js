// Smart Grocery JavaScript (TSX-like shopping list interactions)

document.addEventListener('DOMContentLoaded', () => {
  initializeBootstrapComponents();
  setupSearchFunctionality();
  setupShoppingListHandlers();
  setupShoppingListInteractions();
  setupClaimButtons();
  setupProductModalHandlers();
  setupStoreSuggestions();
  setupHomeStoreSuggestions();
});

// Bootstrap helpers
function initializeBootstrapComponents() {
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (tooltipTriggerEl) { return new bootstrap.Tooltip(tooltipTriggerEl); });
}

// Search stub
function setupSearchFunctionality() {
  const input = document.getElementById('home-search-input');
  const btn = document.getElementById('home-search-btn');
  const resultsSection = document.getElementById('search-results-section');
  const resultsContainer = document.getElementById('search-results');

  async function doSearch() {
    if (!input) return;
    const q = input.value.trim();
    if (!q) { showNotification('Please enter a search term', 'info'); return; }
    try {
      const selectedStoreEl = document.getElementById('home-selected-store');
      let url = `/api/search-products?q=${encodeURIComponent(q)}`;
      if (selectedStoreEl && selectedStoreEl.value) url += `&store=${encodeURIComponent(selectedStoreEl.value)}`;
      const res = await fetch(url, { credentials: 'same-origin' });
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
            <img src="${img}" class="card-img-top" alt="${title}">
            <div class="card-body">
              <h5 class="card-title">${title}</h5>
              <p class="card-text mb-1">${store}</p>
              <p class="card-text text-muted mb-2">${price}</p>
              <div class="d-flex gap-2">
                <button class="btn btn-sm btn-info view-details-btn" data-bs-toggle="modal" data-bs-target="#productModal" data-title="${escapeHtml(title)}" data-price="${escapeHtml(price)}" data-store="${escapeHtml(store)}" data-image="${escapeHtml(img)}">View Details</button>
                <button class="btn btn-sm btn-primary add-to-list-btn" data-id="${escapeHtml(id)}" data-name="${escapeHtml(title)}" data-price="${escapeHtml(price)}">Add to List</button>
              </div>
            </div>
          </div>
        `;
        resultsContainer.appendChild(col);
      });
      resultsSection.style.display = 'block';
      // after rendering, attach view-details behavior and claim buttons
      // view-details handled by setupProductModalHandlers (it binds existing elements on DOMContentLoaded), so we need to re-run attaching for newly created elements
      // attach event for view-details and claim buttons
      document.querySelectorAll('.view-details-btn').forEach(el => el.removeEventListener('click', noop));
      // small rebind: call setupProductModalHandlers to rebind handlers to new elements
      try { setupProductModalHandlers(); } catch(e){}
    } catch (err) {
      showNotification('Search failed', 'danger');
    }
  }

  if (btn) btn.addEventListener('click', doSearch);
  if (input) input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); doSearch(); } });
}

function noop() {}

// Store suggestions for stores page: fetch stores and show dropdown on focus/hover
function setupStoreSuggestions() {
  const input = document.getElementById('stores-search-input');
  const btn = document.getElementById('stores-search-btn');
  const suggestions = document.getElementById('store-suggestions');
  let storeList = [];
  if (!input || !suggestions) return;

  async function fetchStores() {
    try {
      const r = await fetch('/api/stores', { credentials: 'same-origin' });
      const j = await r.json().catch(() => ({}));
      storeList = j.stores || [];
      renderSuggestions(storeList);
    } catch (e) {
      // ignore
    }
  }

  function renderSuggestions(list) {
    suggestions.innerHTML = '';
    if (!list || !list.length) {
      suggestions.style.display = 'none';
      return;
    }
    list.forEach(s => {
      const el = document.createElement('button');
      el.type = 'button';
      el.className = 'list-group-item list-group-item-action';
      el.textContent = s.name + (s.location ? ` — ${s.location}` : '');
      el.setAttribute('data-name', s.name);
      el.setAttribute('data-id', s.id || s.name);
      el.addEventListener('click', () => {
        // set input to chosen store and hide suggestions
        input.value = s.name;
        suggestions.style.display = 'none';
        // perform a store-filtered search or navigate to store detail
        performStoreSearch(s.name);
      });
      suggestions.appendChild(el);
    });
    suggestions.style.display = 'block';
  }

  function performStoreSearch(storeName) {
    // On the stores page, filter the visible store cards by name
    const cards = Array.from(document.querySelectorAll('.card'));
    cards.forEach(card => {
      const title = card.querySelector('.card-title')?.textContent || '';
      if (title.toLowerCase().includes(storeName.toLowerCase())) {
        card.closest('.col-md-4')?.classList.remove('d-none');
      } else {
        card.closest('.col-md-4')?.classList.add('d-none');
      }
    });
  }

  // show suggestions when input focused or hovered near it
  input.addEventListener('focus', () => { if (!storeList.length) fetchStores(); else renderSuggestions(storeList); });
  input.addEventListener('mouseenter', () => { if (!storeList.length) fetchStores(); });

  // hide suggestions on blur (with a slight delay to allow click)
  input.addEventListener('blur', () => { setTimeout(()=>{ suggestions.style.display='none'; }, 150); });

  // allow typing to filter suggestions
  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();
    if (!q) {
      renderSuggestions(storeList);
      return;
    }
    const filtered = storeList.filter(s => (s.name || '').toLowerCase().includes(q) || (s.location||'').toLowerCase().includes(q));
    renderSuggestions(filtered);
  });

  // search button fallback: simple filter
  btn?.addEventListener('click', (e) => { e.preventDefault(); const q = input.value.trim(); if (!q) { renderSuggestions(storeList); } else performStoreSearch(q); });
}

// Home page store suggestions: fetch stores and show dropdown on focus/hover
function setupHomeStoreSuggestions() {
  const input = document.getElementById('home-search-input');
  const btn = document.getElementById('home-search-btn');
  const suggestions = document.getElementById('home-store-suggestions');
  const selectedStoreEl = document.getElementById('home-selected-store');
  let storeList = [];
  if (!input || !suggestions) return;

  async function fetchStores() {
    try {
      const r = await fetch('/api/stores', { credentials: 'same-origin' });
      const j = await r.json().catch(() => ({}));
      storeList = j.stores || [];
      renderSuggestions(storeList);
    } catch (e) {
      // ignore
    }
  }

  function renderSuggestions(list) {
    suggestions.innerHTML = '';
    if (!list || !list.length) { suggestions.style.display = 'none'; return; }
    list.forEach(s => {
      const el = document.createElement('button');
      el.type = 'button';
      el.className = 'list-group-item list-group-item-action';
      el.textContent = s.name + (s.location ? ` — ${s.location}` : '');
      el.setAttribute('data-name', s.name);
      el.setAttribute('data-id', s.id || s.name);
      el.addEventListener('click', () => {
        if (selectedStoreEl) selectedStoreEl.value = s.name;
        input.value = input.value || '';
        suggestions.style.display = 'none';
        btn?.click();
      });
      suggestions.appendChild(el);
    });
    suggestions.style.display = 'block';
  }

  input.addEventListener('focus', () => { if (!storeList.length) fetchStores(); else renderSuggestions(storeList); });
  input.addEventListener('mouseenter', () => { if (!storeList.length) fetchStores(); });
  input.addEventListener('blur', () => { setTimeout(()=>{ suggestions.style.display='none'; }, 150); });
  input.addEventListener('input', () => { const q = input.value.trim().toLowerCase(); if (!q) { renderSuggestions(storeList); return; } const filtered = storeList.filter(s => (s.name || '').toLowerCase().includes(q) || (s.location||'').toLowerCase().includes(q)); renderSuggestions(filtered); });
  btn?.addEventListener('click', () => { /* default search behavior will include selected store */ });
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
      const modal = document.getElementById('productModal');
      if (!modal) return;

      async function populateModalFromDoc(doc) {
        const title = doc.name || doc.title || titleAttr || 'Product';
        const price = doc.price || (doc.cheapest && doc.cheapest.price) || '';
        const store = doc.store || (doc.cheapest && doc.cheapest.store) || (doc.stores && doc.stores[0] && doc.stores[0].store) || '';
        const image = doc.image || (doc.images && doc.images[0]) || viewBtn.getAttribute('data-image') || 'https://via.placeholder.com/300x200';
        modal.querySelector('.modal-title') && (modal.querySelector('.modal-title').textContent = title + ' Details');
        const img = modal.querySelector('.modal-body img'); if (img) img.src = image;
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
      const name = target.getAttribute('data-name') || target.getAttribute('data-title') || (document.querySelector('#productModal h6')?.textContent || 'Item');
      const price = target.getAttribute('data-price') || '';
      const store = target.getAttribute('data-store') || '';
      const item = { name, price, store };
      try {
        const res = await apiPostJson('/shopping-list/add', { item });
        if (res && (res.success || res.success === true)) {
          showNotification('Added to shopping list', 'success');
          try { const modalEl = bootstrap.Modal.getInstance(document.getElementById('productModal')); if (modalEl) modalEl.hide(); } catch(e){}
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
      const item = { name, price, id };
      try {
        const res = await apiPostJson('/shopping-list/add', { item });
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

  // save order
  document.getElementById('save-order')?.addEventListener('click', () => { postCurrentListOrder().then(r => { if (r && r.success) showNotification('Order saved','success'); }); });

  computeTotals();
}

async function postCurrentListOrder() {
  const rows = Array.from(document.querySelectorAll('.item-row'));
  const items = rows.map(r => ({ name: r.getAttribute('data-name'), purchased: r.classList.contains('purchased'), qty: 1, price: formatPrice(r.getAttribute('data-price') || (r.querySelector('.item-price')?.textContent||'0')) }));
  return apiPostJson('/shopping-list/update', { items });
}

let _saveTimer = null; function debounceSaveOrder(delay=700){ if(_saveTimer) clearTimeout(_saveTimer); _saveTimer = setTimeout(()=>postCurrentListOrder(), delay); }

function computeTotals(){ const rows = Array.from(document.querySelectorAll('.item-row')); let total=0; rows.forEach(r=> total += formatPrice(r.getAttribute('data-price') || (r.querySelector('.item-price')?.textContent||'0')) ); const el = document.getElementById('total-value'); if(el) el.textContent = `$${total.toFixed(2)}`; }

// minimal cart counter kept for compatibility
class CartCounter{ constructor(){ this.cartItems=[]; this.loadFromStorage(); this.updateDisplay(); } addItem(name, price){ const it={name,price,id:Date.now()}; this.cartItems.push(it); this.saveToStorage(); this.updateDisplay(); return it.id;} removeItem(id){ this.cartItems=this.cartItems.filter(i=>i.id!==id); this.saveToStorage(); this.updateDisplay(); } getCount(){ return this.cartItems.length;} getTotal(){ return this.cartItems.reduce((s,i)=>s+Number(i.price||0),0);} clearCart(){ this.cartItems=[]; this.saveToStorage(); this.updateDisplay(); } updateDisplay(){ const b=document.getElementById('cart-counter'); if(b){ b.textContent=this.getCount(); b.style.display=this.getCount()>0?'inline-block':'none'; } const t=document.getElementById('cart-total'); if(t) t.textContent=`$${this.getTotal().toFixed(2)}`; } saveToStorage(){ localStorage.setItem('smartGroceryCart', JSON.stringify(this.cartItems)); } loadFromStorage(){ try{ this.cartItems=JSON.parse(localStorage.getItem('smartGroceryCart'))||[] }catch(e){ this.cartItems=[] } }
}
const cart = new CartCounter();

window.smartGrocery = { showNotification, formatPrice, cart };
