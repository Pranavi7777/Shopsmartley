document.addEventListener('DOMContentLoaded', function(){
  const form = document.getElementById('searchForm');
  const input = document.getElementById('searchQuery');
  const out = document.getElementById('searchResults');

  function render(results){
    if(!results || results.length===0){ out.innerHTML = '<p>No results</p>'; return; }
    let html = '<div class="row">';
    results.forEach(r => {
      html += `<div class="col-md-4"><div class="card mb-3">
        <div class="card-body">
          <h5 class="card-title">${r.platform}</h5>
          <p class="card-text">Price: ${r.price===null ? '<em>Not found</em>' : '₹'+r.price}</p>
          <a href="${r.url}" target="_blank" class="btn btn-sm btn-primary">Open ${r.platform}</a>
        </div></div></div>`;
    });
    html += '</div>';
    out.innerHTML = html;
  }

  form.addEventListener('submit', function(e){
    e.preventDefault();
    const q = input.value.trim();
    if(!q) return;
    out.innerHTML = '<div class="spinner-border" role="status"><span class="sr-only">Loading...</span></div>';
    fetch(`/search?q=${encodeURIComponent(q)}`)
      .then(r => r.json())
      .then(res => render(res.results || []))
      .catch(()=> out.innerHTML = '<div class="alert alert-danger">Search failed</div>');
  });
});