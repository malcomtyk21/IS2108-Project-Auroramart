// Simple accessible lightbox for product images
(function(){
  function qs(sel, ctx){ return (ctx || document).querySelector(sel); }
  function qsa(sel, ctx){ return Array.from((ctx || document).querySelectorAll(sel)); }

  document.addEventListener('DOMContentLoaded', function(){
    var overlay = document.createElement('div');
    overlay.className = 'lightbox-overlay';
    overlay.setAttribute('role','dialog');
    overlay.setAttribute('aria-modal','true');
    overlay.innerHTML = '\n      <button class="lightbox-close" aria-label="Close image">\u00d7</button>\n      <div class="lightbox-content" tabindex="0"></div>\n    ';
    document.body.appendChild(overlay);

    var content = qs('.lightbox-content', overlay);
    var closeBtn = qs('.lightbox-close', overlay);

    function openLightbox(src, alt){
      content.innerHTML = '';
      var img = document.createElement('img');
      img.src = src;
      if(alt) img.alt = alt;
      else img.alt = '';
      content.appendChild(img);
      overlay.classList.add('open');
      // focus for keyboard
      closeBtn.focus();
      document.addEventListener('keydown', onKey);
    }

    function closeLightbox(){
      overlay.classList.remove('open');
      content.innerHTML = '';
      document.removeEventListener('keydown', onKey);
    }

    function onKey(e){
      if(e.key === 'Escape') closeLightbox();
      if(e.key === 'ArrowRight' || e.key === 'Right') {
        // no gallery navigation in this simple version
      }
    }

    overlay.addEventListener('click', function(e){
      if(e.target === overlay) closeLightbox();
    });
    closeBtn.addEventListener('click', closeLightbox);

    // attach to product images
    var imgs = qsa('.product-detail-image');
    imgs.forEach(function(img){
      img.style.willChange = 'transform';
      img.addEventListener('click', function(e){
        // open full-size image using actual src (prefer data-full if present)
        var src = img.getAttribute('data-full') || img.src;
        var alt = img.alt || img.getAttribute('alt') || '';
        openLightbox(src, alt);
      });
      img.addEventListener('keydown', function(e){ if(e.key === 'Enter' || e.key === ' ') { e.preventDefault(); img.click(); } });
      // make image focusable for keyboard
      if(!img.hasAttribute('tabindex')) img.setAttribute('tabindex','0');
    });
  });
})();
