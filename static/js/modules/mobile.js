/* ==========================================================================
   SMART GROCERY — MOBILE BEHAVIORS
   Powers the mobile top bar, bottom nav, full-screen search & browse
   overlays, and the filter side drawer. Active below 992px only.
   ========================================================================== */
(function () {
  'use strict';

  const MOBILE_MAX = 991.98;
  const isMobile = () => window.innerWidth <= MOBILE_MAX;

  /* ------------------------------------------------------------------
     FULL-SCREEN SEARCH OVERLAY
     ------------------------------------------------------------------ */
  function initSearchOverlay() {
    const overlay = document.getElementById('mSearchOverlay');
    if (!overlay) return;

    const input = document.getElementById('mSearchInput');
    const body = document.getElementById('mSearchBody');
    const openers = document.querySelectorAll('[data-m-search-open]');
    const cancelBtn = document.getElementById('mSearchCancel');
    let searchTimeout = null;

    const hintHtml =
      '<div class="m-search-hint"><i class="bi bi-search"></i>' +
      '<div class="fw-bold" style="color:#3a3b3a;">Search Smart Grocery</div>' +
      '<small>Find products, brands and stores</small></div>';

    function open() {
      overlay.classList.add('is-open');
      document.body.classList.add('m-drawer-lock');
      if (!body.innerHTML.trim()) body.innerHTML = hintHtml;
      setTimeout(() => input.focus(), 250);
    }
    function close() {
      overlay.classList.remove('is-open');
      document.body.classList.remove('m-drawer-lock');
      input.blur();
    }

    openers.forEach((el) =>
      el.addEventListener('click', (e) => {
        e.preventDefault();
        open();
      })
    );
    if (cancelBtn) cancelBtn.addEventListener('click', close);

    function goToResults() {
      const q = input.value.trim();
      if (q) window.location.href = '/compare-prices?search=' + encodeURIComponent(q);
    }

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') goToResults();
    });

    input.addEventListener('input', () => {
      clearTimeout(searchTimeout);
      const q = input.value.trim();
      if (q.length < 2) {
        body.innerHTML = hintHtml;
        return;
      }
      searchTimeout = setTimeout(async () => {
        body.innerHTML =
          '<div class="d-flex justify-content-center py-5"><div class="spinner-border" style="color:#65388f;" role="status"></div></div>';
        try {
          const res = await fetch('/api/search-products?q=' + encodeURIComponent(q));
          const data = await res.json();
          if (!data.items || data.items.length === 0) {
            body.innerHTML =
              '<div class="m-search-hint"><i class="bi bi-emoji-neutral"></i>' +
              '<div class="fw-bold" style="color:#3a3b3a;">No matches for “' + escapeHtml(q) + '”</div>' +
              '<small>Try fewer or different words.</small></div>';
            return;
          }
          body.innerHTML = '';
          data.items.slice(0, 12).forEach((item) => {
            const c = item.cheapest || {};
            const priceVal =
              item.price || c.price || (item.stores && item.stores[0] && item.stores[0].price);
            const price = priceVal ? '€' + Number(priceVal).toFixed(2) : 'N/A';
            let store = 'Multiple Stores';
            if (item.store) store = item.store;
            else if (c.store) store = c.store;
            else if (item.stores && item.stores[0])
              store = item.stores[0].store || item.stores[0].name || store;
            const img = item.image || (item.images && item.images[0]) || '';
            const name = item.name || item.title || item.product_name || 'Unknown Product';
            const url = item.url || '/product/' + (item.id || item._id);

            const a = document.createElement('a');
            a.href = url;
            a.className = 'm-search-result';
            const imgHtml =
              img && img.indexOf('http') === 0
                ? '<img class="m-search-result__img" src="' + img + '" alt="">'
                : '<div class="m-search-result__img"><i class="bi bi-basket2-fill"></i></div>';
            a.innerHTML =
              imgHtml +
              '<div style="min-width:0;flex:1;">' +
              '<div class="m-search-result__name">' + escapeHtml(name) + '</div>' +
              '<span class="m-search-result__store"><i class="bi bi-shop"></i>' + escapeHtml(store) + '</span>' +
              '</div>' +
              '<div class="m-search-result__price">' + price + '</div>';
            body.appendChild(a);
          });
          if (data.items.length > 12) {
            const viewAll = document.createElement('a');
            viewAll.className = 'm-search-viewall';
            viewAll.href = '/compare-prices?search=' + encodeURIComponent(q);
            viewAll.innerHTML = 'View All Results <i class="bi bi-arrow-right ms-1"></i>';
            body.appendChild(viewAll);
          }
        } catch (err) {
          body.innerHTML =
            '<div class="m-search-hint"><i class="bi bi-exclamation-triangle"></i>Error loading results.</div>';
        }
      }, 320);
    });
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  /* ------------------------------------------------------------------
     FULL-SCREEN BROWSE OVERLAY — multi-level slide with breadcrumbs
     ------------------------------------------------------------------ */
  function initBrowseOverlay() {
    const overlay = document.getElementById('mBrowseOverlay');
    if (!overlay) return;

    const openers = document.querySelectorAll('[data-m-browse-open]');
    const closeBtn = document.getElementById('mBrowseClose');
    const closeBtnSub = document.getElementById('mBrowseCloseSub');
    const backBtn = document.getElementById('mBrowseBack');
    const tabs = overlay.querySelectorAll('.m-browse-tab');
    const panes = overlay.querySelectorAll('.m-browse-pane');
    const slideContainer = document.getElementById('mBrowseSlideContainer');
    const subPanel = document.getElementById('mBrowseSubPanel');
    const headMain = document.getElementById('mBrowseHeadMain');
    const headSub = document.getElementById('mBrowseHeadSub');
    const breadcrumbEl = document.getElementById('mBrowseBreadcrumb');
    const tabRow = document.getElementById('mBrowseTabRow');

    // Stack of navigation levels: [{name, url, items:[{name,url,children:[]}]}]
    let navStack = [];

    function open(e) {
      if (e) e.preventDefault();
      overlay.classList.add('is-open');
      document.body.classList.add('m-drawer-lock');
    }
    function closeOverlay() {
      overlay.classList.remove('is-open');
      document.body.classList.remove('m-drawer-lock');
      setTimeout(resetToRoot, 320);
    }
    function resetToRoot() {
      navStack = [];
      if (slideContainer) slideContainer.classList.remove('is-sub');
      if (headMain) headMain.classList.remove('is-hidden');
      if (headSub) headSub.classList.remove('is-visible');
      if (tabRow) tabRow.style.display = '';
    }
    function showSubPanel() {
      if (slideContainer) slideContainer.classList.add('is-sub');
      if (headMain) headMain.classList.add('is-hidden');
      if (headSub) headSub.classList.add('is-visible');
      if (tabRow) tabRow.style.display = 'none';
    }

    function updateBreadcrumbs() {
      if (!breadcrumbEl) return;
      breadcrumbEl.innerHTML = '';
      navStack.forEach((level, i) => {
        if (i > 0) {
          const sep = document.createElement('i');
          sep.className = 'bi bi-chevron-right m-breadcrumb-sep';
          breadcrumbEl.appendChild(sep);
        }
        const crumb = document.createElement('span');
        crumb.className = 'm-breadcrumb-item' + (i === navStack.length - 1 ? ' is-active' : ' is-link');
        crumb.textContent = level.name;
        if (i < navStack.length - 1) {
          const idx = i;
          crumb.addEventListener('click', () => jumpToLevel(idx));
        }
        breadcrumbEl.appendChild(crumb);
      });
    }

    function jumpToLevel(index) {
      navStack = navStack.slice(0, index + 1);
      updateBreadcrumbs();
      renderLevel(navStack[navStack.length - 1]);
    }

    function renderLevel(level) {
      if (!subPanel) return;
      subPanel.innerHTML = '';

      // "View all" pill at the top
      const viewAll = document.createElement('a');
      viewAll.href = level.url;
      viewAll.className = 'm-subpanel-viewall';
      viewAll.innerHTML = 'View all ' + escapeHtml(level.name) + ' <i class="bi bi-arrow-right"></i>';
      subPanel.appendChild(viewAll);

      const divider = document.createElement('div');
      divider.className = 'm-subpanel-divider';
      subPanel.appendChild(divider);

      // Each item as a row
      level.items.forEach((item) => {
        const row = document.createElement('div');
        row.className = 'm-subrow';

        const link = document.createElement('a');
        link.href = item.url;
        link.className = 'm-subrow__link';
        link.textContent = item.name;
        row.appendChild(link);

        if (item.children && item.children.length > 0) {
          const drillBtn = document.createElement('button');
          drillBtn.type = 'button';
          drillBtn.className = 'm-subrow__drill';
          drillBtn.setAttribute('aria-label', 'Browse ' + item.name);
          drillBtn.innerHTML = '<i class="bi bi-chevron-right"></i>';
          drillBtn.addEventListener('click', () => {
            const nextLevel = { name: item.name, url: item.url, items: item.children };
            navStack.push(nextLevel);
            updateBreadcrumbs();
            renderLevel(nextLevel);
            subPanel.scrollTop = 0;
          });
          row.appendChild(drillBtn);
        }

        subPanel.appendChild(row);
      });

      subPanel.scrollTop = 0;
    }

    function drillIntoCategory(catName, catUrl, templateEl) {
      const items = [];
      if (templateEl && templateEl.content) {
        templateEl.content.querySelectorAll('[data-l1-name]').forEach((l1el) => {
          const children = [];
          l1el.querySelectorAll('[data-l2-name]').forEach((l2el) => {
            children.push({
              name: l2el.getAttribute('data-l2-name'),
              url: l2el.getAttribute('data-l2-url'),
              children: []
            });
          });
          items.push({
            name: l1el.getAttribute('data-l1-name'),
            url: l1el.getAttribute('data-l1-url'),
            children
          });
        });
      }
      const level = { name: catName, url: catUrl, items };
      navStack = [level];
      updateBreadcrumbs();
      renderLevel(level);
      showSubPanel();
    }

    function goBack() {
      if (navStack.length <= 1) {
        resetToRoot();
      } else {
        navStack.pop();
        updateBreadcrumbs();
        renderLevel(navStack[navStack.length - 1]);
        subPanel.scrollTop = 0;
      }
    }

    openers.forEach((el) => el.addEventListener('click', open));
    if (closeBtn) closeBtn.addEventListener('click', closeOverlay);
    if (closeBtnSub) closeBtnSub.addEventListener('click', closeOverlay);
    if (backBtn) backBtn.addEventListener('click', goBack);

    tabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        tabs.forEach((t) => t.classList.remove('active'));
        panes.forEach((p) => p.classList.remove('active'));
        tab.classList.add('active');
        const pane = document.getElementById(tab.getAttribute('data-m-pane'));
        if (pane) pane.classList.add('active');
        if (tab.getAttribute('data-m-pane') === 'mBrowseCategories') resetToRoot();
      });
    });

    // Drill buttons on main category rows
    overlay.querySelectorAll('.m-catrow__drill').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const catName = btn.getAttribute('data-cat-name') || '';
        const catUrl = btn.getAttribute('data-cat-url') || '#';
        const templateEl = btn.querySelector('template.m-catrow-data');
        drillIntoCategory(catName, catUrl, templateEl);
      });
    });
  }

  /* ------------------------------------------------------------------
     FILTER SIDE DRAWER (compare & deals pages)
     Promotes the existing .filters-container into a right-side drawer.
     ------------------------------------------------------------------ */
  function initFilterDrawer() {
    const container = document.querySelector('.filters-container');
    if (!container || container.dataset.mDrawerReady) return;

    let backdrop = null;
    let trigger = null;
    let closeBtn = null;

    function build() {
      if (container.dataset.mDrawerReady) return;
      container.dataset.mDrawerReady = '1';

      // Move drawer to <body> so no ancestor transform/overflow clips it
      container.dataset.mHomeMarker = '1';
      const placeholder = document.createElement('span');
      placeholder.className = 'm-filter-placeholder';
      container.parentNode.insertBefore(placeholder, container);
      document.body.appendChild(container);
      container.classList.add('m-as-drawer');

      // Backdrop
      backdrop = document.createElement('div');
      backdrop.className = 'm-filter-backdrop';
      document.body.appendChild(backdrop);

      // Close button inside drawer header
      closeBtn = document.createElement('button');
      closeBtn.type = 'button';
      closeBtn.className = 'm-drawer-close';
      closeBtn.setAttribute('aria-label', 'Close filters');
      closeBtn.innerHTML = '<i class="bi bi-x-lg"></i>';
      container.appendChild(closeBtn);

      // Trigger pill where the container used to live
      trigger = document.createElement('button');
      trigger.type = 'button';
      trigger.className = 'm-filter-trigger';
      trigger.innerHTML = '<i class="bi bi-funnel-fill"></i> Filters';
      placeholder.parentNode.insertBefore(trigger, placeholder);

      trigger.addEventListener('click', openDrawer);
      backdrop.addEventListener('click', closeDrawer);
      closeBtn.addEventListener('click', closeDrawer);

      // Close the drawer when Apply is pressed (results reload anyway)
      container.querySelectorAll('.btn-apply-filters').forEach((b) =>
        b.addEventListener('click', closeDrawer)
      );
    }

    function openDrawer() {
      container.classList.add('is-open');
      backdrop.classList.add('is-open');
      document.body.classList.add('m-drawer-lock');
    }
    function closeDrawer() {
      container.classList.remove('is-open');
      backdrop.classList.remove('is-open');
      document.body.classList.remove('m-drawer-lock');
    }

    function teardown() {
      if (!container.dataset.mDrawerReady) return;
      delete container.dataset.mDrawerReady;
      closeDrawer();
      container.classList.remove('m-as-drawer');
      const placeholder = document.querySelector('.m-filter-placeholder');
      if (placeholder) {
        placeholder.parentNode.insertBefore(container, placeholder);
        placeholder.remove();
      }
      if (backdrop) backdrop.remove();
      if (trigger) trigger.remove();
      if (closeBtn) closeBtn.remove();
      backdrop = trigger = closeBtn = null;
    }

    function sync() {
      if (isMobile()) build();
      else teardown();
    }
    sync();
    window.addEventListener('resize', debounce(sync, 200));
  }

  /* ------------------------------------------------------------------
     BOTTOM NAV: hide on scroll down, show on scroll up
     ------------------------------------------------------------------ */
  function initBottomNavScroll() {
    const nav = document.getElementById('mBottomNav');
    if (!nav) return;
    let lastY = window.scrollY;
    let ticking = false;
    window.addEventListener('scroll', () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        const y = window.scrollY;
        if (y > lastY + 12 && y > 160) nav.classList.add('is-hidden');
        else if (y < lastY - 6 || y < 160) nav.classList.remove('is-hidden');
        lastY = y;
        ticking = false;
      });
    }, { passive: true });
  }

  function debounce(fn, wait) {
    let t;
    return function () {
      clearTimeout(t);
      t = setTimeout(fn, wait);
    };
  }

  document.addEventListener('DOMContentLoaded', function () {
    initSearchOverlay();
    initBrowseOverlay();
    initFilterDrawer();
    initBottomNavScroll();
  });
})();
