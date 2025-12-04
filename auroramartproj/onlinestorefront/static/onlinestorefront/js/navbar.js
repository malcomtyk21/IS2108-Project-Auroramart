// Make the chevron toggle the dropdown on click/tap while keeping the label link navigational.
document.addEventListener('DOMContentLoaded', function () {
    // Expand/collapse category panels inside the categories dropdown
    var categoryToggles = document.querySelectorAll('.dropdown-category.has-children > .category-toggle');

    function closeAll(except) {
        document.querySelectorAll('.dropdown-category.has-children.open').forEach(function (li) {
            if (li === except) return;
            li.classList.remove('open');
            var toggle = li.querySelector('.category-toggle');
            var panel = li.querySelector('.subcategory-panel');
            if (toggle) toggle.setAttribute('aria-expanded', 'false');
            if (panel) panel.hidden = true;
        });
    }

    categoryToggles.forEach(function (btn) {
        btn.addEventListener('click', function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            var li = btn.closest('.dropdown-category.has-children');
            if (!li) return;
            var panel = li.querySelector('.subcategory-panel');
            var isOpen = li.classList.contains('open');
            if (!isOpen) {
                closeAll(li);
                li.classList.add('open');
                btn.setAttribute('aria-expanded', 'true');
                if (panel) panel.hidden = false;
            } else {
                li.classList.remove('open');
                btn.setAttribute('aria-expanded', 'false');
                if (panel) panel.hidden = true;
            }
        });
        // Keyboard accessibility
        btn.addEventListener('keydown', function (ev) {
            if (ev.key === 'Enter' || ev.key === ' ') {
                ev.preventDefault();
                ev.stopPropagation();
                btn.click();
            }
            // Collapse with Escape when focused
            if (ev.key === 'Escape') {
                var li = btn.closest('.dropdown-category.has-children');
                if (li && li.classList.contains('open')) {
                    li.classList.remove('open');
                    btn.setAttribute('aria-expanded', 'false');
                    var panel = li.querySelector('.subcategory-panel');
                    if (panel) panel.hidden = true;
                }
            }
        });
    });

    // Click outside closes panels (Bootstrap closes parent dropdown already; we just ensure panels reset)
    document.addEventListener('click', function (ev) {
        if (!ev.target.closest('.dropdown-menu')) {
            closeAll();
        }
    });

    // When Bootstrap hides the entire dropdown (e.g., user clicks elsewhere), also collapse panels.
    document.querySelectorAll('.dropdown').forEach(function (dd) {
        dd.addEventListener('hide.bs.dropdown', function () { closeAll(); });
    });
});
