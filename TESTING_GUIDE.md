# Product Card Testing Guide

## Quick Start
1. Start the server: `make run` or `python app.py`
2. Open browser to: `http://127.0.0.1:5001`
3. Follow the test scenarios below

---

## Test Scenarios

### 1. Home Page Testing
**URL:** `http://127.0.0.1:5001/`

#### Test 1.1: Compare Prices Section
- [ ] Scroll to "Compare Prices" section
- [ ] Verify all product cards look identical
- [ ] Check that cards are smaller than before
- [ ] Verify "Add to List" button is purple with white text
- [ ] Hover over "Add to List" button - should darken to #6d28d9
- [ ] Check favorite button has white background with purple border
- [ ] Verify product size displays under product name (if available)
- [ ] Check that up to 2 labels show on each card

#### Test 1.2: Flash Deals Section
- [ ] Scroll to "Flash Deals" section
- [ ] Verify cards match the Compare Prices section design
- [ ] Check store prices display (should show multiple stores if available)
- [ ] Verify cheapest store has green background
- [ ] Check savings badge appears when multiple stores available

#### Test 1.3: Popular Right Now Section
- [ ] Scroll to "Popular Right Now" section
- [ ] Verify cards match other sections
- [ ] Test clicking entire card - should go to product detail page
- [ ] Test clicking favorite button - should toggle without navigating away

---

### 2. Compare Page Testing
**URL:** `http://127.0.0.1:5001/compare-prices`

#### Test 2.1: Product Grid
- [ ] Verify all products use unified card design
- [ ] Check that cards are smaller and more compact
- [ ] Verify grid shows 4 cards per row on desktop
- [ ] Check that each card shows up to 3 store prices
- [ ] Verify cheapest price has green highlight
- [ ] Check "+X more stores" hint appears when >3 stores

#### Test 2.2: Store Prices Display
- [ ] Find a product with multiple stores
- [ ] Verify stores are sorted by price (cheapest first)
- [ ] Check store names have icons
- [ ] Verify prices are formatted as €X.XX
- [ ] Check cheapest store row has green background (#f0fdf4)
- [ ] Verify other store rows have gray background (#f8f9fa)

#### Test 2.3: Interactive Elements
- [ ] Click "Add to List" button - should open list selector
- [ ] Click favorite button - should toggle favorite status
- [ ] Click anywhere else on card - should navigate to product detail
- [ ] Hover over card - should lift up with shadow
- [ ] Check that buttons don't trigger card click

---

### 3. Deals Page Testing
**URL:** `http://127.0.0.1:5001/featured-deals`

#### Test 3.1: Deals Grid
- [ ] Verify all deal cards use unified design
- [ ] Check cards match home and compare page design
- [ ] Verify discount labels show on cards
- [ ] Check that deal-specific labels display correctly
- [ ] Verify savings calculations are correct

#### Test 3.2: Multiple Stores
- [ ] Find deals with multiple stores
- [ ] Verify all store prices display
- [ ] Check cheapest store is highlighted
- [ ] Verify savings badge shows correct amount
- [ ] Check "+X more stores" hint for deals with >3 stores

---

### 4. Responsive Design Testing

#### Test 4.1: Desktop (1920px)
- [ ] Cards should show 4 per row
- [ ] All elements clearly visible
- [ ] Proper spacing between cards
- [ ] Hover effects work smoothly

#### Test 4.2: Laptop (1366px)
- [ ] Cards should show 3-4 per row
- [ ] No horizontal scrolling
- [ ] All text readable
- [ ] Images scale properly

#### Test 4.3: Tablet (768px)
- [ ] Cards should show 2 per row
- [ ] Touch targets large enough
- [ ] Buttons easily tappable
- [ ] No layout breaking

#### Test 4.4: Mobile (375px)
- [ ] Cards should show 1 per row
- [ ] All content fits without overflow
- [ ] Buttons remain accessible
- [ ] Images load properly

---

### 5. Visual Consistency Testing

#### Test 5.1: Cross-Page Comparison
- [ ] Open home page in one tab
- [ ] Open compare page in another tab
- [ ] Open deals page in third tab
- [ ] Compare cards side-by-side
- [ ] Verify they look identical
- [ ] Check button colors match
- [ ] Verify spacing is consistent

#### Test 5.2: Color Verification
- [ ] "Add to List" button: #7c3aed (purple)
- [ ] "Add to List" hover: #6d28d9 (darker purple)
- [ ] Favorite button border: #7c3aed (purple)
- [ ] Cheapest store background: #f0fdf4 (light green)
- [ ] Cheapest store text: #059669 (green)
- [ ] Other store background: #f8f9fa (light gray)

---

### 6. Functionality Testing

#### Test 6.1: Add to List
- [ ] Click "Add to List" on any product
- [ ] Verify list selector modal opens
- [ ] Select a list
- [ ] Verify product is added
- [ ] Check success message appears
- [ ] Verify button doesn't navigate away from page

#### Test 6.2: Favorite Toggle
- [ ] Click favorite button (heart icon)
- [ ] Verify heart fills with color
- [ ] Click again to unfavorite
- [ ] Verify heart returns to outline
- [ ] Check that card doesn't navigate when clicking favorite
- [ ] Verify favorite status persists on page reload

#### Test 6.3: Product Navigation
- [ ] Click on product card (not on buttons)
- [ ] Verify navigation to product detail page
- [ ] Check correct product loads
- [ ] Use browser back button
- [ ] Verify you return to same position on page

---

### 7. Data Display Testing

#### Test 7.1: Product with Multiple Stores
**Expected Data:**
```
Product: Milk 1L
Stores:
  - Tesco: €2.89 (cheapest - green)
  - Dunnes: €2.99
  - SuperValu: €3.49
Savings: €0.60
```

- [ ] Verify all 3 stores display
- [ ] Check Tesco has green background
- [ ] Verify prices are correct
- [ ] Check savings badge shows €0.60

#### Test 7.2: Product with Single Store
**Expected Data:**
```
Product: Bread
Store: Tesco
Price: €1.49
```

- [ ] Verify single store displays
- [ ] Check price is correct
- [ ] Verify no savings badge (only 1 store)
- [ ] Check no "+X more stores" hint

#### Test 7.3: Product with Size/Unit
**Expected Data:**
```
Product: Milk
Size: 1L
```

- [ ] Verify size displays under product name
- [ ] Check icon appears before size
- [ ] Verify text color is #6b7280
- [ ] Check font weight is 600

#### Test 7.4: Product with Labels
**Expected Data:**
```
Product: Organic Milk
Labels: Organic, New
```

- [ ] Verify max 2 labels display
- [ ] Check label colors are correct
- [ ] Verify label icons appear
- [ ] Check labels are positioned top-left

---

### 8. Performance Testing

#### Test 8.1: Page Load Speed
- [ ] Clear browser cache
- [ ] Load home page
- [ ] Check page loads in <2 seconds
- [ ] Verify images load progressively
- [ ] Check no layout shift during load

#### Test 8.2: Scroll Performance
- [ ] Scroll through product grid quickly
- [ ] Verify smooth scrolling
- [ ] Check no lag or stuttering
- [ ] Verify images lazy-load properly

---

### 9. Browser Compatibility Testing

#### Test 9.1: Chrome
- [ ] All features work
- [ ] Cards display correctly
- [ ] Hover effects smooth
- [ ] No console errors

#### Test 9.2: Firefox
- [ ] All features work
- [ ] Cards display correctly
- [ ] Hover effects smooth
- [ ] No console errors

#### Test 9.3: Safari
- [ ] All features work
- [ ] Cards display correctly
- [ ] Hover effects smooth
- [ ] No console errors

#### Test 9.4: Edge
- [ ] All features work
- [ ] Cards display correctly
- [ ] Hover effects smooth
- [ ] No console errors

---

### 10. Edge Cases Testing

#### Test 10.1: Very Long Product Name
- [ ] Find product with long name
- [ ] Verify name truncates to 2 lines
- [ ] Check ellipsis appears
- [ ] Verify card height remains consistent

#### Test 10.2: Product with No Image
- [ ] Find product without image
- [ ] Verify placeholder image displays
- [ ] Check placeholder is centered
- [ ] Verify card layout not broken

#### Test 10.3: Product with Many Stores (>3)
- [ ] Find product with 5+ stores
- [ ] Verify only 3 stores display
- [ ] Check "+2 more stores" hint appears
- [ ] Verify hint text is correct

#### Test 10.4: Product with No Size
- [ ] Find product without size/unit
- [ ] Verify size section doesn't display
- [ ] Check no empty space left
- [ ] Verify card layout remains clean

---

## Bug Reporting Template

If you find any issues, report them using this format:

```
**Page:** [Home/Compare/Deals]
**Browser:** [Chrome/Firefox/Safari/Edge]
**Device:** [Desktop/Tablet/Mobile]
**Issue:** [Brief description]
**Steps to Reproduce:**
1. [Step 1]
2. [Step 2]
3. [Step 3]
**Expected:** [What should happen]
**Actual:** [What actually happens]
**Screenshot:** [If applicable]
```

---

## Success Criteria

All tests should pass with:
- ✅ Unified card design across all pages
- ✅ Smaller, more compact cards
- ✅ Purple "Add to List" button
- ✅ Visible favorite button with border
- ✅ All store prices displayed
- ✅ Cheapest store highlighted in green
- ✅ Product size displays when available
- ✅ No "View Details" button
- ✅ Entire card clickable
- ✅ Smooth hover effects
- ✅ Responsive on all devices
- ✅ No console errors
- ✅ Fast page load times

---

**Testing Completed By:** _______________
**Date:** _______________
**Status:** _______________
