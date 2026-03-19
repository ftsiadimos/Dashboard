// Auto-dismiss flash messages
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.flash').forEach(el => {
        setTimeout(() => {
            el.style.transition = 'opacity 0.4s ease';
            el.style.opacity = '0';
            setTimeout(() => el.remove(), 400);
        }, 3500);
    });

    // ── Live API stats for app tiles ─────────────────────────────────────────
    function fetchStats(card) {
        const appId = card.dataset.apiId;
        const statsEl = document.getElementById('stats-' + appId);
        if (!statsEl) return;

        fetch('/api/app/' + encodeURIComponent(appId) + '/stats')
            .then(r => r.json())
            .then(data => {
                if (data.ok) {
                    const display = String(data.display || '');

                    // Blink the card when the display indicates active alerts (>0).
                    // This uses a heuristic: the display must contain the word "alert" and a numeric count.
                    const hasAlertWord = /\balerts?\b/i.test(display);
                    const counts = (display.match(/\d+/g) || [])
                        .map(n => parseInt(n, 10))
                        .filter(n => !Number.isNaN(n));
                    const alertCount = counts.length ? Math.max(...counts) : 0;
                    const isAlert = hasAlertWord && alertCount > 0;

                    card.classList.toggle('has-alerts-warning', isAlert && alertCount <= 2);
                    card.classList.toggle('has-alerts-danger', isAlert && alertCount >= 3);
                    card.classList.toggle('has-alerts', isAlert);

                    const statsVal = '<span class="stats-value">' + escapeHtml(display) + '</span>';
                    statsEl.innerHTML = statsVal;
                } else {
                    card.classList.remove('has-alerts');
                    statsEl.innerHTML = '<span class="stats-error">' + escapeHtml(data.display) + '</span>';
                }
            })
            .catch(() => {
                card.classList.remove('has-alerts');
                statsEl.innerHTML = '<span class="stats-error">Fetch failed</span>';
            });
    }

    function escapeHtml(str) {
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    }

    document.querySelectorAll('.app-card[data-api-id]').forEach(card => {
        // Initial fetch
        fetchStats(card);
        // Recurring refresh
        const interval = Math.max(5, parseInt(card.dataset.apiInterval, 10) || 30);
        setInterval(() => fetchStats(card), interval * 1000);
    });

    // keep navbar collapse state across reloads
    const navbar = document.querySelector('.navbar');
    const toggleBtn = document.getElementById('navbarToggle');
    if (toggleBtn) {
        // restore previous state
        if (localStorage.getItem('navbarCollapsed') === 'true' && navbar) {
            navbar.classList.add('collapsed');
        }
        toggleBtn.addEventListener('click', () => {
            if (navbar) {
                navbar.classList.toggle('collapsed');
                localStorage.setItem('navbarCollapsed', navbar.classList.contains('collapsed'));
            }
        });
    }

    // enable drag-and-drop reorder for every grid
    function makeGridSortable(grid) {
        let dragging = null;
        let dropTarget = null;

        const clearDropTarget = () => {
            if (dropTarget) {
                dropTarget.classList.remove('drop-target');
                dropTarget = null;
            }
        };

        grid.querySelectorAll('.app-card').forEach(card => {
            card.setAttribute('draggable', 'true');
            card.addEventListener('dragstart', e => {
                dragging = card;
                card.classList.add('dragging');
                e.dataTransfer.effectAllowed = 'move';
            });
            card.addEventListener('dragend', () => {
                card.classList.remove('dragging');
                dragging = null;
                clearDropTarget();
            });
            card.addEventListener('dragover', e => {
                e.preventDefault();
                if (card === dragging) return;
                if (dropTarget && dropTarget !== card) {
                    dropTarget.classList.remove('drop-target');
                }
                card.classList.add('drop-target');
                dropTarget = card;
            });
            card.addEventListener('dragleave', () => {
                if (card === dropTarget) {
                    clearDropTarget();
                }
            });
            card.addEventListener('drop', e => {
                e.preventDefault();
                clearDropTarget();
                if (dragging && dragging !== card) {
                    grid.insertBefore(dragging, card);
                    // send order
                    const ids = Array.from(grid.querySelectorAll('.app-card')).map(c => parseInt(c.dataset.id, 10));
                    fetch('/api/reorder', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ type: 'app', items: ids }),
                    });
                }
            });
        });
    }
    document.querySelectorAll('.app-grid').forEach(makeGridSortable);
});
