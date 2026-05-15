# Multi-Select Filter Implementation Guide

## Changes Made

### 1. Removed HOME/COMPARE and HOME/DEALS breadcrumbs
- Both pages now only show category breadcrumbs when a category is selected
- Breadcrumbs are consistent across both pages

### 2. Fixed category card hover
- Removed underline on hover for visual category cards
- Added `text-decoration: none` to prevent underlines

### 3. Filters not collapsed by default
- Removed `collapsed` class from filters-body by default
- Filters are now visible on page load

### 4. Custom Multi-Select Dropdowns
- Added beautiful custom multi-select for Stores and Brands
- Users can select multiple options
- Selected items show as tags with remove buttons
- Smooth animations and modern styling

## Implementation

The multi-select dropdowns need JavaScript to function. Here's the complete implementation:

### HTML Structure (Replace existing filter groups for Store and Brand):

```html
<div class="filter-group">
  <label class="filter-label">Store</label>
  <div class="custom-multiselect" id="storeMultiselect">
    <div class="multiselect-trigger" onclick="toggleMultiselect('storeMultiselect')">
      <div class="multiselect-selected" id="storeSelected">
        <span class="multiselect-placeholder">Select stores...</span>
      </div>
      <i class="bi bi-chevron-down multiselect-arrow"></i>
    </div>
    <div class="multiselect-dropdown" id="storeDropdown">
      <!-- Options populated dynamically -->
    </div>
  </div>
</div>

<div class="filter-group">
  <label class="filter-label">Brand</label>
  <div class="custom-multiselect" id="brandMultiselect">
    <div class="multiselect-trigger" onclick="toggleMultiselect('brandMultiselect')">
      <div class="multiselect-selected" id="brandSelected">
        <span class="multiselect-placeholder">Select brands...</span>
      </div>
      <i class="bi bi-chevron-down multiselect-arrow"></i>
    </div>
    <div class="multiselect-dropdown" id="brandDropdown">
      <!-- Options populated dynamically -->
    </div>
  </div>
</div>
```

### JavaScript Functions (Add to existing script section):

```javascript
// Multi-select state
const selectedStores = new Set();
const selectedBrands = new Set();

// Toggle multi-select dropdown
function toggleMultiselect(id) {
  const container = document.getElementById(id);
  const trigger = container.querySelector('.multiselect-trigger');
  const dropdown = container.querySelector('.multiselect-dropdown');
  
  // Close other dropdowns
  document.querySelectorAll('.multiselect-dropdown').forEach(d => {
    if (d !== dropdown) {
      d.classList.remove('active');
      d.parentElement.querySelector('.multiselect-trigger').classList.remove('active');
    }
  });
  
  // Toggle this dropdown
  dropdown.classList.toggle('active');
  trigger.classList.toggle('active');
}

// Close dropdowns when clicking outside
document.addEventListener('click', function(e) {
  if (!e.target.closest('.custom-multiselect')) {
    document.querySelectorAll('.multiselect-dropdown').forEach(d => {
      d.classList.remove('active');
      d.parentElement.querySelector('.multiselect-trigger').classList.remove('active');
    });
  }
});

// Select/deselect option
function toggleOption(type, value) {
  const selectedSet = type === 'store' ? selectedStores : selectedBrands;
  
  if (selectedSet.has(value)) {
    selectedSet.delete(value);
  } else {
    selectedSet.add(value);
  }
  
  updateMultiselectDisplay(type);
}

// Update display of selected items
function updateMultiselectDisplay(type) {
  const selectedSet = type === 'store' ? selectedStores : selectedBrands;
  const containerId = type === 'store' ? 'storeSelected' : 'brandSelected';
  const dropdownId = type === 'store' ? 'storeDropdown' : 'brandDropdown';
  const container = document.getElementById(containerId);
  
  container.innerHTML = '';
  
  if (selectedSet.size === 0) {
    container.innerHTML = `<span class="multiselect-placeholder">Select ${type}s...</span>`;
  } else {
    selectedSet.forEach(value => {
      const tag = document.createElement('span');
      tag.className = 'multiselect-tag';
      tag.innerHTML = `
        ${value}
        <button class="multiselect-tag-remove" onclick="event.stopPropagation(); toggleOption('${type}', '${value}')">
          <i class="bi bi-x"></i>
        </button>
      `;
      container.appendChild(tag);
    });
  }
  
  // Update checkboxes
  document.querySelectorAll(`#${dropdownId} .multiselect-option`).forEach(opt => {
    const value = opt.getAttribute('data-value');
    if (selectedSet.has(value)) {
      opt.classList.add('selected');
    } else {
      opt.classList.remove('selected');
    }
  });
}

// Populate multi-select options
function populateMultiselect(type, options) {
  const dropdownId = type === 'store' ? 'storeDropdown' : 'brandDropdown';
  const dropdown = document.getElementById(dropdownId);
  
  dropdown.innerHTML = '';
  options.forEach(option => {
    const optionEl = document.createElement('div');
    optionEl.className = 'multiselect-option';
    optionEl.setAttribute('data-value', option);
    optionEl.onclick = (e) => {
      e.stopPropagation();
      toggleOption(type, option);
    };
    optionEl.innerHTML = `
      <div class="multiselect-checkbox">
        <i class="bi bi-check"></i>
      </div>
      <span>${option}</span>
    `;
    dropdown.appendChild(optionEl);
  });
}

// Update populateStoresAndBrands function
function populateStoresAndBrands() {
  const products = document.querySelectorAll('[data-stores]');
  const stores = new Set();
  const brands = new Set();
  
  products.forEach(product => {
    try {
      const storesData = JSON.parse(product.getAttribute('data-stores') || '[]');
      storesData.forEach(s => {
        if (s.store || s.name) stores.add(s.store || s.name);
      });
    } catch (e) {}
    
    const brand = product.getAttribute('data-brand');
    if (brand) brands.add(brand);
  });
  
  populateMultiselect('store', Array.from(stores).sort());
  populateMultiselect('brand', Array.from(brands).sort());
}

// Update applyFilters to use multi-select
function applyFilters() {
  const minPrice = document.getElementById('minPrice').value;
  const maxPrice = document.getElementById('maxPrice').value;
  const availability = document.getElementById('availabilityFilter').value;
  
  const params = new URLSearchParams(window.location.search);
  
  if (minPrice) params.set('min_price', minPrice);
  else params.delete('min_price');
  
  if (maxPrice) params.set('max_price', maxPrice);
  else params.delete('max_price');
  
  if (selectedStores.size > 0) {
    params.set('stores', Array.from(selectedStores).join(','));
  } else {
    params.delete('stores');
  }
  
  if (selectedBrands.size > 0) {
    params.set('brands', Array.from(selectedBrands).join(','));
  } else {
    params.delete('brands');
  }
  
  if (availability) params.set('availability', availability);
  else params.delete('availability');
  
  window.location.href = window.location.pathname + '?' + params.toString();
}

// Update clearFilters
function clearFilters() {
  document.getElementById('minPrice').value = '';
  document.getElementById('maxPrice').value = '';
  document.getElementById('availabilityFilter').value = '';
  
  selectedStores.clear();
  selectedBrands.clear();
  updateMultiselectDisplay('store');
  updateMultiselectDisplay('brand');
  
  const params = new URLSearchParams(window.location.search);
  const category = params.get('category');
  const search = params.get('search');
  
  let url = window.location.pathname;
  const newParams = new URLSearchParams();
  if (category) newParams.set('category', category);
  if (search) newParams.set('search', search);
  
  window.location.href = url + (newParams.toString() ? '?' + newParams.toString() : '');
}

// Initialize from URL on page load
document.addEventListener('DOMContentLoaded', function() {
  const params = new URLSearchParams(window.location.search);
  
  if (params.get('min_price')) document.getElementById('minPrice').value = params.get('min_price');
  if (params.get('max_price')) document.getElementById('maxPrice').value = params.get('max_price');
  if (params.get('availability')) document.getElementById('availabilityFilter').value = params.get('availability');
  
  // Load selected stores and brands from URL
  if (params.get('stores')) {
    params.get('stores').split(',').forEach(store => selectedStores.add(store));
  }
  if (params.get('brands')) {
    params.get('brands').split(',').forEach(brand => selectedBrands.add(brand));
  }
  
  populateStoresAndBrands();
  updateMultiselectDisplay('store');
  updateMultiselectDisplay('brand');
  updateActiveFilters();
});
```

## Files to Update

1. `/templates/compare_prices.html` - ✅ Updated
2. `/templates/featured_deals.html` - Need to apply same changes
3. Both files need the new HTML structure and JavaScript

## Next Steps

Apply the same multi-select implementation to the deals page for consistency.
