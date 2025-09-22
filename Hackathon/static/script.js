// Common JavaScript functions can be added here.
document.addEventListener("DOMContentLoaded", function(){
  console.log("Custom JS loaded - All pages ready.");
});

function openSetAlert(pid, pname) {
  document.getElementById('alert_product_id').value = pid;
  document.getElementById('alert_product_name').value = pname;
  document.getElementById('setAlertModal').classList.add('show');
}
// Hide modal on submit or after alert set
document.getElementById('setAlertForm').onsubmit = function(e){
  e.preventDefault();
  fetch('/alerts', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({
      product_id: document.getElementById('alert_product_id').value,
      price_alert: document.getElementById('alert_price').value
    })
  })
  .then(r=>r.json())
  .then(res=>{
    document.getElementById('alertMsg').innerHTML = '<div class="alert alert-success">'+res.message+'</div>';
    setTimeout(()=>document.getElementById('setAlertModal').classList.remove('show'), 1000);
  });
};