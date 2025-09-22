document.addEventListener('DOMContentLoaded', function(){
  const params = new URLSearchParams(window.location.search);
  const vendorId = params.get('vendor_id');
  if (!vendorId) {
    document.getElementById('vendorEditForm').style.display = 'none';
    document.getElementById('vendorMessage').innerHTML = '<div class="alert alert-danger">No vendor selected.</div>';
    return;
  }
  const idInput = document.getElementById('vendor_id');
  const nameInput = document.getElementById('vendor_name');
  const websiteInput = document.getElementById('vendor_website');
  const msg = document.getElementById('vendorMessage');

  // load vendor
  fetch(`/vendors/${vendorId}`).then(r => r.json()).then(v => {
    idInput.value = vendorId;
    nameInput.value = v.vendor_name || '';
    websiteInput.value = v.website_url || '';
  }).catch(()=> msg.innerHTML = '<div class="alert alert-danger">Failed to load vendor</div>');

  // save
  document.getElementById('vendorEditForm').addEventListener('submit', function(e){
    e.preventDefault();
    fetch(`/vendors/${vendorId}`, {
      method: 'PUT',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        vendor_name: nameInput.value,
        website_url: websiteInput.value
      })
    }).then(r => r.json()).then(res => {
      msg.innerHTML = '<div class="alert alert-success">'+res.message+'</div>';
    }).catch(()=> msg.innerHTML = '<div class="alert alert-danger">Save failed</div>');
  });

  // delete
  document.getElementById('deleteVendor').addEventListener('click', function(){
    if (!confirm('Delete this vendor?')) return;
    fetch(`/vendors/${vendorId}`, { method: 'DELETE' })
      .then(r => r.json()).then(res => {
        alert(res.message);
        window.location = '/view-vendors';
      }).catch(()=> alert('Delete failed'));
  });
});