layout_content = """{% extends "base.html" %}

{% block body_class %}bg-light admin-dashboard-body{% endblock %}

{% block styles %}
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  .admin-dashboard-body {
    font-family: 'Inter', sans-serif;
    background-color: #f8fafc !important;
  }

  .sidebar {
    width: 260px;
    height: 100vh;
    position: fixed;
    top: 0;
    left: 0;
    background: #ffffff;
    border-right: 1px solid #e2e8f0;
    z-index: 1000;
    display: flex;
    flex-direction: column;
  }

  .sidebar-header {
    height: 70px;
    display: flex;
    align-items: center;
    padding: 0 1.5rem;
    border-bottom: 1px solid #e2e8f0;
    font-weight: 700;
    font-size: 1.25rem;
    color: #0f172a;
  }

  .sidebar-nav {
    flex: 1;
    overflow-y: auto;
    padding: 1.5rem 1rem;
  }

  .nav-item-admin {
    display: flex;
    align-items: center;
    padding: 0.75rem 1rem;
    color: #64748b;
    text-decoration: none;
    border-radius: 0.5rem;
    margin-bottom: 0.25rem;
    font-weight: 500;
    transition: all 0.2s ease-in-out;
  }

  .nav-item-admin i {
    width: 20px;
    margin-right: 12px;
    font-size: 1.1rem;
  }

  .nav-item-admin:hover, .nav-item-admin.active {
    background: #f1f5f9;
    color: #0ea5e9;
  }

  .nav-item-admin.active {
    background: #e0f2fe;
    color: #0284c7;
  }

  .main-content {
    margin-left: 260px;
    min-height: 100vh;
    padding: 2rem;
  }

  .admin-topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
  }

  .card-stat {
    border: none;
    border-radius: 1rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    transition: transform 0.2s;
  }
  
  .card-stat:hover {
    transform: translateY(-2px);
  }

  .stat-icon {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
  }
</style>
{% endblock %}

{% block content %}
<div class="sidebar">
  <div class="sidebar-header">
    <i class="fas fa-shopping-basket text-primary me-2"></i> Smart Admin
  </div>
  <div class="sidebar-nav">
    <div class="text-xs fw-bold text-uppercase text-muted mb-2 px-3">Overview</div>
    <a href="/admin" class="nav-item-admin {{ 'active' if request.path == '/admin' or request.path == '/admin/' else '' }}">
      <i class="fas fa-chart-pie"></i> Dashboard
    </a>
    
    <div class="text-xs fw-bold text-uppercase text-muted mb-2 px-3 mt-4">Catalog Management</div>
    <a href="/admin/products" class="nav-item-admin {{ 'active' if '/admin/products' in request.path and 'smart-import' not in request.path else '' }}">
      <i class="fas fa-box"></i> Products
    </a>
    <a href="/admin/products/smart-import" class="nav-item-admin {{ 'active' if 'smart-import' in request.path else '' }}">
      <i class="fas fa-magic"></i> Smart Import (AI)
    </a>
    <a href="/admin/categories" class="nav-item-admin {{ 'active' if '/admin/categories' in request.path else '' }}">
      <i class="fas fa-tags"></i> Categories
    </a>
    <a href="/admin/brands" class="nav-item-admin {{ 'active' if '/admin/brands' in request.path else '' }}">
      <i class="fas fa-copyright"></i> Brands
    </a>

    <div class="text-xs fw-bold text-uppercase text-muted mb-2 px-3 mt-4">System</div>
    <a href="/" class="nav-item-admin">
      <i class="fas fa-external-link-alt"></i> View Live Site
    </a>
  </div>
</div>

<div class="main-content">
  <div class="admin-topbar">
    <div>
      <h2 class="fw-bold text-dark m-0">{% block admin_title %}Dashboard{% endblock %}</h2>
      <p class="text-muted m-0">{% block admin_subtitle %}Manage your Smart-Grocery platform{% endblock %}</p>
    </div>
    <div>
      <button class="btn btn-outline-secondary me-2"><i class="fas fa-cog"></i> Settings</button>
      <div class="dropdown d-inline-block">
        <button class="btn btn-primary dropdown-toggle" type="button" data-bs-toggle="dropdown">
          <i class="fas fa-user-shield me-2"></i> Admin
        </button>
        <ul class="dropdown-menu dropdown-menu-end">
          <li><a class="dropdown-item" href="/logout">Logout</a></li>
        </ul>
      </div>
    </div>
  </div>

  {% include "partials/flash_messages.html" ignore missing %}

  {% block admin_content %}{% endblock %}
</div>
{% endblock %}"""

products_content = """{% extends "admin_layout.html" %}

{% block admin_title %}Products Directory{% endblock %}
{% block admin_subtitle %}Manage canonical products, brands, and search{% endblock %}

{% block admin_content %}
<div class="row mb-4 align-items-center">
    <div class="col-md-7">
        <form method="get" action="{{ url_for('admin.admin_products_page') }}" class="d-flex bg-white rounded-pill shadow-sm overflow-hidden p-1 border">
            <span class="ps-3 d-flex align-items-center text-muted"><i class="fas fa-search"></i></span>
            <input type="text" class="form-control border-0 shadow-none" name="q" value="{{ data.q or '' }}" placeholder="Search canonical products..." style="box-shadow: none;">
            <select class="form-select border-0 border-start bg-transparent text-muted" name="brand" style="width: auto; max-width: 180px; box-shadow: none;" onchange="this.form.submit()">
               <option value="">All Brands</option>
               {% for b in data.brands or [] %}
               <option value="{{ b.brandId }}" {% if request.args.get('brand') == b.brandId %}selected{% endif %}>{{ b.name_en or b.brandId }}</option>
               {% endfor %}
            </select>
            {% if data.q or request.args.get('brand') %}
            <a href="{{ url_for('admin.admin_products_page') }}" class="btn btn-light rounded-pill"><i class="fas fa-times text-muted"></i></a>
            {% endif %}
            <button type="submit" class="btn btn-primary rounded-pill px-4 ms-1 fw-bold">Search</button>
        </form>
    </div>
    <div class="col-md-5 text-md-end mt-3 mt-md-0">
        <a href="/admin/products/smart-import" class="btn btn-outline-primary rounded-pill px-3 shadow-sm fw-bold me-2">
            <i class="fas fa-magic me-1"></i> AI Import
        </a>
        <button class="btn btn-primary rounded-pill px-4 shadow-sm fw-bold" onclick="prepareProductModal('new')" data-bs-toggle="modal" data-bs-target="#productModal">
            <i class="fas fa-plus me-1"></i> New Product
        </button>
    </div>
</div>

<div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
    <div class="table-responsive">
        <table class="table table-hover align-middle mb-0 bg-white">
            <thead class="bg-light">
                <tr>
                    <th class="text-uppercase text-muted text-xs fw-bold py-3 ps-4">Product</th>
                    <th class="text-uppercase text-muted text-xs fw-bold py-3">Store Offers Mapping</th>
                    <th class="text-uppercase text-muted text-xs fw-bold py-3">Category</th>
                    <th class="text-uppercase text-muted text-xs fw-bold py-3">Brand</th>
                    <th class="text-uppercase text-muted text-xs fw-bold py-3 text-end pe-4">Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for p in data.products or [] %}
                <tr>
                    <td class="ps-4">
                        <div class="d-flex align-items-center">
                            <div class="me-3 bg-light rounded d-flex justify-content-center align-items-center overflow-hidden border" style="width: 48px; height: 48px;">
                                {% if p.image_url %}
                                <img src="{{ p.image_url }}" alt="..." style="width: 100%; height: 100%; object-fit: contain;">
                                {% else %}
                                <i class="fas fa-image text-muted text-opacity-50 fs-4"></i>
                                {% endif %}
                            </div>
                            <div>
                                <h6 class="mb-0 fw-bold text-dark">{{ p.name_en or p.name }}</h6>
                                <span class="text-muted small">ID: {{ p.productId[-6:] if p.productId else 'N/A' }} • {{ p.qty_str|default('N/A') }}</span>
                            </div>
                        </div>
                    </td>
                    <td>
                        <span class="badge bg-primary bg-opacity-10 text-primary border border-primary border-opacity-25 px-2 py-1">
                            <i class="fas fa-link me-1"></i> Linked Offers
                        </span>
                        <a href="#" class="text-xs ms-2 text-decoration-none fw-bold text-primary" title="Connecting to the canonical link editor UI">Manage ></a>
                    </td>
                    <td>
                        {% if p.categoryId %}
                        <span class="badge bg-secondary bg-opacity-10 text-secondary border border-secondary border-opacity-25 px-2 py-1"><i class="fas fa-tag me-1"></i>{{ p.categoryId }}</span>
                        {% else %}
                        <span class="text-muted small">None</span>
                        {% endif %}
                    </td>
                    <td>
                        {% if p.brandId %}
                        <span class="badge bg-secondary bg-opacity-10 text-secondary border border-secondary border-opacity-25 px-2 py-1">{{ p.brandId }}</span>
                        {% else %}
                        <span class="text-muted small">No Brand</span>
                        {% endif %}
                    </td>
                    <td class="text-end pe-4">
                        <button class="btn btn-sm btn-light border shadow-sm rounded-pill text-primary fw-bold px-3 btn-edit-product" onclick='prepareProductModal("edit", {"productId":"{{p.productId}}", "name_en": "{{p.name_en}}", "name_de": "{{p.name_de}}", "qty_str": "{{p.qty_str}}", "brandId": "{{p.brandId}}", "categoryId": "{{p.categoryId}}", "image_url": "{{p.image_url}}"})' data-bs-toggle="modal" data-bs-target="#productModal">
                            <i class="fas fa-pen"></i> Edit
                        </button>
                    </td>
                </tr>
                {% else %}
                <tr>
                    <td colspan="5" class="text-center py-5 text-muted">
                        <div class="mb-3"><i class="fas fa-box-open fs-1 text-muted text-opacity-50"></i></div>
                        <h6 class="fw-bold">No canonical products found.</h6>
                        <p class="small mb-0">Use the smart import or create a new product manually.</p>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<div class="d-flex justify-content-center align-items-center mb-5">
    {% set current_page = data.page|default(1) %}
    {% set total_pages = data.total_pages|default(1) %}
    
    {% if total_pages > 1 %}
      <nav aria-label="Page navigation">
        <ul class="pagination pagination-rounded shadow-sm">
          <li class="page-item {% if current_page <= 1 %}disabled{% endif %}">
            <a class="page-link border-0 text-dark fw-bold px-4" href="?page={{ current_page - 1 }}&q={{ data.q or '' }}&brand={{ request.args.get('brand', '') }}">Prev</a>
          </li>
          <li class="page-item disabled"><span class="page-link border-0 text-muted px-4">Page {{ current_page }} of {{ total_pages }}</span></li>
          <li class="page-item {% if current_page >= total_pages %}disabled{% endif %}">
            <a class="page-link border-0 text-dark fw-bold px-4" href="?page={{ current_page + 1 }}&q={{ data.q or '' }}&brand={{ request.args.get('brand', '') }}">Next</a>
          </li>
        </ul>
      </nav>
    {% endif %}
</div>

<!-- Modal: Product Editor -->
<div class="modal fade" id="productModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered modal-lg">
    <div class="modal-content border-0 rounded-4 shadow-lg">
      <div class="modal-header bg-light border-bottom-0 pb-0 pt-4 px-4">
        <h5 class="modal-title fw-bold text-dark d-flex align-items-center" id="productModalLabel">
            <div class="bg-primary text-white rounded-circle d-flex align-items-center justify-content-center me-2 shadow-sm" style="width: 32px; height: 32px; font-size: 0.9rem;"><i class="fas fa-box"></i></div>
            <span>New Canonical Product</span>
        </h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <form method="post" action="{{ url_for('admin.admin_save_product') }}">
        <div class="modal-body p-4">
           <input type="hidden" name="redirectTo" value="products">
           <input type="hidden" name="productId" id="field_productId">
           
           <div class="row g-4 mb-4">
              <div class="col-md-8">
                 <label class="form-label small fw-bold text-muted text-uppercase mb-1">Product Name (EN) <span class="text-danger">*</span></label>
                 <input type="text" class="form-control form-control-lg bg-light border" name="name_en" id="field_name_en" placeholder="e.g. Full-fat Milk" required>
              </div>
              <div class="col-md-4">
                 <label class="form-label small fw-bold text-muted text-uppercase mb-1">Size / Quantity</label>
                 <input type="text" class="form-control form-control-lg bg-light border" name="qty_str" id="field_qty_str" placeholder="e.g. 1L">
              </div>
           </div>
           
           <div class="mb-4">
              <label class="form-label small fw-bold text-muted text-uppercase mb-1">Local Name (DE)</label>
              <input type="text" class="form-control form-control-lg bg-light border" name="name_de" id="field_name_de" placeholder="e.g. Vollmilch">
           </div>
           
           <div class="row g-4 mb-4">
              <div class="col-md-6">
                 <label class="form-label small fw-bold text-muted text-uppercase mb-1">Brand Mapping</label>
                 <select class="form-select form-control-lg bg-light border" name="brandId" id="field_brandSelect">
                    <option value="">(No Brand)</option>
                    {% for b in data.brands %}
                    <option value="{{ b.brandId }}">{{ b.name_en or b.brandId }}</option>
                    {% endfor %}
                 </select>
              </div>
              <div class="col-md-6">
                 <label class="form-label small fw-bold text-muted text-uppercase mb-1">Category Mapping</label>
                 <select class="form-select form-control-lg bg-light border" name="categoryId" id="field_categorySelect">
                    <option value="">(Uncategorized)</option>
                    {% for c in data.categories %}
                    <option value="{{ c.categoryId }}">{{ c.name_en or c.categoryId }}</option>
                    {% endfor %}
                 </select>
              </div>
           </div>
           
           <div class="mb-2">
              <label class="form-label small fw-bold text-muted text-uppercase mb-1">Image URL</label>
              <div class="input-group input-group-lg bg-light border rounded">
                 <span class="input-group-text bg-transparent border-0"><i class="fas fa-image text-muted"></i></span>
                 <input type="text" class="form-control bg-transparent border-0 ps-0 shadow-none" name="image_url" id="field_image_url" placeholder="https://...">
              </div>
              <small class="text-muted mt-2 d-block"><i class="fas fa-info-circle me-1"></i>For legal safety, ensure you own this image or it is a generic category icon.</small>
           </div>
        </div>
        <div class="modal-footer border-top-0 px-4 pb-4 pt-0 justify-content-between">
           <button type="button" class="btn btn-light rounded-pill px-4 fw-bold shadow-sm" data-bs-dismiss="modal">Cancel</button>
           <div class="d-flex gap-2">
              <button type="submit" formaction="" class="btn btn-outline-danger rounded-pill px-4 fw-bold shadow-sm d-none" id="btn_delete_prod" onclick="return confirm('Delete this canonical product entirely? This breaks store mappings.')"><i class="fas fa-trash-alt me-1"></i> Delete</button>
              <button type="submit" class="btn btn-primary rounded-pill px-4 fw-bold shadow-sm"><i class="fas fa-save me-1"></i> Save Product</button>
           </div>
        </div>
      </form>
    </div>
  </div>
</div>

<script>
function prepareProductModal(mode, product) {
   const label = document.getElementById('productModalLabel').querySelector('span');
   const delBtn = document.getElementById('btn_delete_prod');
   
   if (mode === 'new' || !product) {
      label.innerText = "Create New Canonical Product";
      document.getElementById('field_productId').value = '';
      document.getElementById('field_name_en').value = '';
      document.getElementById('field_qty_str').value = '';
      document.getElementById('field_name_de').value = '';
      document.getElementById('field_brandSelect').value = '';
      document.getElementById('field_categorySelect').value = '';
      document.getElementById('field_image_url').value = '';
      delBtn.classList.add('d-none');
      delBtn.removeAttribute('formaction');
   } else {
      label.innerText = `Edit: ${product.name_en || product.name || 'Product'}`;
      document.getElementById('field_productId').value = product.productId || '';
      document.getElementById('field_name_en').value = product.name_en || product.name || '';
      document.getElementById('field_qty_str').value = product.qty_str || '';
      document.getElementById('field_name_de').value = product.name_de || '';
      document.getElementById('field_brandSelect').value = product.brandId || '';
      document.getElementById('field_categorySelect').value = product.categoryId || '';
      document.getElementById('field_image_url').value = product.image_url || '';
      delBtn.classList.remove('d-none');
      delBtn.setAttribute('formaction', `/admin/products/delete/${product.productId}`);
   }
}
</script>
{% endblock %}"""

brands_content = """{% extends "admin_layout.html" %}

{% block admin_title %}Brands Directory{% endblock %}
{% block admin_subtitle %}Manage all available brands for the catalog{% endblock %}

{% block admin_content %}
<div class="row mb-4 align-items-center">
    <div class="col-md-8">
        <!-- Optional search or filters could go here in the future -->
    </div>
    <div class="col-md-4 text-md-end">
        <button class="btn btn-primary rounded-pill px-4 shadow-sm fw-bold" onclick="prepareBrandModal('new')" data-bs-toggle="modal" data-bs-target="#brandModal">
            <i class="fas fa-plus me-1"></i> New Brand
        </button>
    </div>
</div>

<div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
    <div class="table-responsive">
        <table class="table table-hover align-middle mb-0 bg-white">
            <thead class="bg-light">
                <tr>
                    <th class="text-uppercase text-muted text-xs fw-bold py-3 ps-4">Brand Information</th>
                    <th class="text-uppercase text-muted text-xs fw-bold py-3">Slug</th>
                    <th class="text-uppercase text-muted text-xs fw-bold py-3 text-end pe-4">Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for b in data.brands or [] %}
                <tr>
                    <td class="ps-4">
                        <div class="d-flex align-items-center">
                            <div class="me-3 bg-light rounded d-flex justify-content-center align-items-center overflow-hidden border" style="width: 48px; height: 48px;">
                                {% if b.image_url %}
                                <img src="{{ b.image_url }}" alt="..." style="width: 100%; height: 100%; object-fit: contain;">
                                {% else %}
                                <i class="fas fa-copyright text-muted text-opacity-50 fs-4"></i>
                                {% endif %}
                            </div>
                            <div>
                                <h6 class="mb-0 fw-bold text-dark">{{ b.name_en or b.brandId }}</h6>
                                {% if b.name_de %}
                                <span class="text-muted small">{{ b.name_de }}</span>
                                {% endif %}
                            </div>
                        </div>
                    </td>
                    <td>
                        <span class="badge bg-secondary bg-opacity-10 text-secondary border border-secondary border-opacity-25 px-2 py-1">{{ b.brandId }}</span>
                    </td>
                    <td class="text-end pe-4">
                        <button class="btn btn-sm btn-light border shadow-sm rounded-pill text-primary fw-bold px-3" onclick='prepareBrandModal("edit", {"brandId":"{{b.brandId}}", "name_en":"{{b.name_en}}", "name_de":"{{b.name_de}}", "image_url":"{{b.image_url}}"})' data-bs-toggle="modal" data-bs-target="#brandModal">
                            <i class="fas fa-pen"></i> Edit
                        </button>
                    </td>
                </tr>
                {% else %}
                <tr>
                    <td colspan="3" class="text-center py-5 text-muted">
                        <div class="mb-3"><i class="fas fa-copyright fs-1 text-muted text-opacity-50"></i></div>
                        <h6 class="fw-bold">No brands found.</h6>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<!-- Modal: Brand Editor -->
<div class="modal fade" id="brandModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content border-0 rounded-4 shadow-lg">
      <div class="modal-header bg-light border-bottom-0 pb-0 pt-4 px-4">
        <h5 class="modal-title fw-bold text-dark d-flex align-items-center" id="brandModalLabel">
            <div class="bg-primary text-white rounded-circle d-flex align-items-center justify-content-center me-2 shadow-sm" style="width: 32px; height: 32px; font-size: 0.9rem;"><i class="fas fa-copyright"></i></div>
            <span>Brand Details</span>
        </h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <form method="post" action="{{ url_for('admin.admin_save_brand') }}">
        <div class="modal-body p-4">
           <input type="hidden" name="brandId" id="field_brandId_hidden">
           
           <div class="mb-3">
              <label class="form-label small fw-bold text-muted text-uppercase mb-1">Brand Slug / ID <span class="text-danger">*</span></label>
              <input type="text" class="form-control form-control-lg bg-light border" name="brandId_new" id="field_brandId" placeholder="e.g. coca-cola" required>
              <small class="text-muted mt-1 text-xs">Used internally to link products. Must be unique.</small>
           </div>
           
           <div class="row g-3 mb-3">
              <div class="col-md-6">
                 <label class="form-label small fw-bold text-muted text-uppercase mb-1">Name (EN)</label>
                 <input type="text" class="form-control form-control-lg bg-light border" name="name_en" id="field_brand_name_en">
              </div>
              <div class="col-md-6">
                 <label class="form-label small fw-bold text-muted text-uppercase mb-1">Name (DE)</label>
                 <input type="text" class="form-control form-control-lg bg-light border" name="name_de" id="field_brand_name_de">
              </div>
           </div>

           <div class="mb-2">
              <label class="form-label small fw-bold text-muted text-uppercase mb-1">Logo URL</label>
              <div class="input-group input-group-lg bg-light border rounded">
                 <span class="input-group-text bg-transparent border-0"><i class="fas fa-image text-muted"></i></span>
                 <input type="text" class="form-control bg-transparent border-0 ps-0 shadow-none" name="image_url" id="field_brand_image" placeholder="https://...">
              </div>
           </div>
        </div>
        <div class="modal-footer border-top-0 px-4 pb-4 pt-0 justify-content-between">
           <button type="button" class="btn btn-light rounded-pill px-4 fw-bold shadow-sm" data-bs-dismiss="modal">Cancel</button>
           <div class="d-flex gap-2">
              <button type="submit" formaction="" class="btn btn-outline-danger rounded-pill px-4 fw-bold shadow-sm d-none" id="btn_delete_brand" onclick="return confirm('Delete this brand?')"><i class="fas fa-trash-alt me-1"></i> Delete</button>
              <button type="submit" class="btn btn-primary rounded-pill px-4 fw-bold shadow-sm"><i class="fas fa-save me-1"></i> Save Brand</button>
           </div>
        </div>
      </form>
    </div>
  </div>
</div>

<script>
function prepareBrandModal(mode, brand) {
   const label = document.getElementById('brandModalLabel').querySelector('span');
   const delBtn = document.getElementById('btn_delete_brand');
   
   if (mode === 'new' || !brand) {
      label.innerText = "Create New Brand";
      document.getElementById('field_brandId_hidden').value = '';
      document.getElementById('field_brandId').value = '';
      document.getElementById('field_brandId').readOnly = false;
      document.getElementById('field_brand_name_en').value = '';
      document.getElementById('field_brand_name_de').value = '';
      document.getElementById('field_brand_image').value = '';
      delBtn.classList.add('d-none');
      delBtn.removeAttribute('formaction');
   } else {
      label.innerText = `Edit: ${brand.name_en || brand.brandId}`;
      document.getElementById('field_brandId_hidden').value = brand.brandId || '';
      document.getElementById('field_brandId').value = brand.brandId || '';
      document.getElementById('field_brandId').readOnly = true; // Cannot edit slug once created
      document.getElementById('field_brand_name_en').value = brand.name_en || '';
      document.getElementById('field_brand_name_de').value = brand.name_de || '';
      document.getElementById('field_brand_image').value = brand.image_url || '';
      delBtn.classList.remove('d-none');
      delBtn.setAttribute('formaction', `/admin/brands/delete/${brand.brandId}`);
   }
}
</script>
{% endblock %}"""

categories_content = """{% extends "admin_layout.html" %}

{% block admin_title %}Categories Structure{% endblock %}
{% block admin_subtitle %}Manage taxonomy and global grocery catalog{% endblock %}

{% block admin_content %}
<div class="row mb-4 align-items-center">
    <div class="col-md-8">
    </div>
    <div class="col-md-4 text-md-end">
        <button class="btn btn-primary rounded-pill px-4 shadow-sm fw-bold" onclick="prepareCategoryModal('new')" data-bs-toggle="modal" data-bs-target="#categoryModal">
            <i class="fas fa-plus me-1"></i> New Category
        </button>
    </div>
</div>

<div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
    <div class="table-responsive">
        <table class="table table-hover align-middle mb-0 bg-white">
            <thead class="bg-light">
                <tr>
                    <th class="text-uppercase text-muted text-xs fw-bold py-3 ps-4">Category Name</th>
                    <th class="text-uppercase text-muted text-xs fw-bold py-3">Slug</th>
                    <th class="text-uppercase text-muted text-xs fw-bold py-3">Parent</th>
                    <th class="text-uppercase text-muted text-xs fw-bold py-3 text-end pe-4">Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for c in data.categories or [] %}
                <tr>
                    <td class="ps-4">
                        <h6 class="mb-0 fw-bold text-dark">{{ c.name_en or c.categoryId }}</h6>
                        {% if c.name_de %}
                        <span class="text-muted small">{{ c.name_de }}</span>
                        {% endif %}
                    </td>
                    <td>
                        <span class="badge bg-secondary bg-opacity-10 text-secondary border border-secondary border-opacity-25 px-2 py-1">{{ c.categoryId }}</span>
                    </td>
                    <td>
                        {% if c.parentId %}
                        <span class="badge bg-info bg-opacity-10 text-info border border-info border-opacity-25 px-2 py-1">{{ c.parentId }}</span>
                        {% else %}
                        <span class="text-muted small">Top Level</span>
                        {% endif %}
                    </td>
                    <td class="text-end pe-4">
                        <button class="btn btn-sm btn-light border shadow-sm rounded-pill text-primary fw-bold px-3" onclick='prepareCategoryModal("edit", {"categoryId":"{{c.categoryId}}", "name_en":"{{c.name_en}}", "name_de":"{{c.name_de}}", "parentId":"{{c.parentId}}"})' data-bs-toggle="modal" data-bs-target="#categoryModal">
                            <i class="fas fa-pen"></i> Edit
                        </button>
                    </td>
                </tr>
                {% else %}
                <tr>
                    <td colspan="4" class="text-center py-5 text-muted">
                        <div class="mb-3"><i class="fas fa-tags fs-1 text-muted text-opacity-50"></i></div>
                        <h6 class="fw-bold">No categories found.</h6>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<!-- Modal: Category Editor -->
<div class="modal fade" id="categoryModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content border-0 rounded-4 shadow-lg">
      <div class="modal-header bg-light border-bottom-0 pb-0 pt-4 px-4">
        <h5 class="modal-title fw-bold text-dark d-flex align-items-center" id="categoryModalLabel">
            <div class="bg-primary text-white rounded-circle d-flex align-items-center justify-content-center me-2 shadow-sm" style="width: 32px; height: 32px; font-size: 0.9rem;"><i class="fas fa-tags"></i></div>
            <span>Category Details</span>
        </h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <form method="post" action="{{ url_for('admin.admin_save_category') }}">
        <div class="modal-body p-4">
           <input type="hidden" name="categoryId" id="field_categoryId_hidden">
           
           <div class="mb-3">
              <label class="form-label small fw-bold text-muted text-uppercase mb-1">Category Slug / ID <span class="text-danger">*</span></label>
              <input type="text" class="form-control form-control-lg bg-light border" name="categoryId_new" id="field_categoryId" placeholder="e.g. dairy-eggs" required>
           </div>
           
           <div class="row g-3 mb-3">
              <div class="col-md-6">
                 <label class="form-label small fw-bold text-muted text-uppercase mb-1">Name (EN)</label>
                 <input type="text" class="form-control form-control-lg bg-light border" name="name_en" id="field_cat_name_en">
              </div>
              <div class="col-md-6">
                 <label class="form-label small fw-bold text-muted text-uppercase mb-1">Name (DE)</label>
                 <input type="text" class="form-control form-control-lg bg-light border" name="name_de" id="field_cat_name_de">
              </div>
           </div>

           <div class="mb-2">
              <label class="form-label small fw-bold text-muted text-uppercase mb-1">Parent Category</label>
              <select class="form-select form-control-lg bg-light border" name="parentId" id="field_cat_parentId">
                 <option value="">(None - Top Level)</option>
                 {% for c in data.categories %}
                 <option value="{{ c.categoryId }}">{{ c.name_en or c.categoryId }}</option>
                 {% endfor %}
              </select>
           </div>
        </div>
        <div class="modal-footer border-top-0 px-4 pb-4 pt-0 justify-content-between">
           <button type="button" class="btn btn-light rounded-pill px-4 fw-bold shadow-sm" data-bs-dismiss="modal">Cancel</button>
           <div class="d-flex gap-2">
              <button type="submit" formaction="" class="btn btn-outline-danger rounded-pill px-4 fw-bold shadow-sm d-none" id="btn_delete_cat" onclick="return confirm('Delete this category?')"><i class="fas fa-trash-alt me-1"></i> Delete</button>
              <button type="submit" class="btn btn-primary rounded-pill px-4 fw-bold shadow-sm"><i class="fas fa-save me-1"></i> Save Category</button>
           </div>
        </div>
      </form>
    </div>
  </div>
</div>

<script>
function prepareCategoryModal(mode, category) {
   const label = document.getElementById('categoryModalLabel').querySelector('span');
   const delBtn = document.getElementById('btn_delete_cat');
   
   if (mode === 'new' || !category) {
      label.innerText = "Create New Category";
      document.getElementById('field_categoryId_hidden').value = '';
      document.getElementById('field_categoryId').value = '';
      document.getElementById('field_categoryId').readOnly = false;
      document.getElementById('field_cat_name_en').value = '';
      document.getElementById('field_cat_name_de').value = '';
      document.getElementById('field_cat_parentId').value = '';
      delBtn.classList.add('d-none');
      delBtn.removeAttribute('formaction');
   } else {
      label.innerText = `Edit: ${category.name_en || category.categoryId}`;
      document.getElementById('field_categoryId_hidden').value = category.categoryId || '';
      document.getElementById('field_categoryId').value = category.categoryId || '';
      document.getElementById('field_categoryId').readOnly = true;
      document.getElementById('field_cat_name_en').value = category.name_en || '';
      document.getElementById('field_cat_name_de').value = category.name_de || '';
      document.getElementById('field_cat_parentId').value = category.parentId || '';
      delBtn.classList.remove('d-none');
      delBtn.setAttribute('formaction', `/admin/categories/delete/${category.categoryId}`);
   }
}
</script>
{% endblock %}"""

with open('templates/admin_layout.html', 'w') as f:
    f.write(layout_content)
with open('templates/admin_products.html', 'w') as f:
    f.write(products_content)
with open('templates/admin_brands.html', 'w') as f:
    f.write(brands_content)
with open('templates/admin_categories.html', 'w') as f:
    f.write(categories_content)

print("Files fixed and written successfully.")