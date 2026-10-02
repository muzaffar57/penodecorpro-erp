/* ════════════════════════════════════════════════════════════════════════════════════════════════════════════════
   tanlov.js — QIDIRUVLI TANLAGICH (kech120, zip 130 — E bosqichi 4-qism; audit G4-20, G5-19).

   NIMA UCHUN: katta korxonada oddiy ochiladigan ro'yxat (`<select>`) da 100+ material, 300 buyurtma, 60 loyiha — qidiruvsiz,
   kerakli qatorni topib bo'lmaydi (O'LCHANGAN — audit kech114: Kirim formasida 104 material, «Yangi qaytarish» da korxonaning
   HAMMA buyurtmalari, «Brak yozish» da hamma loyihalar). Retseptlar sahifasidagi tanlash panelidek — yozib topiladi.

   QANDAY: ASL `<select>` joyida qoladi (qiymat, `onchange`, forma, boshqa kod uni o'qiydi / yozadi) — faqat ko'rinmas bo'ladi;
   yonida tugma (tanlangan qator matni) va panel (qidiruv maydoni + ro'yxat). Tanlanganda `select.value` o'rnatiladi va `change`
   hodisasi yuboriladi — sahifaning eski mantig'i O'ZGARMAYDI. Asl ro'yxat o'zgarsa (`innerHTML`, `disabled`) yoki kod qiymatni
   o'zi yozsa (`select.value = …`) — tugma matni darhol yangilanadi.

   ISHLATISH: `<select data-qidiruvli>` (sahifa yuklanganda o'zi) yoki `qidiruvliTanlov(selectEl, {joy: "Qidirish…"})`.
   Ro'yxat panel BIRINCHI ochilganda yuklansin desa — `data-qidiruv-yukla="globalFunksiya"` (yoki `{yukla: fn}`).
   Qidiruv: qator matni + `data-qidiruv` (masalan telefon raqami) ichida, katta-kichik harf va tutuq belgisi farqsiz; faqat
   raqam yozilsa — raqamlar bo'yicha ham. Klaviatura: ↓ / ↑, Enter — tanlash, Esc — yopish (oyna ichida avval panel yopiladi —
   `data-yopish-ichki`, base.html). Panel maydon ostida suzadi; telefonda yoki chetini kesuvchi blok ichida — oqim ichida.
   Tekshiruv: tools/test_e_tanlov.py.
   ════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';
  var KORSATISH_CHEGARA = 300;     // ro'yxatda bir vaqtda chiziladigan qatorlar (qolgani — «yana N ta, qidiruvni aniqlashtiring»)
  var _hisob = 0;
  var _asl = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
  var _aslIndeks = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'selectedIndex');

  function norm(s) {
    return String(s || '').toLowerCase().replace(/[\u02bb\u02bc\u2018\u2019`]/g, "'").replace(/\s+/g, ' ').trim();
  }
  function raqam(s) { return String(s || '').replace(/\D/g, ''); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // Panel oqim ichida (maydon ostini suradi) — telefonda yoki eng yaqin chegaralovchi ajdod pastki chetni KESADIGAN bo'lsa
  // (`overflow-y: hidden` / `clip`); aylanuvchi blok (`auto` / `scroll`, oyna) ichida suzuvchi panel kesilmaydi.
  function oqimdami(w) {
    if (window.matchMedia && window.matchMedia('(max-width: 600px)').matches) return true;
    for (var e = w.parentElement; e && e !== document.body; e = e.parentElement) {
      var cs = window.getComputedStyle(e);
      // eng YAQIN chegaralovchi ajdod hal qiladi: aylanuvchi (`auto` / `scroll`) — panel uning ichida aylanadi (suzsa bo'ladi);
      // kesuvchi (`hidden` / `clip`) — oqim ichida. Faqat pastga kesish muhim (panel maydon kengligida).
      if (/(auto|scroll)/.test(cs.overflowY)) return false;
      if (/(hidden|clip)/.test(cs.overflowY)) return true;
    }
    return false;
  }

  function qidiruvliTanlov(sel, opts) {
    if (!sel || sel.tagName !== 'SELECT') return null;
    if (sel._qt) { sel._qt.yangila(); return sel._qt; }
    opts = opts || {};
    var id = sel.id || ('qt-asl-' + (++_hisob));
    if (!sel.id) sel.id = id;
    var w = document.createElement('div');
    w.className = 'qt';
    w.setAttribute('data-qt-uchun', id);
    w.innerHTML =
      '<button type="button" class="qt-maydon" aria-haspopup="listbox" aria-expanded="false">' +
        '<span class="qt-matn"></span><i class="ti ti-chevron-down" aria-hidden="true"></i></button>' +
      '<div class="qt-panel" hidden>' +
        '<div class="qt-qidiruv"><i class="ti ti-search" aria-hidden="true"></i>' +
          '<input type="text" inputmode="search" enterkeyhint="search" autocomplete="off" data-kiritish-emas aria-label="Qidirish" placeholder="' +
            esc(opts.joy || sel.getAttribute('data-qidiruv-joy') || 'Qidirish…') + '">' +
          '<button type="button" class="qt-yop" data-yopish-ichki aria-label="Yopish">✕</button></div>' +
        '<div class="qt-royxat" role="listbox" id="' + esc(id) + '-qt-royxat"></div>' +
        '<div class="qt-soni"></div>' +
      '</div>';
    sel.parentNode.insertBefore(w, sel.nextSibling);
    sel.classList.add('qt-asl');
    sel.setAttribute('tabindex', '-1');
    sel.setAttribute('aria-hidden', 'true');
    var tugma = w.querySelector('.qt-maydon');
    var panel = w.querySelector('.qt-panel');
    var kirit = w.querySelector('.qt-qidiruv input');
    var royxat = w.querySelector('.qt-royxat');
    var soni = w.querySelector('.qt-soni');
    var faol = -1, korinadi = [];
    var lbl = sel.id ? document.querySelector('label[for="' + sel.id.replace(/"/g, '\\"') + '"]') : null;
    if (lbl) {
      if (!lbl.id) lbl.id = id + '-qt-yorliq';
      tugma.setAttribute('aria-labelledby', lbl.id);
      lbl.addEventListener('click', function (e) { e.preventDefault(); if (!tugma.disabled) tugma.focus(); });
    }

    function yangila() {
      var o = sel.options[_aslIndeks.get.call(sel)];
      var m = o ? o.text : '';
      w.querySelector('.qt-matn').textContent = m || (opts.bosh || '— Tanlang —');
      w.classList.toggle('qt-bosh', !o || o.value === '');
      tugma.disabled = !!sel.disabled;
      tugma.title = m || '';
      tugma.style.borderColor = sel.style.borderColor || '';
      // sahifa asl ro'yxatni yashirsa (`select.style.display = 'none'`) — tanlagich ham yashirinadi
      w.style.display = sel.style.display === 'none' ? 'none' : '';
      if (w.style.display === 'none' && !panel.hidden) yop(false);
      if (!panel.hidden) chiz();
    }

    function bandlar() {
      var natija = [];
      for (var i = 0; i < sel.children.length; i++) {
        var c = sel.children[i];
        if (c.tagName === 'OPTGROUP') {
          for (var j = 0; j < c.children.length; j++) natija.push({o: c.children[j], g: c.label});
        } else if (c.tagName === 'OPTION') natija.push({o: c, g: null});
      }
      return natija;
    }

    function chiz() {
      var q = norm(kirit.value), qr = raqam(kirit.value);
      var hammasi = bandlar(), mos = [];
      for (var i = 0; i < hammasi.length; i++) {
        var o = hammasi[i].o;
        if (o.hidden) continue;
        if (q) {
          var matn = norm(o.text + ' ' + (o.getAttribute('data-qidiruv') || '') + ' ' + (hammasi[i].g || ''));
          var tm = qr.length >= 3 && raqam(o.text + ' ' + (o.getAttribute('data-qidiruv') || '')).indexOf(qr) >= 0;
          if (matn.indexOf(q) < 0 && !tm) continue;
        }
        mos.push(hammasi[i]);
      }
      korinadi = mos.slice(0, KORSATISH_CHEGARA);
      var joriy = _asl.get.call(sel), html = '', oldingiG;
      for (var k = 0; k < korinadi.length; k++) {
        var b = korinadi[k];
        if (b.g !== oldingiG && b.g) html += '<div class="qt-guruh" role="presentation">' + esc(b.g) + '</div>';
        oldingiG = b.g;
        var tanl = b.o.value === joriy && b.o.selected;
        html += '<div class="qt-band' + (b.o.value === '' ? ' qt-band-bosh' : '') + (b.o.disabled ? ' qt-ochiq-emas' : '') +
          (tanl ? ' qt-tanlangan' : '') + '" role="option" id="' + esc(id) + '-qt-' + k + '" data-i="' + k + '" aria-selected="' +
          (tanl ? 'true' : 'false') + '"' + (b.o.disabled ? ' aria-disabled="true"' : '') + '>' + esc(b.o.text) + '</div>';
      }
      if (!korinadi.length) html = '<div class="qt-yoq">Topilmadi</div>';
      royxat.innerHTML = html;
      var qolgan = mos.length - korinadi.length;
      soni.textContent = qolgan > 0 ? ('Yana ' + qolgan + ' ta — qidiruvni aniqlashtiring') : (q ? (mos.length + ' ta topildi') : '');
      soni.hidden = !soni.textContent;
      faol = -1;
      for (var t = 0; t < korinadi.length; t++) {
        if (korinadi[t].o.value === joriy && korinadi[t].o.selected) { faol = t; break; }
      }
      if (faol < 0 && q) faol = birinchiOchiq(0, 1);
      belgila(false);
    }

    function birinchiOchiq(bosh, qadam) {
      for (var i = bosh; i >= 0 && i < korinadi.length; i += qadam) if (!korinadi[i].o.disabled) return i;
      return -1;
    }

    function belgila(korsat) {
      var eski = royxat.querySelector('.qt-faol');
      if (eski) eski.classList.remove('qt-faol');
      if (faol < 0) { kirit.removeAttribute('aria-activedescendant'); return; }
      var el = royxat.querySelector('[data-i="' + faol + '"]');
      if (!el) return;
      el.classList.add('qt-faol');
      kirit.setAttribute('aria-activedescendant', el.id);
      if (korsat) { try { el.scrollIntoView({block: 'nearest'}); } catch (e) { /* ko'rinish — muhim emas */ } }
    }

    function och() {
      if (tugma.disabled || !panel.hidden) return;
      // ro'yxat kerak bo'lganda yuklanadi (`data-qidiruv-yukla="funksiya"` yoki `opts.yukla`) — kelgach kuzatuvchi qayta chizadi
      var yukla = opts.yukla || window[sel.getAttribute('data-qidiruv-yukla') || ''];
      if (typeof yukla === 'function') { try { yukla(); } catch (e) { /* ro'yxat yuklanmasa — borini ko'rsatadi */ } }
      document.querySelectorAll('.qt.qt-ochiq').forEach(function (x) { if (x !== w && x._yop) x._yop(false); });
      w.classList.toggle('qt-oqimda', oqimdami(w));
      panel.hidden = false;
      w.classList.add('qt-ochiq');
      tugma.setAttribute('aria-expanded', 'true');
      kirit.value = '';
      chiz();
      belgila(true);
      try { panel.scrollIntoView({block: 'nearest'}); } catch (e) { /* ko'rinish — muhim emas */ }
      // fokus DARHOL (foydalanuvchi bosishi ichida — telefonda klaviatura ochiladi; keyingi yozuv qidiruvga tushadi)
      try { kirit.focus({preventScroll: true}); } catch (e) { /* jim */ }
    }

    function yop(fokus) {
      if (panel.hidden) return;
      panel.hidden = true;
      w.classList.remove('qt-ochiq');
      tugma.setAttribute('aria-expanded', 'false');
      if (fokus !== false) { try { tugma.focus(); } catch (e) { /* jim */ } }
    }
    w._yop = yop;

    function tanla(i) {
      var b = korinadi[i];
      if (!b || b.o.disabled) return;
      var oldin = _asl.get.call(sel);
      b.o.selected = true;
      yop(true);
      yangila();
      if (oldin !== b.o.value || opts.harDoim) sel.dispatchEvent(new Event('change', {bubbles: true}));
    }

    tugma.addEventListener('click', function () { if (panel.hidden) och(); else yop(true); });
    tugma.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === ' ') { e.preventDefault(); och(); }
    });
    kirit.addEventListener('input', chiz);
    kirit.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); var n = birinchiOchiq(faol + 1, 1); if (n >= 0) { faol = n; belgila(true); } }
      else if (e.key === 'ArrowUp') { e.preventDefault(); var p = birinchiOchiq(faol - 1, -1); if (p >= 0) { faol = p; belgila(true); } }
      else if (e.key === 'Enter') { e.preventDefault(); if (faol >= 0) tanla(faol); }
      else if (e.key === 'Escape' || e.key === 'Esc') { e.preventDefault(); e.stopPropagation(); yop(true); }
      else if (e.key === 'Tab') { yop(false); }
    });
    w.querySelector('.qt-yop').addEventListener('click', function () { yop(true); });
    royxat.addEventListener('mousedown', function (e) { e.preventDefault(); });      // qidiruv maydonidan fokus ketmasin
    royxat.addEventListener('click', function (e) {
      var el = e.target.closest ? e.target.closest('.qt-band') : null;
      if (el) tanla(parseInt(el.getAttribute('data-i'), 10));
    });
    document.addEventListener('click', function (e) { if (!panel.hidden && !w.contains(e.target)) yop(false); }, true);

    // Kod qiymatni o'zi yozsa (`select.value = …`, `selectedIndex`) — tugma matni yangilanadi: prototip ilgagi (pastda,
    // `_qtIlgak`) shu `yangila` ni chaqiradi.
    sel.addEventListener('change', yangila);
    if (typeof MutationObserver === 'function') {
      new MutationObserver(yangila).observe(sel, {childList: true, subtree: true, attributes: true, characterData: true,
                                                  attributeFilter: ['disabled', 'style', 'selected', 'label', 'hidden']});
    }
    var api = {yangila: yangila, och: och, yop: yop, oram: w, tugma: tugma};
    sel._qt = api;
    yangila();
    return api;
  }

  // `select.value = …` / `selectedIndex = …` — kuzatuvchi (MutationObserver) buni ko'rmaydi. Ilgak PROTOTIPDA (HAR `<select>` uchun
  // asl xatti-harakat, faqat tanlagichli ro'yxatda tugma yangilanadi). NUSXANING o'z xossasi EMAS — jsdom (eski brauzer-sinovlari)
  // nusxaga yozilgan `value` xossasida qiymatni yo'qotadi (O'LCHANGAN: `el.value = '7'` → '').
  (function _qtIlgak() {
    try {
      Object.defineProperty(HTMLSelectElement.prototype, 'value', {configurable: true, enumerable: _asl.enumerable,
        get: _asl.get, set: function (v) { _asl.set.call(this, v); if (this._qt) this._qt.yangila(); }});
      Object.defineProperty(HTMLSelectElement.prototype, 'selectedIndex', {configurable: true, enumerable: _aslIndeks.enumerable,
        get: _aslIndeks.get, set: function (v) { _aslIndeks.set.call(this, v); if (this._qt) this._qt.yangila(); }});
    } catch (e) { /* ilgaksiz — `change` va kuzatuvchi yetarli */ }
  })();

  window.qidiruvliTanlov = qidiruvliTanlov;
  function hammasi() {
    document.querySelectorAll('select[data-qidiruvli]').forEach(function (s) { qidiruvliTanlov(s); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hammasi); else hammasi();
})();
