// "Enable notifications on this device" button on the admin Notifications page.
(function () {
  var button = document.getElementById('push-enable');
  var status = document.getElementById('push-status');
  if (!button) return;

  function say(text, kind) {
    status.className = 'flash flash-' + (kind || 'info');
    status.textContent = text;
  }

  function keyToBytes(base64) {
    var padding = '='.repeat((4 - (base64.length % 4)) % 4);
    var raw = atob((base64 + padding).replace(/-/g, '+').replace(/_/g, '/'));
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }

  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
    button.disabled = true;
    say('This browser can\'t receive notifications. On an iPhone, add the app to your Home Screen first, then open it from there.', 'error');
    return;
  }

  button.addEventListener('click', async function () {
    button.disabled = true;
    try {
      var permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        say('Notifications are blocked. Allow them in your browser\'s site settings, then try again.', 'error');
        return;
      }
      var reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
      await navigator.serviceWorker.ready;
      var sub = await reg.pushManager.getSubscription();
      if (!sub) {
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: keyToBytes(button.dataset.key),
        });
      }
      var res = await fetch(button.dataset.url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.csrfToken() },
        body: JSON.stringify(sub.toJSON()),
      });
      if (!res.ok) throw new Error('save failed');
      say('Notifications are on for this device. Tap "Send test push" to check.', 'success');
      setTimeout(function () { location.reload(); }, 1500);
    } catch (err) {
      say('Sorry, that didn\'t work. Please try again.', 'error');
    } finally {
      button.disabled = false;
    }
  });
})();
