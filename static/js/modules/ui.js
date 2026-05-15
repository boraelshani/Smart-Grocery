function setupNavbarScroll() { // Visibility handler
  const nav = document.querySelector('.navbar-premium'); // Locate premium navbar component
  if (!nav) return; // Exit silently if navbar is missing (e.g., error pages)

  const handleScroll = () => { // Animation logic
    // Check vertical scroll position (Y-axis) relative to top of viewport
    if (window.scrollY > 50) { // Threshold for effect
      nav.classList.add('scrolled'); // Apply background and border styles
      document.body.classList.add('scrolled'); // Add to body for padding adjustment
    } else { // Return to top position
      nav.classList.remove('scrolled'); // Restore original transparency
      document.body.classList.remove('scrolled'); // Remove from body
    }
  };

  // Attach listener to window scroll event for reactive updates
  window.addEventListener('scroll', handleScroll); // Listen to motion
  handleScroll(); // Execute once on load to catch pre-scrolled pages
}

// BOOTSTRAP: Activate tooltip popovers
// Bootstrap 5 requires manual initialization of tooltips (hover text)
function initializeBootstrapComponents() { // Feature activation
  // Select all DOM elements that have the custom tooltip data attribute
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]')); // Convert to array
  // Initialize a new Bootstrap Tooltip class for every matched element
  tooltipTriggerList.map(function (tooltipTriggerEl) { return new bootstrap.Tooltip(tooltipTriggerEl); }); // Map creation
}

/**
 * LOGOUT CONFIRMATION INTERCEPTOR
 * Intercepts any click on a logout link and shows a custom confirmation modal
 * instead of immediately navigating away.
 */
function setupLogoutConfirmation() { // UX safety feature
  // EVENT DELEGATION / CAPTURE PHASE
  // We listen on the 'document' for clicks, using 'true' for the capture phase.
  // This lets us intercept the event *before* it reaches the target link.
  document.addEventListener('click', (e) => { // Global click listener
    // EXCEPTION: If the user clicks inside the modal itself (e.g. "Yes" or "No"),
    // don't interfere with the modal's internal logic.
    if (e.target.closest('#customLogoutModal')) { // Nested check
      return; // Handled by Bootstrap
    }

    // Check if the clicked element (or its parent) is an anchor tag linking to "/logout"
    const logoutBtn = e.target.closest('a[href*="/logout"]'); // Pattern match
    if (logoutBtn) { // Found a logout trigger?
      // PROACTIVELY STOP EVERYTHING
      e.preventDefault();         // Halt navigation to the /logout route
      e.stopPropagation();        // Stop event bubbles to other handlers
      e.stopImmediatePropagation(); // Ensure no other scripts fire on this click
      
      // Show our custom UI confirmation instead of immediate logout
      showLogoutModal(logoutBtn.href); // Trigger modal with original target URL
      return false; // Final safeguard
    }
  }, true); // Use capture phase for high priority insertion
}

/**
 * Dynamically creates and injects the Logout Modal into the DOM if it's missing.
 * This uses a "Lazy Load" pattern - we don't clutter the initial HTML with this modal.
 * 
 * @param {string} logoutUrl - The URL to go to if the user confirms "Yes".
 */
function showLogoutModal(logoutUrl) { // UI Generator
  // Check if modal DOM element already exists in the current document
  let modalElem = document.getElementById('customLogoutModal'); // Tag lookup
  
  // LAZY CREATION: Only create the HTML structure the first time it's needed during the session.
  if (!modalElem) { // First time trigger?
    // Template Literal defining the Modal HTML with Bootstrap classes and custom styling
    const modalHtml = `
      <div class="modal fade" id="customLogoutModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered modal-sm">
          <div class="modal-content border-0 shadow-lg" style="border-radius: 20px;">
            <div class="modal-body text-center p-4">
              <div class="mb-3">
                <!-- Visual Icon with branding color -->
                <i class="bi bi-door-open text-danger" style="font-size: 3rem;"></i>
              </div>
              <h5 class="fw-bold mb-2">Wait! Logging out?</h5>
              <p class="text-muted small mb-4">Are you sure you want to end your session?</p>
              <div class="d-grid gap-2">
                <!-- "Yes" button acts as the original link redirecting to the server endpoint -->
                <a href="${logoutUrl}" class="btn btn-danger rounded-pill fw-bold py-2">Yes, Log Out</a>
                <!-- "No" button dismisses modal via data-bs attributes -->
                <button type="button" class="btn btn-light rounded-pill fw-semibold py-2" data-bs-dismiss="modal">Stay Logged In</button>
              </div>
            </div>
          </div>
        </div>
      </div>`;
    // Append the modal string to the end of the body to make it part of the DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml); // Live injection
    modalElem = document.getElementById('customLogoutModal'); // Cache reference
  } else { // Modal already exists?
    // Update the confirmation URL dynamically to handle different logout scenarios if they exist
    const confirmBtn = modalElem.querySelector('a.btn-danger'); // Find trigger
    if (confirmBtn) confirmBtn.href = logoutUrl; // Sync URL
  }

  // Use Bootstrap's JavaScript API to show the modal programmatically by passing the DOM node
  const modal = new bootstrap.Modal(modalElem); // Instantiate JS wrapper
  modal.show(); // Trigger visibility
}

// Compare page: sort the rendered store list items by numeric price (client-side)
