# Implementation Checklist

## ✅ Quick Start Guide for Updating Pages

### Step 1: Update Your Template

Replace old product card HTML with the new unified component:

**OLD CODE** (Remove this):
```html
<div class="product-card-horizontal">
  <div class="card-image-wrapper">
    <img src="{{ product.image }}">
  </div>
  <div class="product-card-body">
    <div class="product-name">{{ product.name }}</div>
    <button class="btn-compare">Compare</button>
    <button class="btn-report">Report</button>
  </div>
</div>
```

**NEW CODE** (Use this):
```jinja
{% from 'components/product_card.html' import product_card %}

<div class="products-grid">
  {% for product in products %}
    {{ product_card(product, show_compare=True) }}
  {% endfor %}
</div>
```

### Step 2: Update Your Product Data

Ensure your Python route returns products with these fields:

```python
product = {
    # Required fields
    'id': product_id,
    'name': 'Product Name',
    'image': 'image_url',
    'price': 4.99,
    'store': 'Store Name',
    
    # Recommended fields
    'unit': '500g',  # Shows under product name
    'original_price': 5.99,  # For showing savings
    
    # Optional label flags
    'is_new': True,
    'is_popular': True,
    'is_healthy': True,
    'is_vegan': True,
    'is_organic': True,
    'is_gluten_free': True,
    'discount_percent': 20,
    
    # For multi-store products
    'stores': [
        {'store': 'Store A', 'price': 4.99},
        {'store': 'Store B', 'price': 5.49}
    ]
}
```

### Step 3: Remove Old CSS

Remove page-specific product card styles that conflict with the new unified system.

**Look for and remove**:
- `.product-card-horizontal` custom styles
- `.product-card-inner` custom styles
- Custom `.btn-compare` styles
- Custom `.btn-report` styles on cards

### Step 4: Test

1. ✅ Check product cards display correctly
2. ✅ Verify labels show when appropriate
3. ✅ Test "Add to List" button works
4. ✅ Check responsive layout on mobile
5. ✅ Verify navigation bar doesn't overlap content
6. ✅ Test favorite button functionality

## 📄 Pages to Update

### Priority 1 (Main Pages):
- [ ] `home.html` - Homepage product grid
- [ ] `compare_prices.html` - Compare page
- [ ] `featured_deals.html` - Deals page

### Priority 2 (Secondary Pages):
- [ ] `discover.html` - Discovery page
- [ ] `shopping_list.html` - Shopping list items
- [ ] `profile_favorites.html` - Favorites page

### Priority 3 (Admin Pages):
- [ ] `admin_products.html` - Admin product management
- [ ] `admin_lists.html` - Admin list view

## 🎨 Adding Product Labels

### In Your Python Route:

```python
# Example: Mark products as new if added in last 7 days
from datetime import datetime, timedelta

for product in products:
    # Check if product is new
    if product.get('created_at'):
        created = datetime.fromisoformat(product['created_at'])
        if datetime.now() - created < timedelta(days=7):
            product['is_new'] = True
    
    # Check if product is popular (e.g., high view count)
    if product.get('view_count', 0) > 1000:
        product['is_popular'] = True
    
    # Check for vegan products
    if 'vegan' in product.get('name', '').lower():
        product['is_vegan'] = True
    
    # Check for healthy products
    if product.get('category') in ['Fruits', 'Vegetables', 'Organic']:
        product['is_healthy'] = True
    
    # Check for discounts
    if product.get('original_price') and product.get('price'):
        discount = ((product['original_price'] - product['price']) / product['original_price']) * 100
        if discount > 0:
            product['discount_percent'] = int(discount)
```

## 🔧 Common Issues & Solutions

### Issue: Labels not showing
**Solution**: Check that your product data includes the label flags (`is_new`, `is_popular`, etc.)

### Issue: Navigation overlaps content
**Solution**: Ensure `body { padding-top: 76px; }` is applied (it's in navbar.css)

### Issue: Cards look different on different pages
**Solution**: Make sure you're using the unified product card macro, not custom HTML

### Issue: "Add to List" button doesn't work
**Solution**: Ensure `window.showListSelector()` function exists in your JavaScript

### Issue: Images not loading
**Solution**: Check image URLs and add fallback: `onerror="this.src='/static/placeholder.svg'"`

## 📱 Mobile Testing Checklist

- [ ] Cards stack properly on mobile
- [ ] Text is readable (not too small)
- [ ] Buttons are easy to tap (min 44px)
- [ ] Images load and display correctly
- [ ] Navigation menu works on mobile
- [ ] Labels don't overflow
- [ ] Price displays correctly

## 🎯 Performance Checklist

- [ ] Images are optimized (WebP format recommended)
- [ ] Lazy loading enabled for images
- [ ] CSS files are minified in production
- [ ] No console errors
- [ ] Page loads in < 3 seconds

## 📊 Quality Assurance

### Visual Check:
- [ ] All cards have consistent height
- [ ] Spacing is uniform
- [ ] Colors match the design system
- [ ] Fonts are correct (Cabinet Grotesk for headings, Plus Jakarta Sans for body)
- [ ] Shadows and borders are subtle

### Functional Check:
- [ ] Favorite button toggles correctly
- [ ] Add to List opens modal/selector
- [ ] View Details links to correct product
- [ ] Labels display appropriate icons
- [ ] Prices format correctly (€X.XX)

### Accessibility Check:
- [ ] All buttons have aria-labels
- [ ] Images have alt text
- [ ] Color contrast meets WCAG AA
- [ ] Keyboard navigation works
- [ ] Screen reader friendly

## 🚀 Deployment Steps

1. **Test Locally**:
   ```bash
   python app.py
   # Visit http://127.0.0.1:5001
   ```

2. **Check All Pages**:
   - Navigate through all main pages
   - Test on different screen sizes
   - Check browser console for errors

3. **Commit Changes**:
   ```bash
   git add .
   git commit -m "Implement unified product card system and theme improvements"
   ```

4. **Push to Repository**:
   ```bash
   git push origin main
   ```

5. **Deploy to Production**:
   - Follow your deployment process
   - Clear CDN cache if applicable
   - Monitor for errors

## 📝 Documentation Updates

After implementation:
- [ ] Update README.md with new features
- [ ] Add screenshots to documentation
- [ ] Update API documentation if needed
- [ ] Create user guide for new features

## 🎓 Training Team Members

Share with your team:
1. This checklist
2. `THEME_IMPROVEMENTS_GUIDE.md`
3. Example implementations
4. Design system documentation

## ✨ Future Enhancements

Consider adding:
- [ ] Product comparison feature
- [ ] Advanced filtering by labels
- [ ] Wishlist functionality
- [ ] Product reviews and ratings
- [ ] Social sharing buttons
- [ ] Recently viewed products
- [ ] Personalized recommendations

---

**Need Help?** Check `THEME_IMPROVEMENTS_GUIDE.md` for detailed documentation.
