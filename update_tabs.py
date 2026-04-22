with open("templates/admin_dashboard.html", "r") as f:
    text = f.read()

import re

old_block = """  <!-- Recent Activity / Feedback -->
  <div class="col-lg-8">
     <div class="card border-0 shadow-sm rounded-4 h-100">
        <div class="card-header bg-white border-bottom py-3 d-flex align-items-center justify-content-between">
           <h6 class="fw-bold mb-0">Recent Feedback</h6>
           <a href="{{ url_for('admin.admin_feedback_page') }}" class="btn btn-sm btn-primary rounded-pill px-3 shadow-sm fw-bold text-white">View All</a>
        </div>
        <div class="card-body p-0">
           {% if data.recent_feedback %}
           <ul class="list-group list-group-flush">
             {% for f in data.recent_feedback %}
             <li class="list-group-item px-4 py-3 border-light">
                <div class="d-flex w-100 justify-content-between align-items-start mb-1">
                   <strong class="text-dark">{{ f.user_email|default('Anonymous') }}</strong>
                   <span class="badge bg-light text-secondary rounded-pill fw-normal">{{ f.type|default('General') }}</span>
                </div>
                <p class="mb-1 text-muted small">{{ f.message|truncate(80) }}</p>
                <small class="text-secondary opacity-50" style="font-size: 0.75rem;">{{ f.timestamp }}</small>
             </li>
             {% endfor %}
           </ul>
           {% else %}
           <div class="h-100 d-flex flex-column align-items-center justify-content-center py-5 text-muted small">
              <i class="fas fa-inbox fs-1 opacity-25 mb-2"></i>
              No recent feedback.
           </div>
           {% endif %}
        </div>
     </div>
  </div>"""

new_block = """  <div class="col-lg-8">
     <div class="card border-0 shadow-sm rounded-4 h-100">
        <div class="card-header bg-white border-bottom py-3">
           <ul class="nav nav-pills card-header-pills" id="dashboardTabs" role="tablist">
              <li class="nav-item" role="presentation">
                 <button class="nav-link active fw-bold small" id="reports-tab" data-bs-toggle="tab" data-bs-target="#reports" type="button" role="tab" aria-controls="reports" aria-selected="true">Price Reports</button>
              </li>
              <li class="nav-item" role="presentation">
                 <button class="nav-link fw-bold small" id="feedback-tab" data-bs-toggle="tab" data-bs-target="#feedback" type="button" role="tab" aria-controls="feedback" aria-selected="false">Feedback</button>
              </li>
           </ul>
        </div>
        <div class="card-body p-0 tab-content" id="dashboardTabsContent">
           <!-- Price Reports Tab -->
           <div class="tab-pane fade show active" id="reports" role="tabpanel" aria-labelledby="reports-tab">
              {% if data.recent_reports %}
              <ul class="list-group list-group-flush">
                {% for r in data.recent_reports %}
                <li class="list-group-item px-4 py-3 border-light">
                   <div class="d-flex w-100 justify-content-between align-items-start mb-1">
                      <strong class="text-dark">{{ r.product_id|default('Unknown Product') }}</strong>
                      <span class="badge bg-danger text-white rounded-pill fw-normal">{{ r.store_name|default('Unknown') }}</span>
                   </div>
                   <p class="mb-1 text-muted small">Observed Price: <strong class="text-success">€{{ r.observed_price }}</strong></p>
                   <small class="text-secondary opacity-50" style="font-size: 0.75rem;">{{ r.created_at }}</small>
                </li>
                {% endfor %}
              </ul>
              {% else %}
              <div class="h-100 d-flex flex-column align-items-center justify-content-center py-5 text-muted small">
                 <i class="fas fa-file-invoice-dollar fs-1 opacity-25 mb-2"></i>
                 No recent price reports.
              </div>
              {% endif %}
           </div>
           <!-- Feedback Tab -->
           <div class="tab-pane fade" id="feedback" role="tabpanel" aria-labelledby="feedback-tab">
              {% if data.recent_feedback %}
              <ul class="list-group list-group-flush">
                {% for f in data.recent_feedback %}
                <li class="list-group-item px-4 py-3 border-light">
                   <div class="d-flex w-100 justify-content-between align-items-start mb-1">
                      <strong class="text-dark">{{ f.user_email|default('Anonymous') }}</strong>
                      <span class="badge bg-light text-secondary rounded-pill fw-normal">{{ f.type|default('General') }}</span>
                   </div>
                   <p class="mb-1 text-muted small">{{ f.message|truncate(80) }}</p>
                   <small class="text-secondary opacity-50" style="font-size: 0.75rem;">{{ f.timestamp }}</small>
                </li>
                {% endfor %}
              </ul>
              {% else %}
              <div class="h-100 d-flex flex-column align-items-center justify-content-center py-5 text-muted small">
                 <i class="fas fa-inbox fs-1 opacity-25 mb-2"></i>
                 No recent feedback.
              </div>
              {% endif %}
           </div>
        </div>
     </div>
  </div>"""

if old_block in text:
    print("Found old block!")
    text = text.replace(old_block, new_block)
    with open("templates/admin_dashboard.html", "w") as f:
        f.write(text)
else:
    print("Could not find old block :(")
