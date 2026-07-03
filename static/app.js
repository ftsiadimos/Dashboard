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
    const alertKeywords = (document.body.dataset.alertKeywords || 'alert,alerts').split(',').map(k => k.trim().toLowerCase()).filter(Boolean);

    function applyStats(card, data) {
        const appId  = card.dataset.apiId;
        const metaEl = document.getElementById('meta-' + appId);
        const statsEl = document.getElementById('stats-' + appId);
        if (!metaEl) return;

        if (data.ok) {
            const display = String(data.display || '');
            const normalized = display.toLowerCase();
            const hasAlertWord = alertKeywords.some(keyword => normalized.includes(keyword));
            const counts = (display.match(/\d+/g) || [])
                .map(n => parseInt(n, 10))
                .filter(n => !Number.isNaN(n));
            const alertCount = counts.length ? Math.max(...counts) : 0;
            const isAlert = hasAlertWord && alertCount > 0;

            card.classList.toggle('has-alerts-warning', isAlert && alertCount <= 2);
            card.classList.toggle('has-alerts-danger', isAlert && alertCount >= 3);
            card.classList.toggle('has-alerts', isAlert);

            if (statsEl) {
                statsEl.innerHTML = '<span class="stats-value">' + escapeHtml(display) + '</span>';
            }
            metaEl.textContent = display;
        } else {
            if (statsEl) {
                statsEl.innerHTML = '<span class="stats-error">' + escapeHtml(data.display) + '</span>';
            }
            card.classList.remove('has-alerts');
            metaEl.textContent = String(data.display || 'API error');
        }
    }

    // per-card abort controllers for polling requests
    const cardAborts = {};

    function fetchStats(card) {
        const appId = card.dataset.apiId;
        // cancel any in-flight request for this card
        if (cardAborts[appId]) cardAborts[appId].abort();
        const ctrl = new AbortController();
        cardAborts[appId] = ctrl;

        fetch('/api/app/' + encodeURIComponent(appId) + '/stats', {signal: ctrl.signal})
            .then(r => r.json())
            .then(data => { applyStats(card, data); })
            .catch(err => {
                if (err.name === 'AbortError') return; // superseded by newer request
                const statsEl = document.getElementById('stats-' + appId);
                card.classList.remove('has-alerts');
                if (statsEl) statsEl.innerHTML = '<span class="stats-error">Fetch failed</span>';
            });
    }

    function escapeHtml(str) {
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    }

    const apiCards = Array.from(document.querySelectorAll('.app-card[data-api-id]'));

    if (apiCards.length > 0) {
        // ── Initial load: one batch request instead of N individual ones ─────
        const ids = apiCards.map(c => parseInt(c.dataset.apiId, 10));
        fetch('/api/apps/stats/batch', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ids}),
        })
        .then(r => r.json())
        .then(data => {
            const results = data.results || {};
            apiCards.forEach(card => {
                const result = results[card.dataset.apiId];
                if (result) applyStats(card, result);
            });
        })
        .catch(() => {
            // fallback to individual fetches if batch fails
            apiCards.forEach(card => fetchStats(card));
        });

        // ── Recurring per-card polls ──────────────────────────────────────────
        apiCards.forEach(card => {
            const interval = Math.max(5, parseInt(card.dataset.apiInterval, 10) || 30);
            setInterval(() => fetchStats(card), interval * 1000);
        });
    }

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

    // ── Quake-style drop-down terminal ────────────────────────────────────────
    const qtPanel = document.getElementById('quake-terminal');
    if (qtPanel) {
        const qtOutput   = document.getElementById('qt-output');
        const qtInput    = document.getElementById('qt-input');
        const qtKeyHint  = document.getElementById('qt-key-hint');
        const qtCloseBtn = document.getElementById('qt-close-btn');

        const bd         = document.body.dataset;
        const triggerKey = bd.terminalKey || '`';
        // prefer localStorage override (set by drag), fall back to server setting
        const savedH     = parseInt(localStorage.getItem('qtHeight'), 10);
        const termHeight = Math.max(150, Math.min(900, savedH || parseInt(bd.terminalHeight, 10) || 400));

        qtPanel.style.height = termHeight + 'px';
        if (qtKeyHint) qtKeyHint.textContent = triggerKey === '`' ? '`/~' : triggerKey;

        // ── apply visual customisation from settings ──────────────────────────
        const opacity    = parseFloat(bd.terminalOpacity)   || 0.97;
        const fontSize   = parseInt(bd.terminalFontSize, 10) || 14;
        const fontFamily = bd.terminalFontFamily || 'monospace';
        const accent     = bd.terminalAccent    || '#6c8ebf';
        const animSpeed  = parseInt(bd.terminalAnimSpeed, 10) || 280;

        const fontStack = fontFamily === 'monospace'
            ? "'Courier New', Courier, monospace"
            : fontFamily === 'sans'
                ? "system-ui, -apple-system, sans-serif"
                : fontFamily === 'serif'
                    ? "Georgia, 'Times New Roman', serif"
                    : fontFamily; // custom value passed as-is

        qtPanel.style.setProperty('--qt-opacity',    opacity);
        qtPanel.style.setProperty('--qt-font-size',  fontSize + 'px');
        qtPanel.style.setProperty('--qt-font-family', fontStack);
        qtPanel.style.setProperty('--qt-accent',     accent);
        qtPanel.style.setProperty('--qt-anim-speed', animSpeed + 'ms');
        // apply immediately so first open already looks right
        qtPanel.style.background           = `rgba(8,10,18,${opacity})`;
        qtPanel.style.fontSize             = fontSize + 'px';
        qtPanel.style.fontFamily           = fontStack;
        qtPanel.style.borderBottomColor    = accent;
        qtPanel.style.transitionDuration   = animSpeed + 'ms';

        // ── resize-by-drag ────────────────────────────────────────────────────
        const qtResizeHandle = document.getElementById('qt-resize-handle');
        if (qtResizeHandle) {
            let dragStartY = 0;
            let dragStartH = 0;

            qtResizeHandle.addEventListener('mousedown', e => {
                e.preventDefault();
                dragStartY = e.clientY;
                dragStartH = qtPanel.offsetHeight;
                qtResizeHandle.classList.add('resizing');
                // disable transition while dragging so it tracks the mouse
                qtPanel.style.transition = 'none';

                function onMove(ev) {
                    const delta = ev.clientY - dragStartY;
                    const newH  = Math.max(150, Math.min(window.innerHeight - 40, dragStartH + delta));
                    qtPanel.style.height = newH + 'px';
                }
                function onUp() {
                    qtResizeHandle.classList.remove('resizing');
                    qtPanel.style.transition = '';
                    const finalH = qtPanel.offsetHeight;
                    localStorage.setItem('qtHeight', finalH);
                    document.removeEventListener('mousemove', onMove);
                    document.removeEventListener('mouseup', onUp);
                }
                document.addEventListener('mousemove', onMove);
                document.addEventListener('mouseup', onUp);
            });
        }

        let isOpen    = false;
        let appsCache = null;
        let customCmdsCache = null;

        // ── open / close ──────────────────────────────────────────────────────
        function qtOpen() {
            isOpen = true;
            qtPanel.classList.add('qt-open');
            qtPanel.removeAttribute('aria-hidden');
            qtInput.focus();
            if (!customCmdsCache) {
                fetch('/api/custom/commands')
                    .then(r => r.json())
                    .then(cmds => { customCmdsCache = cmds; })
                    .catch(() => {});
            }
        }
        function qtClose() {
            isOpen = false;
            qtPanel.classList.remove('qt-open');
            qtPanel.setAttribute('aria-hidden', 'true');
            qtInput.blur();
        }

        // ── output helpers ────────────────────────────────────────────────────
        function qtWrite(text, cls) {
            const line = document.createElement('div');
            line.className = 'qt-line' + (cls ? ' ' + cls : '');
            line.textContent = text;
            qtOutput.appendChild(line);
            qtOutput.scrollTop = qtOutput.scrollHeight;
        }
        function qtWriteEl(el) {
            qtOutput.appendChild(el);
            qtOutput.scrollTop = qtOutput.scrollHeight;
        }
        function qtClear() { qtOutput.innerHTML = ''; }

        // renders a line of AI text, turning URLs and markdown links into clickable anchors
        function qtWriteAI(text, cls) {
            const line = document.createElement('div');
            line.className = 'qt-line' + (cls ? ' ' + cls : '');
            // match [label](url) markdown links or bare http(s) URLs
            const urlRe = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|(https?:\/\/[^\s]+)/g;
            let last = 0, m;
            while ((m = urlRe.exec(text)) !== null) {
                if (m.index > last) {
                    line.appendChild(document.createTextNode(text.slice(last, m.index)));
                }
                const a = document.createElement('a');
                if (m[2]) {
                    // markdown [label](url)
                    a.textContent = m[1];
                    a.href = m[2];
                } else {
                    // bare URL
                    a.textContent = m[3];
                    a.href = m[3];
                }
                a.target = '_blank';
                a.rel = 'noopener noreferrer';
                line.appendChild(a);
                last = m.index + m[0].length;
            }
            if (last < text.length) {
                line.appendChild(document.createTextNode(text.slice(last)));
            }
            qtOutput.appendChild(line);
            qtOutput.scrollTop = qtOutput.scrollHeight;
        }

        // ── app-tile API loading ──────────────────────────────────────────────
        function renderAppRows(data) {
            if (!data.length) { qtWrite('No apps with API URLs configured.', 'qt-muted'); return; }
            qtWrite('API-enabled apps  (click to run, or: run <name>)', 'qt-info');
            data.forEach(app => {
                const row  = document.createElement('div');
                row.className = 'qt-line';
                const link = document.createElement('span');
                link.className = 'qt-app-row';
                link.innerHTML = '<span class="qt-app-icon">&#9654;</span>' + escapeHtml(app.title);
                link.title = app.api_url;
                link.addEventListener('click', () => { qtWrite('> run ' + app.title, 'qt-cmd'); runApp(app); });
                row.appendChild(link);
                qtOutput.appendChild(row);
            });
            qtOutput.scrollTop = qtOutput.scrollHeight;
        }

        function loadApps() {
            fetch('/api/apps')
                .then(r => r.json())
                .then(data => {
                    appsCache = data;
                    renderAppRows(data);
                })
                .catch(() => qtWrite('Failed to load app list.', 'qt-error'));
        }

        function runApp(app) {
            qtWrite('  calling ' + app.api_url + ' …', 'qt-muted');
            fetch('/api/app/' + encodeURIComponent(app.id) + '/stats')
                .then(r => r.json())
                .then(data => {
                    if (data.ok) {
                        qtWrite('[' + app.title + '] ' + (data.display || '(no data)'), 'qt-success');
                    } else {
                        qtWrite('[' + app.title + '] Error: ' + (data.display || 'unknown'), 'qt-error');
                    }
                })
                .catch(() => qtWrite('[' + app.title + '] Fetch failed', 'qt-error'));
        }

        // ── curl tokenizer (respects single/double quotes) ────────────────────
        function tokenize(str) {
            const tokens = [];
            let cur = '';
            let inQ = null;
            for (let i = 0; i < str.length; i++) {
                const ch = str[i];
                if (inQ) {
                    if (ch === inQ) { inQ = null; }
                    else { cur += ch; }
                } else if (ch === '"' || ch === "'") {
                    inQ = ch;
                } else if (ch === ' ' || ch === '\t') {
                    if (cur) { tokens.push(cur); cur = ''; }
                } else {
                    cur += ch;
                }
            }
            if (cur) tokens.push(cur);
            return tokens;
        }

        // Parse curl-style tokens into {method, url, headers (JSON str), payload}
        function parseCurl(tokens) {
            let method  = 'GET';
            let url     = null;
            let hdrs    = {};
            let payload = '';
            for (let i = 0; i < tokens.length; i++) {
                const t = tokens[i];
                if (t === '-X' || t === '--request') {
                    method = (tokens[++i] || 'GET').toUpperCase();
                } else if (t === '-H' || t === '--header') {
                    const h = tokens[++i] || '';
                    const ci = h.indexOf(':');
                    if (ci !== -1) hdrs[h.slice(0, ci).trim()] = h.slice(ci + 1).trim();
                } else if (t === '-d' || t === '--data' || t === '--data-raw') {
                    payload = tokens[++i] || '';
                    if (method === 'GET') method = 'POST';
                } else if (!t.startsWith('-')) {
                    url = t;
                }
            }
            return { method, url, headers: Object.keys(hdrs).length ? JSON.stringify(hdrs) : '', payload };
        }

        // ── split command on | respecting quotes (e.g. curl … | jq .x) ────────
        function splitPipe(str) {
            const parts = [];
            let cur = '';
            let inQ = null;
            for (let i = 0; i < str.length; i++) {
                const ch = str[i];
                if (inQ) {
                    if (ch === inQ) inQ = null;
                    cur += ch;
                } else if (ch === '"' || ch === "'") {
                    inQ = ch;
                    cur += ch;
                } else if (ch === '|') {
                    parts.push(cur.trim());
                    cur = '';
                } else {
                    cur += ch;
                }
            }
            if (cur.trim()) parts.push(cur.trim());
            return parts;
        }

        // ── minimal jq-style filter applied to parsed JSON ────────────────────
        // Supports: .  .key  .key.nested  .key[N]  .[N]  .key[]  length  keys  type  . | pipe
        function applyJq(data, filter) {
            filter = (filter || '').trim();
            // strip surrounding quotes added by shell-style quoting: jq '. | length'
            if ((filter.startsWith("'") && filter.endsWith("'")) ||
                (filter.startsWith('"') && filter.endsWith('"'))) {
                filter = filter.slice(1, -1).trim();
            }
            if (!filter || filter === '.') return JSON.stringify(data, null, 2);

            // handle piped expressions: `. | length`, `. | keys`, etc.
            if (filter.includes(' | ')) {
                const stages = filter.split(' | ');
                let cur = data;
                for (const stage of stages) {
                    const result = applyJq(cur, stage.trim());
                    try { cur = JSON.parse(result); } catch (_) { return result; }
                }
                if (typeof cur === 'object' && cur !== null) return JSON.stringify(cur, null, 2);
                return String(cur);
            }

            // built-in functions
            if (filter === 'length') {
                if (Array.isArray(data) || typeof data === 'string') return String(data.length);
                if (typeof data === 'object' && data !== null) return String(Object.keys(data).length);
                return 'null';
            }
            if (filter === 'keys') {
                if (typeof data === 'object' && data !== null && !Array.isArray(data))
                    return JSON.stringify(Object.keys(data), null, 2);
                return 'null';
            }
            if (filter === 'type') {
                if (data === null) return '"null"';
                if (Array.isArray(data)) return '"array"';
                return '"' + typeof data + '"';
            }

            // strip leading dot
            let path = filter.startsWith('.') ? filter.slice(1) : filter;
            if (!path) return JSON.stringify(data, null, 2);

            // parse path into segments: "a.b[2].c" → ["a","b","[2]","c"]
            const segs = [];
            let seg = '';
            for (let i = 0; i < path.length; i++) {
                const ch = path[i];
                if (ch === '.') {
                    if (seg) { segs.push(seg); seg = ''; }
                } else if (ch === '[') {
                    if (seg) { segs.push(seg); seg = ''; }
                    let bracket = '[';
                    i++;
                    while (i < path.length && path[i] !== ']') bracket += path[i++];
                    segs.push(bracket + ']');
                } else {
                    seg += ch;
                }
            }
            if (seg) segs.push(seg);

            let cur = data;
            for (let si = 0; si < segs.length; si++) {
                const s = segs[si];
                if (cur === null || cur === undefined) break;
                if (s.startsWith('[') && s.endsWith(']')) {
                    const inner = s.slice(1, -1);
                    if (inner === '') {
                        // .[] iterator — if more segments remain, map over each item
                        if (Array.isArray(cur)) {
                            const remaining = segs.slice(si + 1);
                            if (remaining.length === 0) {
                                return cur.map(v =>
                                    (typeof v === 'object' && v !== null)
                                        ? JSON.stringify(v, null, 2)
                                        : String(v)
                                ).join('\n');
                            }
                            // rebuild a sub-filter for the remaining path and apply per item
                            const subFilter = '.' + remaining.map(r => r.startsWith('[') ? r : r).join('.');
                            return cur.map(v => applyJq(v, subFilter)).join('\n');
                        }
                    } else {
                        cur = Array.isArray(cur) ? cur[parseInt(inner, 10)] : undefined;
                    }
                } else {
                    cur = (typeof cur === 'object' && cur !== null) ? cur[s] : undefined;
                }
            }
            if (cur === undefined || cur === null) return 'null';
            if (typeof cur === 'object') return JSON.stringify(cur, null, 2);
            return String(cur);
        }


        function qtRunCustom(req, label, jqFilter) {
            const tag = label || req.method + ' ' + req.url;
            const hint = jqFilter ? ' | jq ' + jqFilter : '';
            qtWrite('  ' + req.method + ' ' + req.url + hint + ' …', 'qt-muted');
            fetch('/api/custom/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(req),
            })
                .then(r => r.json())
                .then(data => {
                    const prefix = data.ok ? 'qt-success' : 'qt-error';
                    qtWrite('HTTP ' + data.status, prefix);
                    let output = data.body || '';
                    if (jqFilter && data.ok) {
                        try { output = applyJq(JSON.parse(data.body), jqFilter); } catch (_) {}
                    }
                    output.split('\n').slice(0, 200).forEach(l => qtWrite(l));
                    if (data.truncated) qtWrite('… (truncated)', 'qt-muted');
                })
                .catch(() => qtWrite('[' + tag + '] Fetch failed', 'qt-error'));
        }

        // ── save a custom command (upsert by name) ────────────────────────────
        function qtSaveCustom(name, req, jqFilter) {
            fetch('/api/custom/commands', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, ...req, jq_filter: jqFilter || '' }),
            })
                .then(r => r.json())
                .then(data => {
                    if (data.status === 'ok') { customCmdsCache = null; qtWrite('Saved "' + name + '"', 'qt-success'); }
                    else qtWrite('Save failed: ' + (data.error || 'unknown'), 'qt-error');
                })
                .catch(() => qtWrite('Save failed', 'qt-error'));
        }

        // ── list-custom: show all saved commands ──────────────────────────────
        function qtLoadCustom() {
            fetch('/api/custom/commands')
                .then(r => r.json())
                .then(cmds => {
                    customCmdsCache = cmds;
                    if (!cmds.length) { qtWrite('No saved custom commands.', 'qt-muted'); return; }
                    qtWrite('Saved custom commands  (click to run):', 'qt-info');
                    cmds.forEach(cmd => {
                        const row  = document.createElement('div');
                        row.className = 'qt-line qt-custom-row';

                        const runBtn = document.createElement('span');
                        runBtn.className = 'qt-app-row';
                        runBtn.innerHTML = '<span class="qt-app-icon">&#9654;</span>'
                            + escapeHtml(cmd.name)
                            + ' <span class="qt-muted-inline">' + escapeHtml(cmd.method) + ' ' + escapeHtml(cmd.url)
                            + (cmd.jq_filter ? ' | jq ' + escapeHtml(cmd.jq_filter) : '') + '</span>';
                        runBtn.title = cmd.method + ' ' + cmd.url + (cmd.jq_filter ? ' | jq ' + cmd.jq_filter : '');
                        runBtn.addEventListener('click', () => {
                            qtWrite('> run-custom ' + cmd.name, 'qt-cmd');
                            qtRunCustom({ method: cmd.method, url: cmd.url,
                                          headers: cmd.headers, payload: cmd.payload },
                                        cmd.name, cmd.jq_filter || null);
                        });

                        const delBtn = document.createElement('span');
                        delBtn.className = 'qt-del-btn';
                        delBtn.textContent = '✕';
                        delBtn.title = 'Delete ' + cmd.name;
                        delBtn.addEventListener('click', () => qtDeleteCustomById(cmd.id, cmd.name, row));

                        row.appendChild(runBtn);
                        row.appendChild(delBtn);
                        qtWriteEl(row);
                    });
                })
                .catch(() => qtWrite('Failed to load custom commands.', 'qt-error'));
        }

        // ── delete a saved command ────────────────────────────────────────────
        function qtDeleteCustomById(id, name, rowEl) {
            fetch('/api/custom/commands/' + id, { method: 'DELETE' })
                .then(r => r.json())
                .then(data => {
                    if (data.status === 'ok') {
                        customCmdsCache = null;
                        if (rowEl) rowEl.remove();
                        qtWrite('Deleted "' + name + '"', 'qt-success');
                    } else {
                        qtWrite('Delete failed: ' + (data.error || 'unknown'), 'qt-error');
                    }
                })
                .catch(() => qtWrite('Delete failed', 'qt-error'));
        }

        function qtDeleteCustomByName(name) {
            fetch('/api/custom/commands')
                .then(r => r.json())
                .then(cmds => {
                    const found = cmds.find(c => c.name.toLowerCase() === name.toLowerCase());
                    if (!found) { qtWrite('Not found: ' + name, 'qt-error'); return; }
                    qtDeleteCustomById(found.id, found.name, null);
                })
                .catch(() => qtWrite('Delete failed', 'qt-error'));
        }

        // ── command dispatcher ────────────────────────────────────────────────
        function handleCommand(raw) {
            const cmd = raw.trim();
            if (!cmd) return;
            qtWrite('> ' + cmd, 'qt-cmd');

            if (cmd === 'help') {
                qtWrite('Commands:', 'qt-info');
                qtWrite('  list                        – list API-enabled app tiles', 'qt-muted');
                qtWrite('  run <name>                  – call an app tile\'s API', 'qt-muted');
                qtWrite('  curl [opts] <url>           – run a custom HTTP request', 'qt-muted');
                qtWrite('    -X <METHOD>               – HTTP method (default GET)', 'qt-muted');
                qtWrite('    -H \'Key: Value\'           – add a header (repeatable)', 'qt-muted');
                qtWrite('    -d \'body\'                 – request body', 'qt-muted');
                qtWrite('    | jq <filter>             – pipe output through jq filter', 'qt-muted');
                qtWrite('    e.g.  curl http://host/api | jq .total', 'qt-muted');
                qtWrite('  save <name> curl [opts] <url> – save a curl command', 'qt-muted');
                qtWrite('  list-custom                 – show saved custom commands', 'qt-muted');
                qtWrite('  run-custom <name>           – run a saved custom command', 'qt-muted');
                qtWrite('  delete-custom <name>        – delete a saved command', 'qt-muted');
                qtWrite('  ask <question>              – ask the configured Ollama AI model', 'qt-muted');
                qtWrite('  chat                        – enter conversation mode with Ollama (keeps history)', 'qt-muted');
                qtWrite('  clear                       – clear this output', 'qt-muted');
                qtWrite('  search <query>              – filter tiles by name (no arg to reset)', 'qt-muted');
                qtWrite('Hotkeys:', 'qt-info');
                qtWrite('  Ctrl+Shift+F                – toggle fullscreen terminal', 'qt-muted');
                return;
            }

            if (cmd === 'clear')  { qtClear(); return; }

            if (cmd === 'list') {
                if (!appsCache) { loadApps(); return; }
                renderAppRows(appsCache);
                return;
            }

            if (cmd === 'list-custom') { qtLoadCustom(); return; }

            if (cmd.startsWith('run-custom ')) {
                const name = cmd.slice('run-custom '.length).trim().toLowerCase();
                fetch('/api/custom/commands')
                    .then(r => r.json())
                    .then(cmds => {
                        const found = cmds.find(c =>
                            c.name.toLowerCase() === name ||
                            c.name.toLowerCase().startsWith(name)
                        );
                        if (!found) { qtWrite('Custom command not found: ' + name, 'qt-error'); return; }
                        qtRunCustom({ method: found.method, url: found.url,
                                      headers: found.headers, payload: found.payload },
                                    found.name, found.jq_filter || null);
                    })
                    .catch(() => qtWrite('Failed to fetch custom commands.', 'qt-error'));
                return;
            }

            if (cmd.startsWith('delete-custom ')) {
                qtDeleteCustomByName(cmd.slice('delete-custom '.length).trim());
                return;
            }

            if (cmd.startsWith('ask ') || cmd === 'ask') {
                const question = cmd.startsWith('ask ') ? cmd.slice(4).trim() : '';
                if (!question) { qtWrite('Usage: ask <your question>', 'qt-error'); return; }
                qtAskOllama(question);
                return;
            }

            if (cmd === 'chat') {
                qtEnterChat();
                return;
            }

            if (cmd.startsWith('run ')) {
                const name = cmd.slice(4).trim().toLowerCase();
                if (!appsCache) { qtWrite('App list not loaded yet — try again.', 'qt-error'); return; }
                const app = appsCache.find(a =>
                    a.title.toLowerCase() === name ||
                    a.title.toLowerCase().startsWith(name)
                );
                if (!app) { qtWrite('App not found: ' + name, 'qt-error'); return; }
                runApp(app);
                return;
            }

            // save <name> curl ...
            if (cmd.startsWith('save ')) {
                const rest = cmd.slice(5).trim();
                const spaceIdx = rest.indexOf(' ');
                if (spaceIdx === -1) { qtWrite('Usage: save <name> curl [opts] <url>', 'qt-error'); return; }
                const saveName = rest.slice(0, spaceIdx).trim();
                const curlPart = rest.slice(spaceIdx + 1).trim();
                if (!curlPart.startsWith('curl')) {
                    qtWrite('Only curl commands can be saved. Usage: save <name> curl [opts] <url>', 'qt-error');
                    return;
                }
                // strip any | jq ... pipe before parsing — the curl part is everything before the first |
                const pipeParts = splitPipe(curlPart);
                const curlOnly  = pipeParts[0];
                let saveJqFilter = null;
                for (let i = 1; i < pipeParts.length; i++) {
                    const seg = pipeParts[i].trim();
                    if (seg === 'jq' || seg.startsWith('jq ')) {
                        saveJqFilter = seg.replace(/^jq\s*/, '').trim() || '.';
                    }
                }
                const tokens = tokenize(curlOnly).slice(1); // drop 'curl'
                const req = parseCurl(tokens);
                if (!req.url) { qtWrite('No URL found in curl command.', 'qt-error'); return; }
                qtSaveCustom(saveName, req, saveJqFilter);
                return;
            }

            // curl [opts] <url> [| jq <filter>]
            if (cmd.startsWith('curl ') || cmd === 'curl') {
                const parts    = splitPipe(cmd);
                const curlPart = parts[0];
                // parse optional  | jq <filter>
                let jqFilter = null;
                for (let i = 1; i < parts.length; i++) {
                    const seg = parts[i].trim();
                    if (seg === 'jq' || seg.startsWith('jq ')) {
                        jqFilter = seg.replace(/^jq\s*/, '').trim() || '.';
                    }
                }
                const tokens = tokenize(curlPart).slice(1); // drop 'curl'
                const req = parseCurl(tokens);
                if (!req.url) { qtWrite('Usage: curl [opts] <url> [| jq <filter>]', 'qt-error'); return; }
                qtRunCustom(req, null, jqFilter);
                return;
            }

            if (cmd.startsWith('search ') || cmd === 'search') {
                const query = cmd.startsWith('search ') ? cmd.slice(7).trim() : '';
                const allCards = Array.from(document.querySelectorAll('.app-card'));
                if (!query) {
                    allCards.forEach(card => { card.style.display = ''; });
                    document.querySelectorAll('.section').forEach(sec => { sec.style.display = ''; });
                    qtWrite('Search cleared — showing all tiles.', 'qt-muted');
                    return;
                }
                const lower = query.toLowerCase();
                let matches = 0;
                allCards.forEach(card => {
                    const titleEl = card.querySelector('.app-title');
                    const title = titleEl ? titleEl.textContent.toLowerCase() : '';
                    const visible = title.includes(lower);
                    card.style.display = visible ? '' : 'none';
                    if (visible) matches++;
                });
                document.querySelectorAll('.section').forEach(sec => {
                    const hasVisible = Array.from(sec.querySelectorAll('.app-card'))
                        .some(c => c.style.display !== 'none');
                    sec.style.display = hasVisible ? '' : 'none';
                });
                if (matches === 0) {
                    qtWrite('No tiles match "' + escapeHtml(query) + '".', 'qt-error');
                } else {
                    qtWrite(
                        'Showing ' + matches + ' tile' + (matches === 1 ? '' : 's') +
                        ' matching "' + escapeHtml(query) + '" — run search with no args to reset.',
                        'qt-success'
                    );
                }
                return;
            }

            qtWrite('Unknown command. Type "help" for a list.', 'qt-error');
        }

        // ── Ollama AI ─────────────────────────────────────────────────────────
        // Chat mode state
        let chatMode    = false;
        let chatHistory = [];   // [{role:'user'|'assistant', content:'...'}]

        const qtPromptEl = document.querySelector('.qt-prompt');

        function qtEnterChat() {
            chatMode    = true;
            chatHistory = [];
            qtPanel.classList.add('qt-chat-mode');
            qtPromptEl.textContent = '\u{1F916}';
            qtInput.placeholder = 'Chat with Ollama \u2014 type exit to leave\u2026';
            qtWrite('Entered chat mode. Type your message and press Enter.', 'qt-info');
            qtWrite('Type exit or /exit to leave \u00b7 /clear to reset conversation history.', 'qt-muted');
        }

        function qtExitChat() {
            chatMode    = false;
            chatHistory = [];
            qtPanel.classList.remove('qt-chat-mode');
            qtPromptEl.textContent = '>';
            qtInput.placeholder = "Type 'help' for commands\u2026";
            qtWrite('Left chat mode.', 'qt-muted');
        }

        const CHAT_HISTORY_LIMIT = Math.max(2, parseInt(bd.ollamaChatHistoryLimit, 10) || 20);

        async function qtChatSend(message) {
            chatHistory.push({role: 'user', content: message});
            // Trim oldest pairs to stay within the limit (always keep an even number so
            // user/assistant turns stay paired; system messages added server-side are excluded)
            if (chatHistory.length > CHAT_HISTORY_LIMIT) {
                chatHistory = chatHistory.slice(chatHistory.length - CHAT_HISTORY_LIMIT);
            }
            const thinkLine = document.createElement('div');
            thinkLine.className = 'qt-line qt-muted';
            thinkLine.textContent = 'Thinking\u2026';
            qtOutput.appendChild(thinkLine);
            qtOutput.scrollTop = qtOutput.scrollHeight;
            try {
                const resp = await fetch('/api/ollama/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({messages: chatHistory}),
                });
                const data = await resp.json();
                thinkLine.remove();
                if (!data.ok) {
                    qtWrite('\u26a0\ufe0f  ' + (data.error || 'Ollama error'), 'qt-error');
                    if (data.context_overflow) {
                        qtWrite('Tip: type /clear to reset conversation history and free context.', 'qt-muted');
                    }
                    chatHistory.pop(); // remove failed user message
                    return;
                }
                if (data.trimmed) {
                    qtWrite('(History was trimmed to fit the model context window.)', 'qt-muted');
                    chatHistory = chatHistory.slice(-4);
                }
                chatHistory.push({role: 'assistant', content: data.response});
                const lines = (data.response || '').split('\n');
                lines.forEach(l => qtWriteAI(l, 'qt-ai'));
            } catch (err) {
                thinkLine.remove();
                qtWrite('Network error: ' + err.message, 'qt-error');
                chatHistory.pop();
            }
        }

        async function qtAskOllama(question) {
            const thinkLine = document.createElement('div');
            thinkLine.className = 'qt-line qt-muted';
            thinkLine.textContent = 'Thinking\u2026';
            qtOutput.appendChild(thinkLine);
            qtOutput.scrollTop = qtOutput.scrollHeight;
            try {
                const resp = await fetch('/api/ollama/ask', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({prompt: question}),
                });
                const data = await resp.json();
                thinkLine.remove();
                if (!data.ok) {
                    qtWrite('\u26a0\ufe0f  ' + (data.error || 'Ollama error'), 'qt-error');
                    return;
                }
                const lines = (data.response || '').split('\n');
                lines.forEach(l => qtWriteAI(l, 'qt-ai'));
            } catch (err) {
                thinkLine.remove();
                qtWrite('Network error: ' + err.message, 'qt-error');
            }
        }

        // ── keyboard / button bindings ────────────────────────────────────────
        let qtMaximized = false;
        function qtToggleMaximize() {
            qtMaximized = !qtMaximized;
            if (qtMaximized) {
                qtPanel.dataset.prevHeight = qtPanel.style.height;
                qtPanel.style.height = '100vh';
                qtPanel.classList.add('qt-maximized');
            } else {
                qtPanel.style.height = qtPanel.dataset.prevHeight || (termHeight + 'px');
                qtPanel.classList.remove('qt-maximized');
            }
        }

        document.addEventListener('keydown', e => {
            if (e.key === 'Escape' && isOpen) {
                e.preventDefault();
                if (chatMode) { qtExitChat(); return; }
                qtClose();
                return;
            }
            if (e.ctrlKey && e.shiftKey && e.key === 'F') {
                e.preventDefault();
                if (!isOpen) qtOpen();
                qtToggleMaximize();
                return;
            }
            if (e.key === triggerKey) {
                const tag     = document.activeElement ? document.activeElement.tagName : '';
                const inField = ['INPUT', 'TEXTAREA', 'SELECT'].includes(tag) &&
                                document.activeElement !== qtInput;
                if (!inField) { e.preventDefault(); isOpen ? qtClose() : qtOpen(); }
            }
        });

        qtCloseBtn.addEventListener('click', qtClose);

        // ── command history (up/down) + tab autocomplete ──────────────────────
        const cmdHistory = [];
        let histIdx = -1;       // -1 = not browsing history
        let histDraft = '';     // saves the in-progress line when user starts browsing

        const COMPLETIONS = [
            'help', 'list', 'list-custom', 'clear',
            'run ', 'run-custom ', 'curl ', 'save ',
            'delete-custom ', 'ask ', 'chat', 'search ',
        ];

        qtInput.addEventListener('keydown', e => {
            if (e.key === 'Enter') {
                const val = qtInput.value.trim();
                qtInput.value = '';
                histIdx = -1;
                histDraft = '';
                if (chatMode) {
                    if (!val) return;
                    if (val === 'exit' || val === '/exit') { qtExitChat(); return; }
                    if (val === '/clear' || val === 'clear') {
                        chatHistory = [];
                        qtWrite('Conversation history cleared.', 'qt-muted');
                        return;
                    }
                    qtWrite('\u{1F916} ' + val, 'qt-cmd');
                    qtChatSend(val);
                    return;
                }
                if (val) {
                    // push to front, avoid consecutive duplicates, cap at 100
                    if (cmdHistory[0] !== val) cmdHistory.unshift(val);
                    if (cmdHistory.length > 100) cmdHistory.pop();
                }
                handleCommand(val);
                return;
            }

            if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (!cmdHistory.length) return;
                if (histIdx === -1) histDraft = qtInput.value; // save draft
                histIdx = Math.min(histIdx + 1, cmdHistory.length - 1);
                qtInput.value = cmdHistory[histIdx];
                // move caret to end
                setTimeout(() => qtInput.setSelectionRange(qtInput.value.length, qtInput.value.length));
                return;
            }

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (histIdx === -1) return;
                histIdx--;
                qtInput.value = histIdx === -1 ? histDraft : cmdHistory[histIdx];
                setTimeout(() => qtInput.setSelectionRange(qtInput.value.length, qtInput.value.length));
                return;
            }

            if (e.key === 'Tab') {
                e.preventDefault();
                const cur = qtInput.value;
                // build candidate list: static completions + dynamic names + search completions
                const appNames   = (appsCache || []).map(a => 'run ' + a.title);
                const customNames = (customCmdsCache || []).flatMap(c => ['run-custom ' + c.name, 'delete-custom ' + c.name]);
                let candidates = [...COMPLETIONS, ...appNames, ...customNames];
                // Add search <tile> completions
                if (cur.startsWith('search ')) {
                    const q = cur.slice(7).toLowerCase();
                    const searchNames = (appsCache || []).map(a => 'search ' + a.title);
                    candidates = candidates.concat(searchNames);
                }
                // Allow partial matching for the first word (e.g., 'se' → 'search')
                let matches = candidates.filter(c => c.startsWith(cur));
                if (matches.length === 0 && cur) {
                    // Try to match partials for the first word only
                    const firstWord = cur.split(' ')[0];
                    const afterSpace = cur.indexOf(' ') !== -1 ? cur.slice(cur.indexOf(' ')) : '';
                    const partialMatches = candidates.filter(c => c.startsWith(firstWord));
                    if (partialMatches.length > 0) {
                        // If only one match, autocomplete it
                        if (partialMatches.length === 1) {
                            qtInput.value = partialMatches[0] + afterSpace;
                            return;
                        } else {
                            // If multiple, show options and fill common prefix
                            let commonPrefix = partialMatches[0];
                            for (const m of partialMatches) {
                                let i = 0;
                                while (i < commonPrefix.length && i < m.length && commonPrefix[i] === m[i]) i++;
                                commonPrefix = commonPrefix.slice(0, i);
                            }
                            qtWrite(partialMatches.map(m => m.slice(commonPrefix.length)).join('   '), 'qt-muted');
                            if (commonPrefix.length > cur.length) qtInput.value = commonPrefix;
                            return;
                        }
                    }
                }
                if (matches.length === 1) {
                    qtInput.value = matches[0];
                } else if (matches.length > 1) {
                    // hide bare prefix entries subsumed by longer matches
                    const displayMatches = matches.filter(m => !matches.some(other => other !== m && other.startsWith(m)));
                    const shown = displayMatches.length ? displayMatches : matches;
                    // compute common prefix of all shown matches
                    let commonPrefix = shown[0];
                    for (const m of shown) {
                        let i = 0;
                        while (i < commonPrefix.length && i < m.length && commonPrefix[i] === m[i]) i++;
                        commonPrefix = commonPrefix.slice(0, i);
                    }
                    // if common prefix ends with a space, strip it so only the argument names are shown
                    const label = commonPrefix.endsWith(' ')
                        ? shown.map(m => m.slice(commonPrefix.length))
                        : shown;
                    qtWrite(label.join('   '), 'qt-muted');
                    // fill the longest common prefix
                    let prefix = matches[0];
                    for (const m of matches) {
                        let i = 0;
                        while (i < prefix.length && i < m.length && prefix[i] === m[i]) i++;
                        prefix = prefix.slice(0, i);
                    }
                    if (prefix.length > cur.length) qtInput.value = prefix;
                }
                return;
            }
        });
    }
});
