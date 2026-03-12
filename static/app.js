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
                    const statsVal = '<span class="stats-value">' + escapeHtml(data.display) + '</span>';
                    statsEl.innerHTML = statsVal;
                } else {
                    statsEl.innerHTML = '<span class="stats-error">' + escapeHtml(data.display) + '</span>';
                }
            })
            .catch(() => {
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

    // enable drag-and-drop reorder for every grid
    function makeGridSortable(grid) {
        let dragging = null;
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
            });
            card.addEventListener('dragover', e => {
                e.preventDefault();
            });
            card.addEventListener('drop', e => {
                e.preventDefault();
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
