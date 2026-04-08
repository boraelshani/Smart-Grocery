import re

with open('templates/recipe_planner.html', 'r', encoding='utf-8') as f:
    text = f.read()

old_unmatched = r'''              } else {
                  card.classList.add('unmatched-card');
                  bodyHTML = `
                      <div class="ingredient-header">
                          <span class="d-flex align-items-center text-muted"><i class="bi bi-dash-circle text-secondary me-2 fs-5"></i><del>${originalName}</del></span>
                          <span class="badge rounded-pill badge-store" style="background: #f8fafc; color: #94a3b8; border: 1px solid #e2e8f0;"><i class="bi bi-ban me-1"></i>Not in stock</span>
                      </div>
                      <div class="ingredient-body justify-content-center py-4">
                           <div class="text-center text-muted">
                               <i class="bi bi-info-circle fs-4 d-block mb-2 text-secondary"></i>
                               <span class="fw-medium">No direct match found in database for this ingredient.</span>
                           </div>
                      </div>
                  `;
              }'''

new_unmatched = r'''              } else {
                  card.classList.add('unmatched-card');
                  bodyHTML = `
                      <div class="ingredient-header">
                          <span class="d-flex align-items-center" style="color: #64748b; font-weight: 500; font-size: 1.05rem;"><i class="bi bi-bookmark text-primary me-2 fs-5"></i>${originalName}</span>
                          <span class="badge rounded-pill badge-store" style="background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1;"><i class="bi bi-check2-circle me-1"></i>Recipe Item</span>
                      </div>
                      <div class="ingredient-body justify-content-center align-items-center py-3">
                           <div class="text-center w-100" style="color: #94a3b8;">
                               <span class="fw-medium" style="font-size: 0.95rem;">Not available to shop in our database right now.</span>
                           </div>
                      </div>
                  `;
              }'''

text = text.replace(old_unmatched, new_unmatched)

with open('templates/recipe_planner.html', 'w', encoding='utf-8') as f:
    f.write(text)
