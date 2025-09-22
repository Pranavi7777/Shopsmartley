document.addEventListener('DOMContentLoaded', function(){
  const params = new URLSearchParams(window.location.search);
  const productId = params.get('product_id');
  if (!productId) return;

  const msg = document.getElementById('productMessage');

  function addVendorRow(v = {}) {
    const container = document.getElementById('vendorPriceRows');
    const idx = Date.now();
    const div = document.createElement('div');
    div.className = 'form-row mb-2 vendor-row';
    div.innerHTML = `
      <div class="col"><input class="form-control vendor_name" placeholder="Vendor name" value="${v.vendor_name||''}"></div>
      <div class="col"><input class="form-control vendor_website" placeholder="Vendor website" value="${v.vendor_website||''}"></div>
      <div class="col"><input class="form-control vendor_price" placeholder="Price" value="${v.price||''}"></div>
      <div class="col-auto"><button class="btn btn-sm btn-danger removeRow">Remove</button></div>
    `;
    container.appendChild(div);
    div.querySelector('.removeRow').addEventListener('click', ()=> div.remove());
  }

  // load product
  fetch(`/products/${productId}`).then(r => r.json()).then(prod => {
    document.getElementById('product_id').value = prod.product_id;
    document.getElementById('product_name').value = prod.product_name;
    document.getElementById('product_category').value = prod.category || '';
    (prod.vendors || []).forEach(v => addVendorRow({
      vendor_name: v.vendor_name, vendor_website: v.website_url || '', price: v.product_price || v.product_price
    }));
  }).catch(()=> msg.innerHTML = '<div class="alert alert-danger">Failed to load product</div>');

  document.getElementById('addVendorRow').addEventListener('click', ()=> addVendorRow());

  document.getElementById('productEditForm').addEventListener('submit', function(e){
    e.preventDefault();
    const vendors = [];
    const names = document.getElementsByClassName('vendor_name');
    const webs = document.getElementsByClassName('vendor_website');
    const prices = document.getElementsByClassName('vendor_price');
    for (let i=0;i<names.length;i++){
      if (!names[i].value) continue;
      vendors.push({
        vendor_name: names[i].value,
        vendor_website: webs[i].value,
        price: parseFloat(prices[i].value) || null
      });
    }
    fetch(`/products/${productId}`, {
      method: 'PUT',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        product_name: document.getElementById('product_name').value,
        category: document.getElementById('product_category').value,
        vendors: vendors
      })
    }).then(r => r.json()).then(res => {
      msg.innerHTML = '<div class="alert alert-success">'+res.message+'</div>';
    }).catch(()=> msg.innerHTML = '<div class="alert alert-danger">Save failed</div>');
  });

  document.getElementById('deleteProduct').addEventListener('click', function(){
    if (!confirm('Delete this product?')) return;
    fetch(`/products/${productId}`, { method: 'DELETE' })
      .then(r => r.json()).then(res => {
        alert(res.message);
        window.location = '/view-products';
      }).catch(()=> alert('Delete failed'));
  });

  // Assuming `data` is available in this scope
  let html = '';
  data.forEach(a => {
    html += `<li class="list-group-item">
      <b>${a.product_name}</b> (${a.category}) — Target Price: ₹${a.price_alert}
    </li>`;
  });
  document.getElementById('yourTargetElementId').innerHTML = html; // Replace with your actual element ID
});