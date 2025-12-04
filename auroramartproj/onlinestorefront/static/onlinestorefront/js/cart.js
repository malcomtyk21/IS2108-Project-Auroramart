// Live-update selected subtotal for cart items
(function () {
    function parseFloatSafe(v) {
        var n = parseFloat(String(v).replace(/[^0-9.\-]+/g, ''));
        return isNaN(n) ? 0 : n;
    }

    function updateSelectedSubtotal() {
        var total = 0;
        var inputs = document.querySelectorAll('input[name="selected_items"][form="checkout-form"]');
        inputs.forEach(function (cb) {
            if (cb.checked) {
                total += parseFloatSafe(cb.dataset.lineTotal);
            }
        });
        var disp = document.getElementById('selected-subtotal');
        if (disp) disp.textContent = total.toFixed(2);
        var aria = document.getElementById('selected-subtotal-aria');
        if (aria) aria.textContent = '$' + total.toFixed(2);
    }

    function updateRecommendationsVisibility() {
        var inputs = document.querySelectorAll('input[name="selected_items"][form="checkout-form"]');
        inputs.forEach(function (cb) {
            var section = document.getElementById('complete-set-' + cb.value);
            if (!section) return;
            if (cb.checked) {
                section.classList.remove('d-none');
            } else {
                section.classList.add('d-none');
            }
        });
    }

    // Persist selected item ids in sessionStorage so selections survive page reloads
    var STORAGE_KEY = 'auroramart_cart_selected';

    function getSavedSelections() {
        try {
            var raw = sessionStorage.getItem(STORAGE_KEY);
            if (!raw) return [];
            var arr = JSON.parse(raw);
            if (!Array.isArray(arr)) return [];
            return arr.map(String);
        } catch (e) {
            return [];
        }
    }

    function saveSelections(ids) {
        try {
            sessionStorage.setItem(STORAGE_KEY, JSON.stringify(ids.map(String)));
        } catch (e) {
            // ignore storage errors
        }
    }

    function getCurrentSelectedIds() {
        var inputs = document.querySelectorAll('input[name="selected_items"][form="checkout-form"]');
        var out = [];
        inputs.forEach(function (cb) {
            if (cb.checked) out.push(String(cb.value));
        });
        return out;
    }

    document.addEventListener('DOMContentLoaded', function () {
        var inputs = document.querySelectorAll('input[name="selected_items"][form="checkout-form"]');
        // Restore previous selections (if any)
        var saved = getSavedSelections();
        inputs.forEach(function (cb) {
            if (saved.indexOf(String(cb.value)) !== -1) cb.checked = true;
            // ensure checkbox has dataset available (server filled it)
            if (!cb.dataset.lineTotal) {
                // As fallback, try to read sibling line total text
                var parent = cb.closest('.card-body');
                if (parent) {
                    var lineText = parent.querySelector('.text-end.small');
                    if (lineText) {
                        var m = lineText.textContent.match(/\$([0-9,.]+)/);
                        if (m) cb.dataset.lineTotal = m[1].replace(/,/g, '');
                    }
                }
            }
            cb.addEventListener('change', function () {
                updateSelectedSubtotal();
                updateRecommendationsVisibility();
                saveSelections(getCurrentSelectedIds());
            });
        });

        // Patch Select All / Clear All buttons to update subtotal after toggling and persist
        var selAll = document.querySelectorAll('button[onclick]');
        selAll.forEach(function (btn) {
            var onclick = btn.getAttribute('onclick') || '';
            if (onclick.indexOf('selected_items') !== -1) {
                // leave inline action but also attach event listener to persist
                btn.addEventListener('click', function () {
                    // small timeout to let inline onclick toggle checkboxes first
                    setTimeout(function () {
                        updateSelectedSubtotal();
                        updateRecommendationsVisibility();
                        saveSelections(getCurrentSelectedIds());
                    }, 10);
                });
            }
        });

        // expose updater for inline calls
        window.updateSelectedSubtotal = updateSelectedSubtotal;

        // Save selections when any form in the cart is submitted (quantity changes, removals)
        var cartForms = document.querySelectorAll('.container form');
        cartForms.forEach(function (f) {
            // skip checkout-form since it is submitting the selections intentionally
            if (f.id === 'checkout-form') return;
            f.addEventListener('submit', function () {
                saveSelections(getCurrentSelectedIds());
            });
        });

        // Submit quantity updates when the user finishes manual input.
        // Behavior: when a quantity input loses focus (blur) or the user presses Enter,
        // submit the enclosing form via requestSubmit(), but only if the value changed.
        var qtyInputs = document.querySelectorAll('input[name="quantity"]');
        qtyInputs.forEach(function (inp) {
            // remember original value so we only submit when changed
            inp.dataset.origValue = String(inp.value);

            inp.addEventListener('blur', function (ev) {
                try {
                    if (String(inp.value) !== inp.dataset.origValue) {
                        // requestSubmit is preferred (works with modern browsers)
                        if (typeof inp.form.requestSubmit === 'function') inp.form.requestSubmit();
                        else inp.form.submit();
                    }
                } catch (e) {
                    // ignore
                }
            });

            inp.addEventListener('keydown', function (ev) {
                if (ev.key === 'Enter') {
                    ev.preventDefault();
                    try {
                        if (typeof inp.form.requestSubmit === 'function') inp.form.requestSubmit();
                        else inp.form.submit();
                    } catch (e) { /* ignore */ }
                }
            });
        });

        // When the user submits the checkout form, clear saved selections because
        // the user is attempting to complete the checkout and cart items will be
        // removed server-side on success.
        var checkoutForm = document.getElementById('checkout-form');
        if (checkoutForm) {
            checkoutForm.addEventListener('submit', function () {
                try { sessionStorage.removeItem(STORAGE_KEY); } catch (e) { /* ignore */ }
            });
        }

        // initial calculation
        updateSelectedSubtotal();
        updateRecommendationsVisibility();
    });
})();
