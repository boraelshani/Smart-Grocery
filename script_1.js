
		// Helper to safely reload page by cleaning up modals first
		function safeReload() {
			// Hide all open modals
			document.querySelectorAll('.modal.show').forEach(el => {
				const modal = bootstrap.Modal.getInstance(el);
				if (modal) modal.hide();
			});
			
			// Force remove backdrops and body locks
			document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
			document.body.classList.remove('modal-open');
			document.body.style.overflow = '';
			document.body.style.paddingRight = '';

			// Reload with brief delay to ensure UI updates
			setTimeout(() => {
				window.location.reload();
			}, 50);
		}

		// Initialize totals on page load
		document.addEventListener('DOMContentLoaded', () => {
			// CRITICAL FIX: Move all modals to body to strictly prevent z-index/stacking context issues
			// This fixes the "frozen" state where backdrops cover the modal
			document.querySelectorAll('.modal').forEach(modal => {
				document.body.appendChild(modal);
			});

			// Update all item row prices to account for multi-buy discounts
			document.querySelectorAll('.item-row').forEach(row => {
				const priceEl = row.querySelector('.item-price');
				if (priceEl) {
					const itemPrice = calculateItemPrice(row);
					priceEl.textContent = `€${itemPrice.toFixed(2)}`;
				}
			});
			computeTotals();
			updateListStats();
		});

		// Compute totals
		// Helper: effective unit price for buy X get Y offers
		function parseOffer(row) {
			// First, prioritise explicit data attributes which we know are populated correctly by Jinja
			const type = row.getAttribute('data-offer-type') || '';
			const ox = parseInt(row.getAttribute('data-offer-x') || '0', 10) || 0;
			const oy = parseInt(row.getAttribute('data-offer-y') || '0', 10) || 0;
			
			// If we have explicit X and Y, assume 2+1 style deal even if type is missing/weird
			if (ox > 0 && oy > 0) {
				return { type: 'buyXgetY', x: ox, y: oy };
			}
			
			// Fallback to JSON
			const offerJson = row.getAttribute('data-offer-json');
			if (offerJson) {
				try { 
					const obj = JSON.parse(offerJson); 
					if (obj) {
						// Normalize keys if possible
						const jx = parseInt(obj.x || obj.buy_quantity || 0, 10);
						const jy = parseInt(obj.y || obj.free_quantity || 0, 10);
						if (jx > 0 && jy > 0) {
							return { type: 'buyXgetY', x: jx, y: jy };
						}
						if (obj.type) return obj;
					}
				} catch (e) { }
			}

			// Fallback to text match
			const offerText = row.getAttribute('data-offer') || '';
			const m = offerText.match(/buy\s+(\d+)\s+get\s+(\d+)/i);
			if (m) return { type: 'buyXgetY', x: parseInt(m[1], 10) || 0, y: parseInt(m[2], 10) || 0 };
			
			return null;
		}

		function calculateItemPrice(row) {
			// CORE PRICING LOGIC (The Brain):
			// Calculates the final price for a row based on Quantity, Unit Price, and Active Discounts.
			
			const unitPrice = parseFloat(row.getAttribute('data-price') || 0) || 0;
			const qty = parseInt(row.getAttribute('data-qty') || 1, 10) || 1;
			const offerObj = parseOffer(row);

			// SCENARIO 1: Multi-Buy Offer (e.g., "Buy 2 Get 1 Free")
			// Logic: We define a 'cycle' (e.g., 3 items). Inside each cycle, you pay for X items.
			// We calculate how many full cycles fit in the user's quantity.
			
			// Check for multi-buy offer first (Buy X Get Y Free)
			if (offerObj && offerObj.type === 'buyXgetY') {
				const x = parseInt(offerObj.x || 0, 10) || 0;
				const y = parseInt(offerObj.y || 0, 10) || 0;
				if (x && y) {
					// For multibuy: charge x items at full price, y items free, repeat pattern
					// Example: 2+1 with 99 items = 33 cycles of (pay 2, get 1 free) = pay for 66
					const cycle = x + y;  // e.g., 2+1 = cycle of 3
					const fullCycles = Math.floor(qty / cycle);
					const remainder = qty % cycle;

					// Full cycles: pay for x items, free for y items per cycle
					let total = fullCycles * x * unitPrice;
					
					// Remainder: pay for as many as we need (but not more than x)
					total += Math.min(remainder, x) * unitPrice;

					return total;
				}
			}

			// SCENARIO 2: Tiered Discounts (e.g., "Buy 5+ for 10% off")
			// Logic: We check if the quantity meets the minimum requirement ('minQty').
			// If it does, we apply the discount percentage to the bundles.
			
			// Check for quantity tier discount (e.g., Buy 2+ get 15% off)
			const tierJson = row.getAttribute('data-tier-json');
			if (tierJson) {
				try {
					const tiers = JSON.parse(tierJson);
					if (Array.isArray(tiers) && tiers.length > 0) {
                        // Bundle Logic: Sort by min_qty DESC to find largest bundle first
                        tiers.sort((a, b) => (b.min_qty || 0) - (a.min_qty || 0));
                        
						// Find applicable bundle tier
						let activeTier = null;
						for (let tier of tiers) {
							const minQty = tier.min_qty || 0;
                            // Ignore max_qty for bundle logic unless handled specifically, 
                            // typically bundle = sets of X.
							if (qty >= minQty) {
                                activeTier = tier;
                                break; 
							}
						}

						if (activeTier) {
                            const bundleSize = activeTier.min_qty || 1;
                            const discountPercent = activeTier.discount_percent || 0;
                            
                            // Apply discount only to complete sets/bundles
                            const bundles = Math.floor(qty / bundleSize);
                            const discountedCount = bundles * bundleSize;
                            const remainder = qty % bundleSize;
                            
							const effectivePrice = unitPrice * (1 - discountPercent / 100);
							return (effectivePrice * discountedCount) + (unitPrice * remainder);
						}
					}
				} catch (e) {
					// Invalid JSON, skip tier processing
				}
			}

			// Check for special offer (2nd item discount, etc)
			const specialOffer = row.getAttribute('data-special-offer');
			if (specialOffer === 'second_half_off') {
				// Buy 1 at full, 2nd at 50% off, repeat
				const pairs = Math.floor(qty / 2);
				const remainder = qty % 2;
				return pairs * (unitPrice + unitPrice * 0.5) + remainder * unitPrice;
			} else if (specialOffer === 'second_free') {
				// Buy 1 get 2nd free, repeat
				const pairs = Math.floor(qty / 2);
				const remainder = qty % 2;
				return pairs * unitPrice + remainder * unitPrice;
			}

			// No special offers - return simple calculation
			return unitPrice * qty;
		}

		function computeTotals() {
                        let planned = 0;
                        let remaining = 0;
                        let completedCount = 0;
                        
                        // Track subtotals per store
                        const storeSubtotals = {};
                        
                        const items = document.querySelectorAll('.item-row');
                        const totalCount = items.length;

                        items.forEach(row => {
                                const itemPrice = calculateItemPrice(row);
                                const isCompleted = row.classList.contains('completed');
                                const store = row.getAttribute('data-store') || 'Other';

                                if (!storeSubtotals[store]) {
                                        storeSubtotals[store] = 0;
                                }
                                storeSubtotals[store] += itemPrice;

                                planned += itemPrice;
                                if (isCompleted) {
                                        completedCount++;
                                } else {
                                        remaining += itemPrice;
                                }
                        });
                        
                        // Update Subtotal DOM elements dynamically
                        document.querySelectorAll('.store-subtotal').forEach(el => {
                                const store = el.getAttribute('data-store');
                                if (store in storeSubtotals) {
                                        el.textContent = `€${storeSubtotals[store].toFixed(2)}`;
                                }
                        });

                        const plannedEl = document.getElementById('planned-total');
			const remainingEl = document.getElementById('remaining-total');
			const completedCountEl = document.getElementById('completed-count');
			const itemsCountEl = document.getElementById('items-count');

			if (plannedEl) plannedEl.textContent = `€${planned.toFixed(2)}`;
			if (remainingEl) remainingEl.textContent = `€${remaining.toFixed(2)}`;
			if (completedCountEl) completedCountEl.textContent = completedCount;
			if (itemsCountEl) itemsCountEl.textContent = totalCount;
		}

		function updateListStats() {
			computeTotals();
		}

		// Switch active list
		let isSwitchingList = false;
		function switchList(listId) {
			if (isSwitchingList) return;
			isSwitchingList = true;

			// UX IMPROVEMENT: Remember which list was open so we can re-open it on refresh (localStorage).
			localStorage.setItem('lastOpenedListId', listId);

			// Update active tab styling
			document.querySelectorAll('.list-card').forEach(tab => {
				tab.classList.remove('active');
				tab.classList.remove('enlarged');
			});
			
			const targetCard = document.querySelector(`.list-card[data-list-id="${listId}"]`);
			if (targetCard) {
				targetCard.classList.add('active');
				targetCard.classList.add('enlarged');
			}

			// Scroll into view
			const target = document.getElementById('active-list-wrapper');
			if (target && target.scrollIntoView) {
				target.scrollIntoView({ behavior: 'auto', block: 'start' });
			}

			// AJAX CALL (Asynchronous JavaScript and XML/JSON):
			// We ask the server for the items in this list WITHOUT reloading the whole page.
			// 'fetch' returns a Promise (future result).
			fetch(`/api/list/${listId}/items`)
				.then(r => {
					if (!r.ok) throw new Error('Network response was not ok');
					return r.json(); // Convert response text to JSON object
				})
				.then(data => {
					if (data.success) {
						// Show active wrapper, hide placeholder only after data is fetched
						const activeWrapper = document.getElementById('active-list-wrapper');
						const placeholder = document.getElementById('list-placeholder');

						try {
							displayListItems(data);
						} catch (e) {
							console.error('Display Error:', e);
							showNotification('Error displaying items', 'danger');
						}

						if (activeWrapper) activeWrapper.classList.remove('d-none');
						if (placeholder) placeholder.classList.add('d-none');

						// Set as active list on server
						fetch('/api/list/set-active', {
							method: 'POST',
							headers: { 'Content-Type': 'application/json' },
							body: JSON.stringify({ list_id: listId })
						});
					} else {
						showNotification('Error loading list: ' + (data.error || 'Unknown error'), 'danger');
					}
				})
				.catch(err => {
					console.error('Error:', err);
					showNotification('Error loading list. Please try again.', 'danger');
				})
				.finally(() => {
					isSwitchingList = false;
				});
		}

		// Exit list view without leaving page
		function exitListView() {
			const activeWrapper = document.getElementById('active-list-wrapper');
			const placeholder = document.getElementById('list-placeholder');
			if (activeWrapper) activeWrapper.classList.add('d-none');
			if (placeholder) placeholder.classList.remove('d-none');
			// remove active highlight from tabs
			document.querySelectorAll('.list-tab').forEach(tab => tab.classList.remove('active'));
			// Clear the stored last opened list
			localStorage.removeItem('lastOpenedListId');
		}

		// Initialize: auto-open the last viewed list on page load
		function restoreLastOpenedList() {
                        const lastListId = localStorage.getItem('lastOpenedListId');
                        let targetId = null;

                        if (lastListId) {
                                const listTab = document.querySelector(`[data-list-id="${lastListId}"]`);
                                if (listTab) {
                                        targetId = lastListId;
                                }
                        }
                        
                        if (!targetId) {
                                const firstTab = document.querySelector('.list-card');
                                if (firstTab) targetId = firstTab.getAttribute('data-list-id');
                        }

                        if (targetId) {
                                setTimeout(() => switchList(targetId), 50);
                        }
                }
		}

		// Run restore on page load
		// DATA PROCESSING: 
		// Users might find the same item twice. This function combines them.
		// It uses an object 'merged' as a dictionary to track unique items (Key: "name__store").
		if (document.readyState === 'loading') {
			document.addEventListener('DOMContentLoaded', restoreLastOpenedList);
		} else {
			restoreLastOpenedList();
		}

		// Merge duplicate items by name and sum quantities
		function mergeItemsByName(items) {
			const merged = {};

			items.forEach((item) => {
				const name = (typeof item === 'string') ? item : (item.name || '');
				const store = (item.store || item.store_name || '').toString();
				const nameKey = name.toLowerCase().trim();
				const storeKey = store.toLowerCase().trim();
				const mergedKey = `${nameKey}__${storeKey}`;
				const incomingQty = parseInt(item.qty || item.quantity || 1) || 1;
				const incomingPrice = parseFloat(item.price_val !== undefined ? item.price_val : item.price || 0) || 0;

				if (merged[mergedKey]) {
					merged[mergedKey].qty = parseInt(merged[mergedKey].qty || 1) + incomingQty;
					if (!merged[mergedKey].price_val && incomingPrice) merged[mergedKey].price_val = incomingPrice;
					if (!merged[mergedKey].price && incomingPrice) merged[mergedKey].price = incomingPrice;
					if (!merged[mergedKey].image && item.image) merged[mergedKey].image = item.image;
					if (!merged[mergedKey].store && store) merged[mergedKey].store = store;
					if (!merged[mergedKey].category && item.category) merged[mergedKey].category = item.category;
				} else {
					// Safe merge: handle item being string vs object
					const baseItemData = (typeof item === 'object' && item !== null) ? item : {};
					merged[mergedKey] = {
						...baseItemData,
						name: name,
						store: store,
						qty: incomingQty,
						id: item.id || name,
						purchased: item.purchased || false,
						image: item.image || '',
						category: item.category || 'Uncategorized',
						price_val: incomingPrice,
						price: incomingPrice
			// DOM MANIPULATION:
			// This function takes raw JSON data and turns it into HTML elements (Strings).
			// It then inserts this HTML into the page using .innerHTML.
			
					};
				}
			});

			return Object.values(merged);
		}

		const PLACEHOLDER_IMG = "{{ url_for('static', filename='placeholder.svg') }}";

		// Display list items dynamically
		function displayListItems(data) {
			if (!data) return;
			const listName = data.list_name || data.name || 'Unnamed List';
			let items = data.items || [];

			// Store globally for Modals
			currentSharedListUsers = data.collaborators || [];
			currentListOwnerEmail = data.is_shared ? (data.owner_email || 'Another User') : 'You';

			// Merge duplicate items by name
			items = mergeItemsByName(items);

			// Update title
			const titleEl = document.getElementById('active-list-title');
			if (titleEl) {
				let titleHtml = `<i class="bi bi-basket3-fill text-premium-purple me-2"></i>${listName}`;
				if (data.is_shared) {
					titleHtml += ` <span class="badge bg-info text-dark ms-2 fs-6 pb-2" style="vertical-align: middle; cursor: pointer;" onclick="showCollaboratorsModal()"><i class="bi bi-people-fill me-1"></i>Shared by ${data.owner_email || 'another user'}</span>`;
				} else if (data.collaborators && data.collaborators.length > 0) {
					titleHtml += ` <span class="badge bg-primary ms-2 fs-6 pb-2" style="vertical-align: middle; cursor: pointer;" onclick="showCollaboratorsModal()"><i class="bi bi-person-lines-fill me-1"></i>Shared (${data.collaborators.length})</span>`;
				}
				titleEl.innerHTML = titleHtml;
			}

			// Update items container
			const cardBody = document.getElementById('active-list-body');
			if (!cardBody) {
				console.error('active-list-body not found');
				return;
			}

			if (items.length === 0) {
				cardBody.innerHTML = `
					<div class="p-5 text-center text-muted">
						<div class="mb-4">
							<i class="bi bi-cart-x display-1 opacity-20"></i>
						</div>
						<h4 class="fw-700 text-premium-dark">Your list is empty</h4>
						<p class="mb-4">Start your smart shopping journey by adding products here.</p>
						<div class="d-flex justify-content-center">
							<a href="/compare-prices" class="btn btn-premium-purple btn-premium-style px-5" style="max-width: 300px;">
								<i class="bi bi-search me-2"></i>Explore Products
							</a>
						</div>
					</div>
				`;
				// Reset summary counts but allow computeTotals to handle it
				setTimeout(computeTotals, 50);
				return;
			}

			// Build HTML for items
			let itemsHTML = `
				<div class="p-3 border-bottom bg-light bg-opacity-50">
					<div class="row g-2 align-items-center">
						<div class="col-md-6 col-lg-5">
							<div class="premium-search-container">
								<span class="search-icon"><i class="bi bi-search"></i></span>
								<input type="text" id="active-search-items" class="item-search-input" placeholder="Search items in list...">
							</div>
						</div>
						<div class="col-auto">
							<button class="btn btn-outline-secondary btn-sm rounded-pill px-3 py-2" onclick="toggleCompletedItems()"
								title="Hide/Show Completed" style="font-weight: 600;">
								<i class="bi ${hideCompleted ? 'bi-eye' : 'bi-eye-slash'} me-1"></i> <span id="toggle-text">${hideCompleted ? 'Show Completed' : 'Hide Completed'}</span>
							</button>
						</div>
					</div>
				</div>
				<div class="py-2" id="items-container">
			`;

			// GROUP BY STORE
                        const groupedByStore = {};
                        const uniqueStores = [];
                        items.forEach((it) => {
                                if (!it) return;
                                const st = it.store || 'Other';
                                if (!groupedByStore[st]) {
                                        groupedByStore[st] = [];
                                        uniqueStores.push(st);
                                }
                                groupedByStore[st].push(it);
                        });

                        uniqueStores.forEach(store => {
                                let subtotal = 0;
                                groupedByStore[store].forEach((it) => {
                                        const raw_price = (it.price_val !== undefined ? it.price_val : it.price || 0);
                                        const unit = parseFloat(raw_price) || 0;
                                        const qty = (it.qty || 1);
                                        subtotal += (unit * qty);
                                });

                                itemsHTML += `<div class="store-group mt-3 mb-2 px-3 fw-bold text-premium-purple d-flex justify-content-between align-items-center" style="font-size: 1.1rem; border-bottom: 2px solid #e0e7ff;">`;
                                itemsHTML += `<div><i class="bi bi-shop me-2"></i>${store}</div>`;
                                itemsHTML += `<div class="store-subtotal" data-store="${store}">€${subtotal.toFixed(2)}</div></div>`;
                                itemsHTML += `<div class="store-items-wrapper">`;
                                
                                groupedByStore[store].forEach((it, index) => {
                                        const name = (typeof it === 'string') ? it : (it.name || 'Unknown Item');
                                        const item_id = (it.id || name);
                                        const purchased = (it.purchased || false);      
                                        const img = (it.items && it.items.length > 0 && it.items[0].image) ? it.items[0].image : (it.image || (it.images && it.images[0]) || '/static/placeholder.svg');
                                        const raw_price = (it.price_val !== undefined ? it.price_val : it.price || 0);
                                        const unit = parseFloat(raw_price) || 0;        
                                        const qty = (it.qty || 1);

                                        // Extract offer data
                                        const offerObj = (it.offer && typeof it.offer === 'object') ? it.offer : null;
                                        const offerX = offerObj ? (offerObj.x || '') : (it.multibuy_buy || '');
                                        const offerY = offerObj ? (offerObj.y || '') : (it.multibuy_free || '');
                                        const offerType = offerObj ? (offerObj.type || '') : (offerX && offerY ? 'buyXgetY' : '');
                                        const offerJson = offerObj ? JSON.stringify(offerObj).replace(/"/g, '&quot;') : '';
                                        const tierJson = (it.discount_tiers && Array.isArray(it.discount_tiers)) ? JSON.stringify(it.discount_tiers).replace(/"/g, '&quot;') : '';
                                        const specialOffer = it.special_offer || '';    

                                        itemsHTML += `
                                                <div class="item-row d-flex align-items-center gap-3 ${purchased ? 'completed' : ''}" draggable="true"
                                                        data-item-id="${item_id}" data-name="${name}" data-price="${unit}"
                                                        data-qty="${qty}" data-store="${store}" data-image="${img}"
                                                        data-offer-json='${offerJson}'  
                                                        data-offer-type="${offerType}"  
                                                        data-offer-x="${offerX}" data-offer-y="${offerY}"
                                                        data-tier-json='${tierJson}'    
                                                        data-special-offer="${specialOffer}"
                                                        style="${hideCompleted && purchased ? 'display: none !important;' : ''}">

                                                        <div class="form-check p-0 m-0">
                                                                <input class="form-check-input item-checkbox d-none" type="checkbox"
                                                                        id="item-${index}_${store.replace(/\W+/g, '')}" ${purchased ? 'checked' : ''}
                                                                        onchange="toggleItemComplete(this)">
                                                                <label class="premium-checkbox" for="item-${index}_${store.replace(/\W+/g, '')}">
                                                                        <i class="bi bi-check-lg"></i>
                                                                </label>
                                                        </div>

                                                        <div class="text-muted d-none d-md-block" style="cursor: move;">
                                                                <i class="bi bi-grip-vertical fs-5"></i>
                                                        </div>

                                                        <div class="item-img-pill">     
                                                                <img src="${img}" alt="${name}" onerror="this.src='/static/placeholder.svg'">
                                                        </div>

                                                        <div class="flex-grow-1">       
                                                                <h6 class="mb-1 item-name fw-700" style="font-weight: 700;">${name}</h6>
                                                        </div>

                                                        <div class="qty-container d-flex">
                                                                <button type="button" class="qty-btn qty-decr" onclick="changeQuantity(this, -1)">
                                                                        <i class="bi bi-dash"></i>
                                                                </button>
                                                                <input type="number" class="qty-input" value="${qty}" min="1"
                                                                        onchange="setQuantity(this)"
                                                                        onkeypress="if(event.key==='Enter') setQuantity(this)">
                                                                <button type="button" class="qty-btn qty-incr" onclick="changeQuantity(this, 1)">
                                                                        <i class="bi bi-plus"></i>
                                                                </button>
                                                        </div>

                                                        <div class="d-flex align-items-center gap-2 ms-md-3" style="min-width: 140px; justify-content: flex-end;">      
                                                                <div class="text-end d-flex flex-column align-items-end" style="min-width: 90px;">
                                                                        <div class="fw-900 text-premium-dark item-price" style="font-weight: 900; font-size: 1.1rem;">€${(unit * qty).toFixed(2)}</div>
                                                                        <small class="text-muted" style="font-size: 0.75rem;">€${unit.toFixed(2)} ea.</small>
                                                                </div>
                                                                <button type="button" class="btn-list-action btn-delete border-0"
                                                                        onclick="showRemoveItemConfirm(this)" title="Remove">
                                                                        <i class="bi bi-x-lg"></i>
                                                                </button>
                                                        </div>
                                                </div>
                                        `;
                                });
                                itemsHTML += `</div>`;
                        });
                        cardBody.innerHTML = itemsHTML;

			// Update stats after DOM render
			setTimeout(() => {
				computeTotals();
				updateListStats();
			}, 50);
		}

		// Create new list
		function createList() {
			const nameInput = document.getElementById('new-list-name');
			if (!nameInput) {
				console.error('List name input not found');
				return;
			}
			
			const listName = nameInput.value.trim();
			if (!listName) {
				if (typeof showNotification === 'function') {
					showNotification('Please enter a list name', 'warning');
				} else {
					alert('Please enter a list name');
				}
				return;
			}

			// Change button state to show progress
			const btn = document.querySelector('#createListModal button[onclick*="createList"]');
			const originalText = btn ? btn.innerHTML : 'Create List';
			if (btn) {
				btn.disabled = true;
				btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating...';
			}

			fetch('/api/list/create', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name: listName })
			})
				.then(async response => {
					const data = await response.json();
					if (!response.ok) throw new Error(data.error || 'Server error');
					return data;
				})
				.then(data => {
					if (data.success) {
						safeReload();
					} else {
						throw new Error(data.error || 'Failed to create list');
					}
				})
				.catch(err => {
					console.error('Error creating list:', err);
					if (typeof showNotification === 'function') {
						showNotification(err.message || 'A server error occurred', 'danger');
					} else {
						alert(err.message || 'A server error occurred');
					}
				})
				.finally(() => {
					if (btn) {
						btn.disabled = false;
						btn.innerHTML = originalText;
					}
				});
		}

		// View Collaborators Modal
		let currentSharedListUsers = [];
		try {
			const dataElement = document.getElementById('shared-list-collaborators-data');
			if (dataElement) {
				currentSharedListUsers = JSON.parse(dataElement.textContent || '[]');
			}
		} catch(e) {
			console.error("Error parsing collaborators", e);
		}
		
		let currentListOwnerEmail = "{{ active_list.owner_email if active_list and active_list.is_shared else 'You' }}";
		function showCollaboratorsModal() {
			const container = document.getElementById('collaborators-list-container');
			let html = '';

			// Show Owner
			html += `
				<div class="d-flex align-items-center p-3 rounded-4" style="background: #f8fafc; border: 1px solid #f1f5f9;">
					<div class="header-icon-circle me-3" style="width: 40px; height: 40px; background: #e0e7ff; border-radius: 12px; display: flex; align-items: center; justify-content: center; color: #4338ca;">
						<i class="bi bi-person-badge fs-5"></i>
					</div>
					<div class="me-auto">
						<div class="fw-bold" style="color: #1e293b;">${currentListOwnerEmail || 'Unknown User'}</div>
						<div class="small text-muted">Owner</div>
					</div>
				</div>
			`;

			// Show Collaborators
			if (currentSharedListUsers && currentSharedListUsers.length > 0) {
				currentSharedListUsers.forEach(collab => {
					html += `
						<div class="d-flex align-items-center p-3 rounded-4" style="background: #ffffff; border: 1px solid #f1f5f9;">
							<div class="header-icon-circle me-3" style="width: 40px; height: 40px; background: #fdf2f8; border-radius: 12px; display: flex; align-items: center; justify-content: center; color: #ec4899;">
								<i class="bi bi-person fs-5"></i>
							</div>
							<div class="me-auto">
								<div class="fw-bold" style="color: #1e293b;">${collab.email}</div>
								<div class="small text-muted text-capitalize">${collab.role || 'view'}</div>
							</div>
						</div>
					`;
				});
			} else {
				html += `<div class="text-center text-muted p-3">No other collaborators.</div>`;
			}

			container.innerHTML = html;
			const modalEl = document.getElementById('collaboratorsModal');
			if (modalEl) {
				const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
				modal.show();
			}
		}

		// Share List Modals
		function showShareListModal(listId) {
			const idEl = document.getElementById('share-list-id');
			if (idEl) idEl.value = listId;

			const modalEl = document.getElementById('shareListModal');
			if (modalEl) {
				const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
				modal.show();
			}
		}

		function confirmShareList() {
			const listId = document.getElementById('share-list-id').value;
			const targetEmail = document.getElementById('share-email').value.trim();
			const role = document.getElementById('share-role').value;

			if (!targetEmail) {
				if (typeof showNotification === 'function') {
					showNotification('Please enter an email limit.', 'warning');
				} else {
					alert('Please enter an email.');
				}
				return;
			}

			// Add loading state
			const btn = document.querySelector('#shareListModal .btn-premium-purple');
			const originalText = btn ? btn.innerHTML : 'Send Invite';
			if (btn) {
				btn.disabled = true;
				btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Sharing...';
			}

			fetch('/api/list/share', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ list_id: listId, target_email: targetEmail, role: role })
			})
				.then(r => r.json())
				.then(data => {
					if (data.success) {
						if (typeof showNotification === 'function') {
							showNotification('Shared successfully!', 'success');
						} else {
							alert('Shared successfully!');
						}
						const modalEl = document.getElementById('shareListModal');
						if (modalEl) {
							const modal = bootstrap.Modal.getInstance(modalEl);
							if (modal) modal.hide();
						}
						document.getElementById('share-email').value = '';
					} else {
						throw new Error(data.error || 'Failed to share list');
					}
				})
				.catch(err => {
					console.error('Error sharing list:', err);
					if (typeof showNotification === 'function') {
						showNotification(err.message || 'Error sharing list', 'danger');
					}
				})
				.finally(() => {
					if (btn) {
						btn.disabled = false;
						btn.innerHTML = originalText;
					}
				});
		}

		// Rename list
		function renameList(listId, btnOrName) {
			const currentName = typeof btnOrName === 'string' ? btnOrName : 
				(btnOrName && btnOrName.closest('.list-card') 
					? btnOrName.closest('.list-card').querySelector('.list-name-text').textContent.trim() 
					: '');
			const renameIdEl = document.getElementById('rename-list-id');
			const renameNameEl = document.getElementById('rename-list-name');
			if (renameIdEl) renameIdEl.value = listId;
			if (renameNameEl) {
				renameNameEl.value = currentName;
				// Store original name for comparison
				renameNameEl.dataset.originalName = currentName;
			}
			
			const modalEl = document.getElementById('renameListModal');
			if (modalEl) {
				const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
				modal.show();
			}
		}

		function confirmRename() {
			const listId = document.getElementById('rename-list-id').value;
			const nameInput = document.getElementById('rename-list-name');
			const newName = nameInput.value.trim();
			const originalName = nameInput.dataset.originalName;

			// If no change, simply close the modal without reloading
			if (newName === originalName) {
				const modalEl = document.getElementById('renameListModal');
				if (modalEl) {
					const modal = bootstrap.Modal.getInstance(modalEl);
					if (modal) modal.hide();
				}
				return;
			}

			if (!newName) {
				if (typeof showNotification === 'function') {
					showNotification('Please enter a name', 'warning');
				} else {
					alert('Please enter a name');
				}
				return;
			}

			// Add loading state
			const btn = document.querySelector('#renameListModal .btn-premium-purple');
			const originalText = btn ? btn.innerHTML : 'Update';
			if (btn) {
				btn.disabled = true;
				btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Updating...';
			}

			fetch('/api/list/rename', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ list_id: listId, name: newName })
			})
				.then(r => r.json())
				.then(data => {
					if (data.success) {
						safeReload();
					} else {
						throw new Error(data.error || 'Failed to rename list');
					}
				})
				.catch(err => {
					console.error('Error renaming list:', err);
					if (typeof showNotification === 'function') {
						showNotification(err.message || 'Error updating list', 'danger');
					}
				})
				.finally(() => {
					if (btn) {
						btn.disabled = false;
						btn.innerHTML = originalText;
					}
				});
		}

		// Delete list
		let deleteListTargetId = null;

		function deleteList(listId, btnOrName) {
			const listName = typeof btnOrName === 'string' ? btnOrName : 
				(btnOrName && btnOrName.closest('.list-card') 
					? btnOrName.closest('.list-card').querySelector('.list-name-text').textContent.trim() 
					: '');
			deleteListTargetId = listId;
			const nameEl = document.getElementById('delete-list-name');
			const idEl = document.getElementById('delete-list-id');
			if (nameEl) nameEl.textContent = listName || 'this list';
			if (idEl) idEl.value = listId;
			
			const modalEl = document.getElementById('deleteListModal');
			if (modalEl) {
				const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
				modal.show();
			}
		}

		function confirmDeleteList() {
			const listId = deleteListTargetId || document.getElementById('delete-list-id')?.value;
			if (!listId) {
				if (typeof showNotification === 'function') {
					showNotification('List ID missing', 'danger');
				}
				return;
			}

			// Add loading state
			const btn = document.querySelector('#deleteListModal .btn-danger');
			const originalText = btn ? btn.innerHTML : 'Delete Forever';
			if (btn) {
				btn.disabled = true;
				btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Deleting...';
			}

			fetch('/api/list/delete', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ list_id: listId })
			})
				.then(r => r.json())
				.then(data => {
					if (data.success) {
						safeReload();
					} else {
						throw new Error(data.error || 'Failed to delete list');
					}
				})
				.catch(err => {
					console.error('Error deleting list:', err);
					if (typeof showNotification === 'function') {
						showNotification(err.message || 'Error deleting list', 'danger');
					}
				})
				.finally(() => {
					if (btn) {
						btn.disabled = false;
						btn.innerHTML = originalText;
					}
				});
		}

		// Toggle item completion
		function toggleItemComplete(checkbox) {
			const row = checkbox.closest('.item-row');
			if (checkbox.checked) {
				row.classList.add('completed');
			} else {
				row.classList.remove('completed');
			}
			updateListStats();
			saveListState();
		}

		// Change quantity
		function changeQuantity(btn, delta) {
			const row = btn.closest('.item-row');
			const input = row.querySelector('.qty-input');
			let qty = parseInt(input.value || 1);

			qty = Math.max(1, qty + delta);
			input.value = qty;
			row.setAttribute('data-qty', qty);

			// Update price using multi-buy logic
			const unitPrice = parseFloat(row.getAttribute('data-price') || 0);
			const itemPrice = calculateItemPrice(row);
			const priceEl = row.querySelector('.item-price');
			if (priceEl) {
				priceEl.textContent = `€${itemPrice.toFixed(2)}`;
			}

			updateListStats();
			saveListState();
		}

		function setQuantity(input) {
			const row = input.closest('.item-row');
			let qty = parseInt(input.value || 1);

			// Validate quantity
			if (isNaN(qty) || qty < 1) {
				qty = 1;
				input.value = 1;
			}

			row.setAttribute('data-qty', qty);

			// Update price using multi-buy logic
			const itemPrice = calculateItemPrice(row);
			const priceEl = row.querySelector('.item-price');
			if (priceEl) {
				priceEl.textContent = `€${itemPrice.toFixed(2)}`;
			}

			updateListStats();
			saveListState();
		}

		// Remove item
		function removeItem(btn) {
			const row = btn.closest('.item-row');
			const name = row.getAttribute('data-name');

			fetch('/api/list/remove-item', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ item_name: name })
			})
				.then(r => r.json())
				.then(data => {
					if (data.success) {
						row.style.transition = 'all 0.3s ease';
						row.style.opacity = '0';
						row.style.transform = 'translateX(20px)';
						setTimeout(() => {
							row.remove();
							updateListStats();
							showNotification(`"${name}" removed from list`, 'success');
						}, 300);
					} else {
						showNotification('Failed to remove item', 'danger');
					}
				})
				.catch(err => showNotification('Error removing item', 'danger'));
		}

		// Clear completed items
		function clearCompleted() {
			const completed = document.querySelectorAll('.item-row.completed');
			if (completed.length === 0) {
				showNotification('No completed items to clear', 'info');
				return;
			}

			const count = completed.length;
			fetch('/api/list/clear-completed', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' }
			})
				.then(r => r.json())
				.then(data => {
					if (data.success) {
						showNotification(`${count} completed item${count > 1 ? 's' : ''} removed`, 'success');
						setTimeout(() => window.location.reload(), 500);
					} else {
						showNotification('Failed to clear completed items', 'danger');
					}
				})
				.catch(err => showNotification('Error clearing items', 'danger'));
		}

		// Clear all items - show modal
		function clearAllItems() {
			const allItems = document.querySelectorAll('.item-row');
			if (allItems.length === 0) {
				showNotification('No items to clear', 'info');
				return;
			}

			// Update count in modal
			document.getElementById('clearAllCount').textContent = allItems.length;

			// Show modal
			const modalEl = document.getElementById('clearAllModal');
			if (modalEl) {
				const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
				modal.show();
			}
		}

		// Show clear all items confirmation modal
		function showClearAllConfirm() {
			clearAllItems();
		}

		// Confirm clear all items
		function confirmClearAll() {
			// Find button to show loading
			const btn = document.querySelector('#clearAllModal .btn-danger');
			const originalText = btn ? btn.innerHTML : 'Clear Items';
			if (btn) {
				btn.disabled = true;
				btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Clearing...';
			}

			fetch('/api/list/clear-all', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' }
			})
				.then(r => r.json())
				.then(data => {
					if (data.success) {
						showNotification('All items cleared from list', 'success');
						safeReload();
					} else {
						showNotification('Failed to clear all items', 'danger');
					}
				})
				.catch(err => {
					console.error('Error clearing list:', err);
					showNotification('Error clearing list', 'danger');
				})
				.finally(() => {
					if (btn) {
						btn.disabled = false;
						btn.innerHTML = originalText;
					}
				});
		}

		// Clear all items (legacy function)
		function clearAll() {
			clearAllItems();
		}

		// Save list state
		function saveListState() {
			const items = Array.from(document.querySelectorAll('.item-row')).map(row => {
				let offer = null;
				try {
					const offerJson = row.getAttribute('data-offer-json');
					if (offerJson) offer = JSON.parse(offerJson);
				} catch (e) { }

				let discountTiers = null;
				try {
					const tierJson = row.getAttribute('data-tier-json');
					if (tierJson) discountTiers = JSON.parse(tierJson);
				} catch (e) { }

				return {
					name: row.getAttribute('data-name'),
					qty: parseInt(row.getAttribute('data-qty') || 1),
					purchased: row.classList.contains('completed'),
					price: parseFloat(row.getAttribute('data-price') || 0),
					store: row.getAttribute('data-store') || '',
					image: row.getAttribute('data-image') || '',
					offer: offer,
					discount_tiers: discountTiers,
					special_offer: row.getAttribute('data-special-offer') || ''
				};
			});

			fetch('/api/list/update-items', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ items: items })
			});
		}

		// Print list
		function printList() {
			window.print();
		}

		// Export list
		function exportList() {
			const items = Array.from(document.querySelectorAll('.item-row')).map(row => ({
				name: row.getAttribute('data-name'),
				quantity: row.getAttribute('data-qty'),
				price: row.getAttribute('data-price'),
				store: row.getAttribute('data-store'),
				completed: row.classList.contains('completed')
			}));

			const csv = 'Item,Quantity,Price,Store,Completed\n' +
				items.map(i => `"${i.name}",${i.quantity},€${i.price},"${i.store}",${i.completed}`).join('\n');

			const blob = new Blob([csv], { type: 'text/csv' });
			const url = window.URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = 'shopping-list.csv';
			a.click();
		}

		// Toggle completed items visibility
		let hideCompleted = false;
		function toggleCompletedItems() {
			hideCompleted = !hideCompleted;
			
			// Force update on all item rows
			const items = document.querySelectorAll('.item-row');
			items.forEach(row => {
				const isPurchased = row.classList.contains('completed');
				if (isPurchased) {
					if (hideCompleted) {
						row.setAttribute('style', 'display: none !important');
					} else {
						// Only show if it matches current search (if any)
						const searchInput = document.getElementById('active-search-items') || document.getElementById('search-items');
						const query = searchInput ? searchInput.value.toLowerCase().trim() : '';
						const name = row.getAttribute('data-name')?.toLowerCase() || '';
						const store = row.getAttribute('data-store')?.toLowerCase() || '';
						if (!query || name.includes(query) || store.includes(query)) {
							row.setAttribute('style', 'display: flex !important');
						}
					}
				}
			});

			// Update all toggle buttons text (there might be multiple if re-rendered)
			const toggleTexts = document.querySelectorAll('#toggle-text');
			toggleTexts.forEach(el => {
				el.textContent = hideCompleted ? 'Show Completed' : 'Hide Completed';
			});

			const toggleIcons = document.querySelectorAll('.btn-outline-secondary i');
			toggleIcons.forEach(icon => {
				if (icon.classList.contains('bi-eye') || icon.classList.contains('bi-eye-slash')) {
					icon.className = hideCompleted ? 'bi bi-eye me-1' : 'bi bi-eye-slash me-1';
				}
			});
		}

		// Search items - use event delegation to handle dynamically added search inputs
		document.addEventListener('input', function (e) {
			if (e.target && (e.target.id === 'search-items' || e.target.classList.contains('item-search-input'))) {
				const query = e.target.value.toLowerCase().trim();
				const items = document.querySelectorAll('.item-row');
				
				items.forEach(row => {
					const name = row.getAttribute('data-name')?.toLowerCase() || '';
					const store = row.getAttribute('data-store')?.toLowerCase() || '';
					const isMatch = !query || name.includes(query) || store.includes(query);
					
					const isPurchased = row.classList.contains('completed');
					const hiddenByFilter = hideCompleted && isPurchased;

					if (isMatch && !hiddenByFilter) {
						row.setAttribute('style', 'display: flex !important');
					} else {
						row.setAttribute('style', 'display: none !important');
					}
				});
			}
		});

		// Drag and drop
		let draggedItem = null;
		// EVENT LISTENERS: We attach functions to run when specific events happen (dragstart, drop, etc.)
		document.addEventListener('dragstart', function (e) {
			const itemRow = e.target.closest('.item-row');
			if (itemRow) {
				draggedItem = itemRow;
				// setTimeout 0 puts this action at the end of the event queue, allowing the drag image to be created first.
				setTimeout(() => {
					itemRow.classList.add('dragging');
				}, 0);
			}
		});

		document.addEventListener('dragend', function (e) {
			const itemRow = e.target.closest('.item-row');
			if (itemRow) {
				itemRow.classList.remove('dragging');
				document.querySelectorAll('.item-row').forEach(row => row.classList.remove('drag-over'));
				saveListState();
			}
		});

		document.addEventListener('dragover', function (e) {
			e.preventDefault();
			const itemRow = e.target.closest('.item-row');
			if (itemRow && itemRow !== draggedItem) {
				itemRow.classList.add('drag-over');
			}
		});

		document.addEventListener('dragleave', function (e) {
			const itemRow = e.target.closest('.item-row');
			if (itemRow) {
				itemRow.classList.remove('drag-over');
			}
		});

		document.addEventListener('drop', function (e) {
			e.preventDefault();
			const targetRow = e.target.closest('.item-row');
			if (targetRow && draggedItem && targetRow !== draggedItem) {
				const container = document.getElementById('items-container');
				const items = Array.from(container.children);
				const draggedIdx = items.indexOf(draggedItem);
				const targetIdx = items.indexOf(targetRow);

				if (draggedIdx < targetIdx) {
					targetRow.after(draggedItem);
				} else {
					targetRow.before(draggedItem);
				}
				
				targetRow.classList.remove('drag-over');
			}
		});

		// Show remove item confirmation modal
		function showRemoveItemConfirm(btn) {
			const itemNameEl = document.getElementById('removeItemName');
			const itemBtnEl = document.getElementById('removeItemBtn');
			const row = btn ? btn.closest('.item-row') : null;
			const itemName = row ? row.getAttribute('data-name') : 'this item';
			if (itemNameEl) itemNameEl.textContent = itemName;
			if (itemBtnEl) itemBtnEl.value = row ? row.getAttribute('data-item-id') || '' : '';

			// Store the button reference for later use
			window.removeItemButton = btn;

			const modalEl = document.getElementById('removeItemModal');
			if (modalEl) {
				const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
				modal.show();
			}
		}

		// Confirm remove item
		function confirmRemoveItem() {
			if (window.removeItemButton) {
				// Hide modal first
				const modalEl = document.getElementById('removeItemModal');
				if (modalEl) {
					const modal = bootstrap.Modal.getInstance(modalEl);
					if (modal) modal.hide();
				}

				// Call the original removeItem function
				removeItem(window.removeItemButton);
				window.removeItemButton = null;
			}
		}

		// Show export list confirmation modal
		function showExportListConfirm() {
			const modalEl = document.getElementById('exportListModal');
			if (modalEl) {
				const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
				modal.show();
			}
		}

		// Confirm export list
		function confirmExportList() {
			// Hide modal first
			const modalEl = document.getElementById('exportListModal');
			if (modalEl) {
				const modal = bootstrap.Modal.getInstance(modalEl);
				if (modal) modal.hide();
			}

			// Call the original exportList function
			exportList();
		}

		// Show print list confirmation modal
		function showPrintListConfirm() {
			const modalEl = document.getElementById('printListModal');
			if (modalEl) {
				const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
				modal.show();
			}
		}

		// Confirm print list
		function confirmPrintList() {
			// Hide modal first
			const modalEl = document.getElementById('printListModal');
			if (modalEl) {
				const modal = bootstrap.Modal.getInstance(modalEl);
				if (modal) modal.hide();
			}

			// Call the original printList function
			printList();
		}
	