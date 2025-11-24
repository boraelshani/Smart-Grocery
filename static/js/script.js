// Smart Grocery JavaScript (TSX-like shopping list interactions)

document.addEventListener('DOMContentLoaded', () => {
  initializeBootstrapComponents();
  setupSearchFunctionality();
  setupShoppingListHandlers();
  setupShoppingListInteractions();
  setupClaimButtons();
});

// Bootstrap helpers
function initializeBootstrapComponents() {
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (tooltipTriggerEl) { return new bootstrap.Tooltip(tooltipTriggerEl); });
}

// Search stub
function setupSearchFunctionality() {
  document.querySelectorAll('.search-btn').forEach(btn => btn.addEventListener('click', () => {
    const input = btn.previousElementSibling;
    if (!input) return; const q = input.value.trim(); if (!q) return alert('Please enter a search term');
  }));
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
