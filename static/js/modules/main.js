// ===============================================
// SMART GROCERY FRONTEND JAVASCRIPT
// Handles user interactions: shopping lists, favorites, filtering, search
// ===============================================

/**
 * MAIN ENTRY POINT
 * We use 'DOMContentLoaded' to ensure all HTML elements are loaded before running any scripts.
 * This prevents "element not found" errors.
 */
document.addEventListener('DOMContentLoaded', () => { // Page ready event
  // INITIALIZE: Run all setup functions when page loads
  initializeBootstrapComponents();    // Enable Bootstrap tooltips/popovers globally
  setupNavbarScroll();                // Change navbar visibility based on page scroll
  setupSearchFunctionality();         // Initialize the search bar logic
  setupShoppingListHandlers();        // Link "Add to List" buttons to backend APIs
  setupShoppingListInteractions();    // Enable checkbox/purchased toggling in list view
  setupClaimButtons();                // Initialize "Claim Deal" logic for featured items
  setupProductModalHandlers();        // Ensure modal state is reset on close events
  setupStoreSuggestions();            // Enable AJAX autocomplete for store input fields
  setupProfileEditHandlers();         // Toggle visibility for user profile edit forms
  setupFeaturedDealsSearch();         // Initialize filtering for the deals dashboard
  setupCompareHandlers();             // Enable price sorting on the comparison grid
  setupCompareFilters();              // Initialize hybrid (client+server) filtering
  if (typeof setupCompareExperience === 'function') {
    setupCompareExperience();         // Advanced compare tray, alerts, reports, basket insights
  }
  setupPaginationSmoothTransition();  // (Optional) Soft loading for paginated views
  setupLogoutConfirmation();          // Hijack logout links to show confirmation modal
  setupStoreSelection();              // Initialize store-specific pricing logic on cards

  // Always hide product modal on page load (prevents unwanted popup loops on creating new items)
  // This is a safety cleanup for stale modal states in the browser cache.
  const productModalEl = document.getElementById('productModal'); // Find modal by ID
  if (productModalEl) { // Check if it exists in current view
    const modalInstance = bootstrap.Modal.getOrCreateInstance(productModalEl); // Get wrapper
    modalInstance.hide(); // Force closure
  }
});

// EVENT LISTENER: BROWSER BACK BUTTON
// Hide product modal on browser back navigation (prevents unwanted popup staying open)
window.addEventListener('pageshow', function (event) { // Triggered on navigation
  const productModalEl = document.getElementById('productModal'); // Grab reference
  if (productModalEl) { // Verify element presence
    const modalInstance = bootstrap.Modal.getOrCreateInstance(productModalEl); // Instantiate
    modalInstance.hide(); // Clear visual overlay
  }
});

/**
 * NAVBAR SCROLL EFFECT
 * Adds a '.scrolled' CSS class to the navbar when the user scrolls down > 50px.
 * This allows us to change transparency/shadow via CSS.
 */
