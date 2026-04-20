
    // Rebind price report logic for main UI and dynamic elements
    const reportModalEl = document.getElementById('priceReportModal');
    if (reportModalEl) {
        const reportModal = new bootstrap.Modal(reportModalEl);
        
        document.body.addEventListener('click', function(e) {
            const btn = e.target.closest('.js-report-btn');
            if (!btn) return;
            
            const productId = btn.getAttribute('data-product-id');
            const productName = btn.getAttribute('data-product-name');
            let stores = [];
            try {
                stores = JSON.parse(btn.getAttribute('data-product-stores') || '[]');
            } catch (err) {}
            
            document.getElementById('report-product-name').textContent = productName;
            document.getElementById('submit-report-btn').dataset.productId = productId;
            
            const storeSelect = document.getElementById('report-store-select');
            storeSelect.innerHTML = '';
            
            if (stores && stores.length > 0) {
                stores.forEach(st => {
                    const opt = document.createElement('option');
                    opt.value = st;
                    opt.textContent = st;
                    storeSelect.appendChild(opt);
                });
            } else {
                const opt = document.createElement('option');
                opt.value = 'Unknown';
                opt.textContent = 'Unknown/Other';
                storeSelect.appendChild(opt);
            }
            
            document.getElementById('report-price-input').value = '';
            document.getElementById('report-note-input').value = '';
            document.getElementById('report-feedback').textContent = '';
            document.getElementById('report-feedback').className = 'text-muted d-block mt-2';
            
            reportModal.show();
        });

        document.getElementById('submit-report-btn')?.addEventListener('click', async function() {
            const btn = this;
            const productId = btn.dataset.productId;
            const store = document.getElementById('report-store-select').value;
            const priceStr = document.getElementById('report-price-input').value;
            const note = document.getElementById('report-note-input').value;
            const feedback = document.getElementById('report-feedback');
            
            if (!priceStr || isNaN(parseFloat(priceStr))) {
                feedback.textContent = 'Please enter a valid price.';
                feedback.className = 'text-danger d-block mt-2';
                return;
            }
            
            const originalText = btn.innerHTML;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Submitting...';
            btn.disabled = true;
            
            try {
                const res = await fetch('/api/community-price-report', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        product_id: productId,
                        store_name: store,
                        observed_price: parseFloat(priceStr),
                        note: note
                    })
                });
                const data = await res.json();
                
                if (data.success) {
                    feedback.textContent = 'Report submitted successfully. Thank you!';
                    feedback.className = 'text-success d-block mt-2';
                    setTimeout(() => reportModal.hide(), 1500);
                } else {
                    feedback.textContent = data.message || 'Error submitting report.';
                    feedback.className = 'text-danger d-block mt-2';
                }
            } catch (err) {
                feedback.textContent = 'Network error.';
                feedback.className = 'text-danger d-block mt-2';
            } finally {
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        });
    }
