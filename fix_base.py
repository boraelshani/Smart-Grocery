import re

with open('templates/base.html', 'r') as f:
    html = f.read()

# 1. Update the `.mega-cat-icon` style in base.html
# The user said: "On the browse tab, it shows the category images on the left side, but they are out of place and are lower than they should be, so fix that, make them bigger, and remove their container so only the image shows, but dont remove the whole image like you did before"
# So change .mega-cat-icon: remove background/border, make it bigger, align it better.

style_pattern = re.compile(r'<div class="mega-col-left".*?<ul class="mega-cat-list">', re.DOTALL)
new_style = r'''<div class="mega-col-left" id="mega-categories-list" style="width: 25%;">
                          <style>
                              /* Override left category lists locally to fit more items */
                              .mega-cat-item {
                                  padding: 8px 12px !important;
                                  font-size: 0.85rem !important; /* Smaller text */
                                  display: flex;
                                  align-items: center;
                              }
                              .mega-cat-icon {
                                  width: 32px;
                                  height: 32px;
                                  margin-right: 12px;
                                  flex-shrink: 0;
                                  display: flex;
                                  align-items: center;
                                  justify-content: center;
                              }
                              .mega-cat-icon img {
                                  width: 100%;
                                  height: 100%;
                                  object-fit: contain;
                                  border-radius: 6px;
                              }
                          </style>
                          <ul class="mega-cat-list">'''
html, count1 = style_pattern.subn(new_style, html)

# Remove the border/padding classes from the icon container loop
img_pattern = re.compile(r'<div class="mega-cat-icon p-0 border" style="overflow: hidden;">(.*?)</div>', re.DOTALL)
new_img = r'<div class="mega-cat-icon">\1</div>'
html, count1_img = img_pattern.subn(new_img, html)

# 2. Insert the new modal before the scripts
modal_html = r'''
      <!-- Global Price Report Modal -->
      <div class="modal fade" id="priceReportModal" tabindex="-1" aria-labelledby="priceReportLabel" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content overflow-hidden border-0 shadow-lg" style="border-radius: 20px;">
            <div class="modal-header border-0 pb-3" style="background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);">
              <h5 class="modal-title text-white fw-bold d-flex align-items-center" id="priceReportLabel">
                <i class="bi bi-flag-fill me-2 fs-5"></i> Report Inaccurate Price
              </h5>
              <button type="button" class="btn-close btn-close-white opacity-75 hover-opacity-100" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body p-4 bg-white">
              <div class="p-3 mb-4 rounded-3" style="background-color: #f8fafc; border: 1px solid #f1f5f9;">
                <p class="mb-0 text-dark fw-bold" id="report-product-name" style="font-size: 1.05rem;"></p>
                <small class="text-muted"><i class="bi bi-info-circle me-1"></i> Help us keep prices accurate.</small>
              </div>
              
              <div class="mb-4">
                <label class="form-label fw-bold text-secondary" for="report-store-select" style="font-size: 0.9rem;">Store where price was seen</label>
                <select id="report-store-select" class="form-select form-select-lg shadow-none" style="border-radius: 10px; border-color: #e2e8f0; font-size: 1rem; color: #334155; cursor: pointer;"></select>
              </div>
              <div class="mb-4">
                <label class="form-label fw-bold text-secondary" for="report-price-input" style="font-size: 0.9rem;">Observed price (in €)</label>
                <div class="input-group input-group-lg shadow-sm" style="border-radius: 10px; overflow: hidden;">
                  <span class="input-group-text bg-light border-0 text-muted" style="border-right: 1px solid #e2e8f0 !important;">€</span>
                  <input id="report-price-input" type="number" step="0.01" min="0.01" class="form-control border-0 shadow-none ps-2" placeholder="e.g. 2.99" style="font-size: 1.1rem; color: #334155;">
                </div>
              </div>
              <div class="mb-3">
                <label class="form-label fw-bold text-secondary" for="report-note-input" style="font-size: 0.9rem;">Note <span class="fw-normal text-muted">(Optional)</span></label>
                <textarea id="report-note-input" rows="2" maxlength="220" class="form-control shadow-none" style="border-radius: 10px; border-color: #e2e8f0; font-size: 0.95rem; resize: none;" placeholder="e.g. 'It was on clearance', 'Price matched at checkout'"></textarea>
              </div>
              <small id="report-feedback" class="d-block mt-1 fw-medium" style="min-height: 20px;"></small>
            </div>
            <div class="modal-footer border-0 pt-0 pb-4 px-4 bg-white">
              <button type="button" class="btn btn-light fw-bold rounded-pill px-4 shadow-sm" data-bs-dismiss="modal" style="color: #64748b;">Cancel</button>
              <button type="button" class="btn fw-bold text-white rounded-pill px-4 shadow-sm" id="submit-report-btn" style="background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);">Submit Report <i class="bi bi-send ms-1"></i></button>
            </div>
          </div>
        </div>
      </div>
'''
html = html.replace('<!-- Page Specific JavaScript / Inline Scripts -->', modal_html + '\n  <!-- Page Specific JavaScript / Inline Scripts -->')

# 3. Fix the array bug: opt.value = st; opt.textContent = st; 
# Needs to handle st.store or st.name
js_fix_pattern = re.compile(r"opt\.value = st;\s*opt\.textContent = st;")
js_fix_replacement = r"const sName = st.store || st.name || st; opt.value = sName; opt.textContent = sName;"
html, count3 = js_fix_pattern.subn(js_fix_replacement, html)

with open('templates/base.html', 'w') as f:
    f.write(html)
print(f"Fixed base.html style: {count1}, imgs: {count1_img}, JS fix: {count3}")

