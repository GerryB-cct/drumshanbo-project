// Add/edit book form: ISBN lookup (Open Library) and optional camera barcode scan.
(function () {
  var lookupBtn = document.getElementById('isbn-lookup');
  if (!lookupBtn) return;
  var isbnInput = document.getElementById('isbn');
  var result = document.getElementById('isbn-result');
  var cover = document.getElementById('cover-preview');
  var coverInput = document.getElementById('cover_url');

  function say(text, kind) {
    result.className = text ? 'flash flash-' + (kind || 'info') : '';
    result.style.marginTop = text ? '.75rem' : '';
    result.textContent = text || '';
  }

  function showCover(url) {
    if (url) { cover.src = url; cover.hidden = false; } else { cover.hidden = true; }
  }

  async function lookup() {
    var isbn = (isbnInput.value || '').replace(/[^0-9Xx]/g, '');
    if (isbn.length !== 10 && isbn.length !== 13) {
      say('Please type a 10 or 13 digit ISBN first.', 'error');
      return;
    }
    lookupBtn.disabled = true;
    say('Looking up…');
    try {
      var res = await fetch(lookupBtn.dataset.url + '?isbn=' + encodeURIComponent(isbn), { headers: { Accept: 'application/json' } });
      var data = await res.json();
      if (!data.ok) { say(data.message || 'Not found — enter details manually', 'error'); return; }
      isbnInput.value = data.isbn;
      document.getElementById('title').value = data.title || '';
      document.getElementById('author').value = data.author || '';
      coverInput.value = data.cover_url || '';
      showCover(data.cover_url);
      say('Found it. Please check the details, choose the type, then save.' + (data.warning ? ' ' + data.warning : ''), data.warning ? 'error' : 'success');
    } catch (e) {
      say('Couldn\'t look that up just now. Enter the details manually.', 'error');
    } finally {
      lookupBtn.disabled = false;
    }
  }

  lookupBtn.addEventListener('click', lookup);
  isbnInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') { e.preventDefault(); lookup(); }
  });
  coverInput.addEventListener('change', function () { showCover(coverInput.value); });

  // --- Barcode scanning (html5-qrcode, loaded only when needed) ---
  var scanBtn = document.getElementById('scan-btn');
  var scannerBox = document.getElementById('scanner');
  var scanner = null;
  var LIB = 'https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js';

  function loadLib() {
    return new Promise(function (resolve, reject) {
      if (window.Html5Qrcode) return resolve();
      var s = document.createElement('script');
      s.src = LIB; s.onload = resolve; s.onerror = reject;
      document.head.appendChild(s);
    });
  }

  async function stopScan() {
    if (scanner) { try { await scanner.stop(); } catch (e) {} scanner = null; }
    scannerBox.hidden = true;
    scanBtn.textContent = 'Scan barcode with camera';
  }

  scanBtn.addEventListener('click', async function () {
    if (scanner) { stopScan(); return; }
    try {
      await loadLib();
    } catch (e) {
      say('The barcode scanner couldn\'t load. Type the ISBN instead.', 'error');
      return;
    }
    scannerBox.hidden = false;
    scanBtn.textContent = 'Stop scanning';
    var F = window.Html5QrcodeSupportedFormats;
    scanner = new window.Html5Qrcode('scanner', { formatsToSupport: [F.EAN_13, F.EAN_8, F.UPC_A, F.UPC_E], verbose: false });
    try {
      await scanner.start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 260, height: 120 } },
        function (text) {
          isbnInput.value = text;
          stopScan();
          lookup();
        }
      );
    } catch (e) {
      say('Couldn\'t use the camera. Check camera permission, or type the ISBN.', 'error');
      stopScan();
    }
  });
})();
