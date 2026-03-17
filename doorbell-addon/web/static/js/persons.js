/**
 * persons.js — Loaded globally for nav badge polling.
 * Also contains all Persons page tab/action logic (runs only when #persons-tabs exists).
 */

// ── Nav badge polling ────────────────────────────────────────────────────────

(function () {
    var badgeEl = null;
    var frEnabled = null; // null = unchecked, true/false = result

    function updateBadge() {
        if (frEnabled === false) return;
        fetch('api/face-crops?count_only=true')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                badgeEl = badgeEl || document.getElementById('unrecognised-count');
                if (!badgeEl) return;
                var n = data.count || 0;
                if (n > 0) {
                    badgeEl.textContent = n;
                    badgeEl.style.display = 'inline-block';
                } else {
                    badgeEl.style.display = 'none';
                }
            })
            .catch(function () {});
    }

    function checkStatusThenPoll() {
        fetch('api/face-recognition/status')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                frEnabled = !!data.enabled;
                if (frEnabled) {
                    updateBadge();
                    setInterval(updateBadge, 30000);
                }
            })
            .catch(function () {});
    }

    document.addEventListener('DOMContentLoaded', checkStatusThenPoll);
})();

// ── Persons page logic ───────────────────────────────────────────────────────
// Only runs when the two-tab layout is present on /persons.

document.addEventListener('DOMContentLoaded', function () {
    if (!document.getElementById('persons-tabs')) return;

    // ── Tab switching ──────────────────────────────────────────────────────
    var tabs = document.querySelectorAll('[data-tab]');
    var panes = document.querySelectorAll('[data-pane]');

    function showTab(name) {
        tabs.forEach(function (t) {
            var active = t.dataset.tab === name;
            t.style.color = active ? 'var(--primary, #38bdf8)' : '#888';
            t.style.borderBottom = active ? '2px solid var(--primary, #38bdf8)' : '2px solid transparent';
        });
        panes.forEach(function (p) {
            p.style.display = p.dataset.pane === name ? '' : 'none';
        });
        if (name === 'unrecognised') loadCrops();
    }

    tabs.forEach(function (t) {
        t.addEventListener('click', function () { showTab(t.dataset.tab); });
    });
    showTab('known');

    // ── Inline rename ──────────────────────────────────────────────────────
    document.addEventListener('click', function (e) {
        if (!e.target.classList.contains('rename-btn')) return;
        var pid = e.target.dataset.personId;
        var nameEl = document.getElementById('person-name-' + pid);
        var input = document.createElement('input');
        input.value = nameEl.textContent.trim();
        input.style.cssText = 'font-size:13px;font-weight:600;border:1px solid #38bdf8;' +
            'background:#111;color:#e5e7eb;border-radius:4px;padding:1px 4px;width:100px';
        nameEl.replaceWith(input);
        input.focus();
        function save() {
            var newName = input.value.trim();
            if (!newName) { input.replaceWith(nameEl); return; }
            fetch('api/persons/' + pid, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: newName }),
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    nameEl.textContent = data.name;
                    input.replaceWith(nameEl);
                })
                .catch(function () { input.replaceWith(nameEl); });
        }
        input.addEventListener('blur', save);
        input.addEventListener('keydown', function (ev) {
            if (ev.key === 'Enter') save();
            if (ev.key === 'Escape') input.replaceWith(nameEl);
        });
    });

    // ── Delete person ──────────────────────────────────────────────────────
    window.deletePerson = function (personId, name) {
        if (!confirm('Remove ' + name + ' from known persons?')) return;
        fetch('api/persons/' + personId, { method: 'DELETE' })
            .then(function (r) {
                if (r.ok) {
                    var card = document.getElementById('person-card-' + personId);
                    if (card) card.closest('.col-sm-6, .col-md-4, [id^=person-card-]')
                        ? card.closest('[id^=person-card-]').parentElement.remove()
                        : card.remove();
                    location.reload();
                } else {
                    r.json().then(function (d) { alert('Error: ' + (d.detail || 'Unknown')); });
                }
            });
    };

    // ── Delete sample ──────────────────────────────────────────────────────
    window.deleteSample = function (personId, embId) {
        if (!confirm('Remove this sample?')) return;
        fetch('api/persons/' + personId + '/samples/' + embId, { method: 'DELETE' })
            .then(function (r) {
                if (r.ok) location.reload();
                else r.json().then(function (d) { alert('Error: ' + (d.detail || 'Unknown')); });
            });
    };

    // ── Add sample ─────────────────────────────────────────────────────────
    window.addSample = function (personId) {
        var input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.addEventListener('change', function () {
            if (!input.files[0]) return;
            var fd = new FormData();
            fd.append('image', input.files[0]);
            fetch('api/persons/' + personId + '/samples', { method: 'POST', body: fd })
                .then(function (r) {
                    if (r.ok) location.reload();
                    else r.json().then(function (d) {
                        alert('Error: ' + (d.detail || 'Unknown'));
                    });
                });
        });
        input.click();
    };

    // ── Add new person ─────────────────────────────────────────────────────
    window.addPerson = function () {
        var name = (document.getElementById('new-person-name') || {}).value || '';
        var photo = (document.getElementById('new-person-photo') || {}).files;
        var status = document.getElementById('add-person-status');
        name = name.trim();
        if (!name) { if (status) status.innerHTML = '<span style="color:var(--red)">Enter a name.</span>'; return; }
        if (!photo || !photo[0]) { if (status) status.innerHTML = '<span style="color:var(--red)">Select a photo.</span>'; return; }
        var fd = new FormData();
        fd.append('name', name);
        fd.append('image', photo[0]);
        fetch('api/persons', { method: 'POST', body: fd })
            .then(function (r) {
                if (r.ok) location.reload();
                else r.json().then(function (d) {
                    if (status) status.innerHTML = '<span style="color:var(--red)">Error: ' + (d.detail || 'Unknown') + '</span>';
                });
            });
    };

    // ── Unrecognised crops tab ─────────────────────────────────────────────
    var selectedCropId = null;

    function loadCrops() {
        fetch('api/face-crops?dismissed=false')
            .then(function (r) { return r.json(); })
            .then(function (data) { renderCrops(data.crops || []); })
            .catch(function () {});
    }

    function renderCrops(crops) {
        var grid = document.getElementById('crops-grid');
        var panel = document.getElementById('crop-action-panel');
        if (!grid) return;
        grid.innerHTML = '';
        if (crops.length === 0) {
            grid.innerHTML = '<p style="color:#666;font-size:13px;grid-column:1/-1">No unrecognised faces — great!</p>';
            if (panel) panel.style.display = 'none';
            return;
        }
        crops.forEach(function (crop) {
            var div = document.createElement('div');
            div.style.cssText = 'background:#1c1c1f;border-radius:8px;border:1px solid #333;overflow:hidden;cursor:pointer';
            div.id = 'crop-' + crop.id;
            var ts = (crop.event_timestamp || crop.created_at || '').slice(0, 16).replace('T', ' ');
            div.innerHTML =
                '<img src="' + crop.image_path + '" style="width:100%;height:80px;object-fit:cover" ' +
                'onerror="this.style.background=\'#333\';this.style.height=\'80px\'">' +
                '<div style="padding:4px 6px;font-size:10px;color:#888">' + ts + '</div>';
            div.addEventListener('click', function () { selectCrop(crop.id); });
            grid.appendChild(div);
        });
    }

    function selectCrop(cropId) {
        // Highlight selected
        document.querySelectorAll('[id^=crop-]').forEach(function (el) {
            el.style.border = '1px solid #333';
        });
        var el = document.getElementById('crop-' + cropId);
        if (el) el.style.border = '2px solid #38bdf8';
        selectedCropId = cropId;
        var panel = document.getElementById('crop-action-panel');
        if (panel) panel.style.display = '';
    }

    window.assignCropToPerson = function (personId) {
        if (!selectedCropId) return;
        fetch('api/face-crops/' + selectedCropId + '/assign', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ person_id: personId }),
        })
            .then(function (r) {
                if (r.ok) location.reload();
                else r.json().then(function (d) { alert('Error: ' + (d.detail || 'Unknown')); });
            });
    };

    window.assignCropNewPerson = function () {
        var name = (document.getElementById('new-crop-name') || {}).value || '';
        name = name.trim();
        if (!name || !selectedCropId) return;
        fetch('api/face-crops/' + selectedCropId + '/assign', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name }),
        })
            .then(function (r) {
                if (r.ok) location.reload();
                else r.json().then(function (d) { alert('Error: ' + (d.detail || 'Unknown')); });
            });
    };

    window.dismissCrop = function () {
        if (!selectedCropId) return;
        fetch('api/face-crops/' + selectedCropId + '/dismiss', { method: 'POST' })
            .then(function (r) {
                if (r.ok) location.reload();
            });
    };
});
