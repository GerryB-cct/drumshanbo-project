// Small helpers used on every page. The app works without JavaScript; this only adds extras.
(function () {
  // Register the service worker (PWA: installable, offline page, push).
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {});
    });
  }

  // Forms with data-confirm ask "are you sure?" before submitting.
  document.addEventListener('submit', function (e) {
    var form = e.target;
    var message = form.getAttribute('data-confirm');
    if (message && !window.confirm(message)) {
      e.preventDefault();
    }
  });

  // Stop double taps submitting a form twice.
  document.addEventListener('submit', function (e) {
    if (e.defaultPrevented) return;
    var form = e.target;
    if (form.dataset.submitted) { e.preventDefault(); return; }
    form.dataset.submitted = '1';
    setTimeout(function () { delete form.dataset.submitted; }, 4000);
  });
})();

window.csrfToken = function () {
  var meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : '';
};
