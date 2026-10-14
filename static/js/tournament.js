/* ==============================================================
   Tournament page: plays and edits one bracket.
   Needs TOURNAMENT (the server's view), ALL_SETS and API from the page,
   and tools.js (FIGHTER_BY_ID, matchup, escapeHtml, $, $$, storeGet/Set).
   Every change is sent to the server as one "op"; the server checks it,
   saves a new version and sends the whole tournament back.
================================================================*/

const PLAYER_COLORS = ['#3b82f6', '#f97316', '#22c55e', '#a855f7', '#ec4899', '#14b8a6'];
const EDIT_KEY = 'ufc_tournament_edit';
let pendingSwap = null;   // {mid, side} picked first when swapping two slots
let modalOpen = false;
let busy = false;
let adjustments = null;   // the score adjustments, once "Show adjustments" is pressed (they aren't sent with the page)
const folded = new Map();  // round id → folded? Rounds already finished when first shown start folded

const byMatch = () => Object.fromEntries(TOURNAMENT.matches.map(m => [m.id, m]));
const fighterName = id => (FIGHTER_BY_ID[id] ? FIGHTER_BY_ID[id].name : id);
const playerOf = pid => TOURNAMENT.players.find(p => p.id === pid);
const playerColor = pid => PLAYER_COLORS[Math.max(0, TOURNAMENT.players.findIndex(p => p.id === pid)) % PLAYER_COLORS.length];
const editing = () => $('#edit-mode').checked;
// Finished: has a winner and, when there are players, who played it (so the "Who played?" step stays in view)
const finished = m => m.winner && (m.player || !TOURNAMENT.players.length) && !m.ask_loser;

/*************************** TALKING TO THE SERVER ***************************/
async function op(name, args = {}) {
    if (busy) return null;
    busy = true;
    setStatus('Saving…');
    try {
        const r = await fetch(`${API}/op`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ op: name, args, version: TOURNAMENT.version }),
        });
        const data = await r.json().catch(() => ({}));
        if (data.tournament) TOURNAMENT = data.tournament;
        if (!r.ok) {
            setStatus('');
            alert(data.error || `Couldn't save (error ${r.status}).`);
        } else {
            setStatus(`Saved: ${named(data.summary)}`);
        }
        render();
        return r.ok ? data : null;
    } catch (e) {
        setStatus("Couldn't reach the server; nothing was saved.");
        return null;
    } finally {
        busy = false;
    }
}

async function poll() {
    if (busy || modalOpen || drag || document.hidden) return;
    try {
        const r = await fetch(`${API}?since=${TOURNAMENT.version}`);
        if (r.status === 200) {
            TOURNAMENT = await r.json();
            setStatus('Updated from another device.');
            render();
        } else if (r.status === 401) {
            setStatus('Logged out. Reload the page to log in again.');
        }
    } catch (e) { /* offline: try again next time */ }
}

function setStatus(text) { $('#sync-status').textContent = text; }

/** Server summaries name fighters and players by id; this swaps in their names (tokens: letters, digits, _). */
function named(text) {
    const players = Object.fromEntries(TOURNAMENT.players.map(p => [p.id, p.name]));
    return text.replace(/[A-Za-z][A-Za-z0-9_]*/g, w => (FIGHTER_BY_ID[w] ? FIGHTER_BY_ID[w].name : players[w] || w));
}

/*************************** SMALL PIECES ***************************/
function fighterHTML(id, cls = '') {
    const f = FIGHTER_BY_ID[id];
    if (!f) return `<span class="t-fighter ${cls}">${escapeHtml(id)}</span>`;
    return `<span class="t-fighter ${cls}"><img src="${f.image_url}" alt="" loading="lazy">${escapeHtml(f.name)}</span>`;
}

const fmtScore = (v, mode) => (mode === 'weighted' ? v.toFixed(2) : (Number.isInteger(v) ? String(v) : v.toFixed(2)));
const statusLabel = { played: 'Played', ready: 'Ready', waiting: 'Waiting' };

/** One fighter row of a match card: portrait, name, their win chance, edit tools. */
function slotRowHTML(m, side, edit) {
    const slot = m[side];
    const fighter = side === 'top' ? m.top_fighter : m.bot_fighter;
    const unplayed = !m.winner;
    const grip = (edit && unplayed && slot)
        ? `<span class="t-grip" data-drag="slot" data-mid="${m.id}" data-side="${side}" title="Drag onto another slot to swap, or onto the bench">⠿</span>` : '';
    const tools = (edit && unplayed) ? `<span class="t-slot-tools">
        <button type="button" data-act="change" data-mid="${m.id}" data-side="${side}" title="Put someone else in this slot">change</button>
        <button type="button" data-act="swap" data-mid="${m.id}" data-side="${side}" class="${pendingSwap && pendingSwap.mid === m.id && pendingSwap.side === side ? 'on' : ''}" title="Swap this slot with another">⇄</button>
        ${slot ? `<button type="button" data-act="playin" data-mid="${m.id}" data-side="${side}" title="Make whoever is here win a play-in match first">+ play-in</button>` : ''}
        </span>` : '';
    let body;
    let state = '';
    const pick = side === 'top' ? m.top_player : m.bot_player;
    if (fighter) {
        const f = FIGHTER_BY_ID[fighter];
        state = m.winner ? (m.winner === fighter ? 'won' : 'lost') : '';
        const pct = m.win_pct == null ? null : (side === 'top' ? m.win_pct : 100 - m.win_pct);
        const low = m.games < FULL_CONFIDENCE_GAMES;
        body = `<span class="t-ava">${f ? `<img src="${f.image_url}" alt="" loading="lazy">` : ''}</span>
            <span class="t-name">${escapeHtml(f ? f.name : fighter)}${state === 'won' ? ' <span class="t-crown" title="Winner">♛</span>' : ''}${pick && !m.winner
                ? `<span class="t-player-tag t-pick-tag" style="--pc:${playerColor(pick)}" title="Picked to play this fighter">🎮 ${escapeHtml(playerOf(pick) ? playerOf(pick).name : pick)}</span>` : ''}</span>
            ${pct != null && !m.winner ? `<span class="t-pct" title="Chance to win${low ? ' (estimate: few games)' : ''}">${low ? '~' : ''}${Math.round(pct)}%</span>` : ''}`;
    } else if (!slot) {
        body = '<span class="t-ava t-ava-empty">+</span><span class="t-name t-tbd">Empty slot</span>';
    } else {
        const src = byMatch()[slot.from];
        body = `<span class="t-ava t-ava-empty">?</span><span class="t-name t-tbd">Winner of ${escapeHtml(src ? src.label : '?')}</span>`;
    }
    return `<div class="t-slot ${state}" data-mid="${m.id}" data-side="${side}" ${unplayed ? 'data-open="1"' : ''}>${grip}${body}${tools}</div>`;
}

function winBarHTML(m) {
    if (m.win_pct == null || m.winner) return '';
    const d = Math.abs(m.win_pct - 50);
    const fair = d <= 2 ? 'Even' : d <= 5 ? 'Close' : d <= 10 ? 'Leaning' : 'Lopsided';
    return `<div class="t-bar ${fair.toLowerCase()}" title="${fair} matchup"><span style="width:${m.win_pct}%"></span></div>
        <div class="t-bar-text"><span>${fair}</span><span class="games-note${m.games < FULL_CONFIDENCE_GAMES ? ' low-data' : ''}">${m.games ? m.games.toLocaleString('en-US') + ' games' : 'estimate'}</span></div>`;
}

/** Buttons to say who played the winner (role "winner") or the loser (role "loser": not the winner's player). */
function playerButtons(m, role = 'winner') {
    return TOURNAMENT.players.filter(p => role === 'winner' || p.id !== m.player).map(p => `<button type="button"
        class="t-player-btn" style="--pc:${playerColor(p.id)}" data-act="player" data-role="${role}" data-mid="${m.id}"
        data-player="${p.id}">${escapeHtml(p.name)}</button>`).join('');
}

const playerTag = pid => `<span class="t-player-tag" style="--pc:${playerColor(pid)}">🎮 ${escapeHtml(playerOf(pid) ? playerOf(pid).name : pid)}</span>`;

/*************************** RENDERING ***************************/
function renderHero() {
    const mode = TOURNAMENT.scoring;
    $('#hero-title').textContent = TOURNAMENT.name;
    document.title = `${TOURNAMENT.name} – Tournament`;
    const played = TOURNAMENT.matches.filter(m => m.winner).length;
    const total = TOURNAMENT.matches.length;
    const cur = TOURNAMENT.rounds.find(r => r.id === TOURNAMENT.current_round);
    $('#hero-meta').textContent = `${TOURNAMENT.players.map(p => p.name).join(' vs ')} · ${played} of ${total} matches played` +
        (cur ? ` · now: ${cur.name}` : '');
    $('#hero-progress').style.width = `${total ? (100 * played / total) : 0}%`;

    const vals = TOURNAMENT.players.map(p => TOURNAMENT.scores[p.id][mode]);
    const best = Math.max(...vals);
    const leader = vals.filter(v => v === best).length === 1 ? best : null;
    $('#scoreboard').innerHTML = TOURNAMENT.players.map((p, i) => {
        return `<div class="t-score ${vals[i] === leader ? 'lead' : ''}" style="--pc:${playerColor(p.id)}">
            <span class="t-score-name">${escapeHtml(p.name)}${vals[i] === leader ? ' <span class="t-score-crown">👑</span>' : ''}</span>
            <b>${fmtScore(vals[i], mode)}</b>
            <span class="t-score-sub">${mode === 'weighted' ? 'weighted points' : 'wins'}</span>
        </div>`;
    }).join('') +
        (TOURNAMENT.champion ? `<div class="t-champion">🏆 Champion: ${fighterHTML(TOURNAMENT.champion)}</div>` : '');
    $$('.t-segment [data-scoring]').forEach(b => b.classList.toggle('on', b.dataset.scoring === mode));
}

function renderRoundNav() {
    $('#round-nav').innerHTML = TOURNAMENT.rounds.map(r => {
        const ms = TOURNAMENT.matches.filter(m => m.round === r.id);
        const done = ms.length && ms.every(finished);
        const now = TOURNAMENT.current_round === r.id;
        const state = done ? 'done' : now ? 'now' : 'later';
        return `<a href="#round-${r.id}" class="t-pill ${state}" data-round-link="${r.id}">
            <span class="t-pill-dot">${done ? '✓' : ''}</span>${escapeHtml(r.name)}
            <span class="t-pill-count">${ms.filter(m => m.winner).length}/${ms.length}</span></a>`;
    }).join('');
}

function matchCardHTML(m) {
    const ms = byMatch();
    const edit = editing();
    const unplayed = !m.winner;
    let action = '';
    if (m.status === 'ready') {
        action = `<p class="t-ask">Who won?</p><div class="t-win-btns">
            <button type="button" data-act="win" data-mid="${m.id}" data-side="top">${escapeHtml(fighterName(m.top_fighter))}</button>
            <button type="button" data-act="win" data-mid="${m.id}" data-side="bot">${escapeHtml(fighterName(m.bot_fighter))}</button></div>
            <button type="button" class="t-link t-pick-link" data-act="picks" data-mid="${m.id}">${m.top_player || m.bot_player ? '🎮 Change who plays' : '🎮 Pick who plays (optional)'}</button>`;
    } else if (m.winner && !m.player) {
        action = `<p class="t-ask">♛ ${escapeHtml(fighterName(m.winner))} won. Who played them?</p><div class="t-player-btns">${playerButtons(m)}</div>
            <button type="button" class="t-link" data-act="undo" data-mid="${m.id}">↩ undo result</button>`;
    } else if (m.ask_loser) {
        const loser = m.winner === m.top_fighter ? m.bot_fighter : m.top_fighter;
        action = `<div class="t-result">${playerTag(m.player)}</div>
            <p class="t-ask">And who played ${escapeHtml(fighterName(loser))}?</p><div class="t-player-btns">${playerButtons(m, 'loser')}</div>
            <div class="t-result"><button type="button" class="t-link" data-act="player" data-role="loser" data-mid="${m.id}" data-player="">skip, don't know</button>
            <button type="button" class="t-link" data-act="undo" data-mid="${m.id}">↩ undo result</button></div>`;
    } else if (m.winner) {
        // With two players the loser's player is obvious; with more, say who they beat
        const beat = TOURNAMENT.players.length > 2 && m.loser_player ? ` <span class="t-beat">beat</span> ${playerTag(m.loser_player)}` : '';
        action = `<div class="t-result"><span>${playerTag(m.player)}${beat}</span>
            <button type="button" class="t-link" data-act="undo" data-mid="${m.id}" title="Undo this result">↩ undo</button></div>`;
    }
    const next = m.next ? ms[m.next] : null;
    const goesTo = next ? `<div class="t-next">Winner → ${escapeHtml(next.label)}</div>`
        : (TOURNAMENT.open_winners.includes(m.id) ? '<div class="t-next warn">Winner doesn\'t go anywhere yet</div>' : '');
    const cardTools = edit ? `<span class="t-card-tools">
        <span class="t-grip t-drag-handle" data-drag="match" data-mid="${m.id}" title="Drag onto another round, or just before another match">⠿</span>
        <button type="button" data-act="move-round" data-mid="${m.id}" title="Move to another round">⤵</button>
        <button type="button" data-act="rename-match" data-mid="${m.id}" title="Rename">✎</button>
        <button type="button" data-act="move" data-mid="${m.id}" data-dir="up" title="Move up">↑</button>
        <button type="button" data-act="move" data-mid="${m.id}" data-dir="down" title="Move down">↓</button>
        ${unplayed ? `<button type="button" data-act="delete-match" data-mid="${m.id}" title="Delete this match">🗑</button>` : ''}</span>` : '';
    const needsPlayer = m.winner && (!m.player || m.ask_loser);
    const cls = ['t-card', m.status, needsPlayer ? 'needs-player' : ''].join(' ');
    return `<div class="${cls}" id="card-${m.id}" data-mid="${m.id}">
        <div class="t-card-head"><span class="t-label">${escapeHtml(m.label)}</span>
            <span class="t-status ${needsPlayer ? 'ask' : m.status}">${needsPlayer ? 'Who played?' : statusLabel[m.status]}</span>${cardTools}</div>
        ${slotRowHTML(m, 'top', edit)}
        <div class="t-vs"><span>${m.winner ? 'def.' : 'vs'}</span></div>
        ${slotRowHTML(m, 'bot', edit)}
        ${winBarHTML(m)}${action}${goesTo}</div>`;
}

function renderRounds() {
    const edit = editing();
    $('#rounds').innerHTML = TOURNAMENT.rounds.map(r => {
        const ms = TOURNAMENT.matches.filter(m => m.round === r.id);
        const played = ms.filter(m => m.winner).length;
        const tools = edit ? `<span class="t-round-tools">
            <button type="button" class="t-tool-sm" data-act="add-match" data-round="${r.id}">+ match</button>
            <button type="button" class="t-tool-sm" data-act="rebalance" data-round="${r.id}">⇄ rebalance</button>
            <button type="button" class="t-tool-sm" data-act="rename-round" data-round="${r.id}">✎ rename</button>
            <button type="button" class="t-tool-sm" data-act="add-round" data-round="${r.id}">+ round before</button>
            ${ms.length ? '' : `<button type="button" class="t-tool-sm" data-act="delete-round" data-round="${r.id}">🗑 delete</button>`}</span>` : '';
        const now = TOURNAMENT.current_round === r.id;
        // Finished rounds fold away (except while editing) so the current round is near the top. A round that
        // finishes while it's on screen stays open until the page is reloaded.
        const done = ms.length && ms.every(finished);
        if (!folded.has(r.id)) folded.set(r.id, !!done);
        const fold = done && !edit && folded.get(r.id);
        const toggle = done && !edit ? `<button type="button" class="t-tool-sm" data-act="toggle-round" data-round="${r.id}">${fold ? `Show ${ms.length} results ▾` : 'Hide ▴'}</button>` : '';
        return `<section class="t-round${fold ? ' collapsed' : ''}${now ? ' now' : ''}${done ? ' done' : ''}" data-round="${r.id}" id="round-${r.id}">
            <div class="t-round-head"><h2>${escapeHtml(r.name)}</h2>
                ${now ? '<span class="t-chip now">● Now playing</span>' : done ? '<span class="t-chip done">✓ Done</span>' : ''}
                <span class="t-round-count">${played} / ${ms.length} played</span>${toggle}<span class="spacer"></span>${tools}</div>
            <div class="t-grid">${ms.map(matchCardHTML).join('') || '<p class="muted">No matches in this round yet. Drag a bench fighter here, or use + match.</p>'}</div></section>`;
    }).join('');
}

function renderAdjustments() {
    $('#adj-player').innerHTML = TOURNAMENT.players.map(p => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join('');
    const where = { weighted: 'weighted', standard: 'standard', both: 'both scorings' };
    $('#show-adjustments').textContent = adjustments ? 'Hide adjustments' : 'Show adjustments';
    if (!adjustments) { $('#adjustments').innerHTML = ''; return; }
    $('#adjustments').innerHTML = adjustments.length ? `<ul class="t-adj-list">${adjustments.map(a => {
        const p = playerOf(a.player);
        return `<li><span class="t-player-tag" style="--pc:${playerColor(a.player)}">${escapeHtml(p ? p.name : a.player)}</span>
            <strong>${a.points > 0 ? '+' : ''}${a.points}</strong> <span class="muted">${where[a.scoring]}${a.note ? ' · ' + escapeHtml(a.note) : ''}</span>
            <button type="button" class="t-link" data-act="remove-adjustment" data-adj="${a.id}" title="Remove">✕</button></li>`;
    }).join('')}</ul>` : '<p class="muted">No adjustments.</p>';
}

async function loadAdjustments() {
    const r = await fetch(`${API}/adjustments`).catch(() => null);
    adjustments = r && r.ok ? await r.json() : null;
    if (!adjustments) setStatus("Couldn't load the adjustments.");
    renderAdjustments();
}

function renderEditPanel() {
    $('#edit-panel').hidden = !editing();
    document.body.classList.toggle('t-editing', editing());
    if (!editing()) return;
    renderAdjustments();
    if (document.activeElement !== $('#edit-name')) $('#edit-name').value = TOURNAMENT.name;
    if (!$('#edit-players').contains(document.activeElement)) {
        $('#edit-players').innerHTML = TOURNAMENT.players.map(p =>
            `<input type="text" class="edit-player" value="${escapeHtml(p.name)}" placeholder="${p.id}" style="width:8rem">`).join('');
    }
    $('#bench').innerHTML = TOURNAMENT.bench.length
        ? TOURNAMENT.bench.map(f => `<span class="t-bench-chip" data-drag="bench" data-fighter="${f}" title="Drag onto a slot, or onto a round to start a new match">${fighterHTML(f)}<button type="button" data-act="unbench" data-fighter="${f}" title="Remove from the tournament">×</button></span>`).join('')
        : '<span class="muted">Nobody on the bench.</span>';
    $('#slot-in-box').hidden = !TOURNAMENT.bench.length && !TOURNAMENT.open_winners.length;
    $('#pair-box').hidden = TOURNAMENT.bench.length < 2;
    const keepPair = $('#pair-round').value;
    const playable = TOURNAMENT.rounds.filter(r => TOURNAMENT.matches.some(m => m.round === r.id && !m.winner));
    $('#pair-round').innerHTML =
        playable.map(r => `<option value="new:${r.id}">a new "Qualifier" round before ${escapeHtml(r.name)}</option>`).join('') +
        TOURNAMENT.rounds.map(r => `<option value="${r.id}">${escapeHtml(r.name)}</option>`).join('');
    if (keepPair && [...$('#pair-round').options].some(o => o.value === keepPair)) {
        $('#pair-round').value = keepPair;
    } else {
        // Default: before the round after the current one, when the current round is mostly played
        const cur = TOURNAMENT.current_round;
        const idx = TOURNAMENT.rounds.findIndex(r => r.id === cur);
        const ms = TOURNAMENT.matches.filter(m => m.round === cur);
        const mostlyPlayed = ms.length && ms.filter(m => m.winner).length * 2 >= ms.length;
        const target = mostlyPlayed && TOURNAMENT.rounds[idx + 1] ? TOURNAMENT.rounds[idx + 1].id : cur;
        if (target) $('#pair-round').value = `new:${target}`;
    }
    const keep = $('#slot-in-round').value;
    const open = TOURNAMENT.rounds.filter(r => TOURNAMENT.matches.some(m => m.round === r.id && !m.winner));
    // Rounds with matches still to play; keeps the round picked last time
    $('#slot-in-round').innerHTML = open.map(r => `<option value="${r.id}">${escapeHtml(r.name)}</option>`).join('');
    if (keep && open.some(r => r.id === keep)) $('#slot-in-round').value = keep;
    $('#edit-notes').innerHTML = TOURNAMENT.notes.length
        ? `<ul class="t-notes">${TOURNAMENT.notes.map(n => `<li>${escapeHtml(n)}</li>`).join('')}</ul>` : '';
}

function render() {
    renderHero();
    renderRoundNav();
    renderEditPanel();
    renderRounds();
}

/*************************** PICKERS (modal) ***************************/
function openModal(html) {
    $('#t-modal-body').innerHTML = html;
    $('#t-modal').classList.remove('hidden');
    modalOpen = true;
}

function closeModal() {
    $('#t-modal').classList.add('hidden');
    modalOpen = false;
    render();
}

/** Options for a slot: benched fighters and winners not sent anywhere yet, closest to 50/50 vs `against` first. */
function slotOptions(forMatch, against) {
    const ms = byMatch();
    const roundOrder = Object.fromEntries(TOURNAMENT.rounds.map((r, i) => [r.id, i]));
    const pct = f => (against && f && matchup(f, against)) ? matchup(f, against)[0] : null;
    const opt = (slot, label, f) => {
        const p = pct(f);
        return { slot, html: label + (p != null ? ` <span class="muted">· ${p}% vs ${escapeHtml(fighterName(against))}</span>` : ''), gap: p == null ? 99 : Math.abs(p - 50) };
    };
    const bench = TOURNAMENT.bench.map(f => opt({ fighter: f }, fighterHTML(f), f));
    const winners = TOURNAMENT.open_winners
        .filter(mid => mid !== forMatch.id && roundOrder[ms[mid].round] < roundOrder[forMatch.round])
        .map(mid => {
            const w = ms[mid].winner;
            return opt({ from: mid }, w ? `${fighterHTML(w)} <span class="muted">(won ${escapeHtml(ms[mid].label)})</span>`
                : `<span class="t-tbd">Winner of ${escapeHtml(ms[mid].label)}</span>`, w);
        });
    return { bench: bench.sort((a, b) => a.gap - b.gap), winners: winners.sort((a, b) => a.gap - b.gap) };
}

function pickerHTML(title, intro, groups, allowEmpty) {
    const list = (name, items) => items.length ? `<h3>${name}</h3><div class="t-options">${items.map((o, i) =>
        `<button type="button" class="t-option" data-pick='${escapeHtml(JSON.stringify(o.slot))}'>${o.html}</button>`).join('')}</div>` : '';
    const body = list('On the bench', groups.bench) + list('Winners not sent anywhere yet', groups.winners);
    return `<h2>${title}</h2><p class="muted">${intro}</p>` +
        (body || '<p>Nobody available. Add fighters to the bench first (Edit → + Add fighters).</p>') +
        (allowEmpty ? `<h3>Or</h3><div class="t-options"><button type="button" class="t-option" data-pick="null">Leave the slot empty</button></div>` : '');
}

function openSlotPicker(mid, side) {
    const m = byMatch()[mid];
    const other = side === 'top' ? m.bot_fighter : m.top_fighter;
    const current = side === 'top' ? m.top_fighter : m.bot_fighter;
    openModal(pickerHTML(`Change a slot in ${escapeHtml(m.label)}`,
        `Who should be here instead${current ? ` of ${escapeHtml(fighterName(current))} (they go back to the bench)` : ''}?` +
        (other ? ` Win chances are against ${escapeHtml(fighterName(other))}.` : ''),
        slotOptions(m, other), true));
    bindPicks(slot => op('set_slot', { mid, side, slot }));
}

function openPlayInPicker(mid, side) {
    const m = byMatch()[mid];
    const holder = side === 'top' ? m.top_fighter : m.bot_fighter;
    const who = holder ? escapeHtml(fighterName(holder)) : 'whoever wins the earlier match';
    openModal(pickerHTML(`Play-in for a slot in ${escapeHtml(m.label)}`,
        `${who} will have to beat this challenger first; the winner takes the slot. ` +
        `The play-in goes in a "Play-in" round just before ${escapeHtml(TOURNAMENT.rounds.find(r => r.id === m.round).name)}.` +
        (holder ? ` Win chances are against ${who}.` : ''),
        slotOptions(m, holder), false));
    bindPicks(slot => op('insert_play_in', { mid, side, challenger: slot }));
}

function bindPicks(onPick) {
    $$('#t-modal-body [data-pick]').forEach(btn => btn.addEventListener('click', async () => {
        const slot = JSON.parse(btn.dataset.pick);
        const ok = await onPick(slot);
        if (ok) closeModal();
    }));
}

/** Pick the two fighters of a new match yourself: bench fighters or winners that don't go anywhere yet. */
function openMatchBuilder(roundId) {
    const roundName = TOURNAMENT.rounds.find(r => r.id === roundId).name;
    const picked = [];  // slots, in the order tapped
    const fighterOf = slot => slot.fighter || (byMatch()[slot.from] || {}).winner || null;
    const draw = () => {
        const against = picked.length ? fighterOf(picked[0]) : null;
        const opts = slotOptions({ id: null, round: roundId }, against);
        const key = slot => JSON.stringify(slot);
        const chosen = new Set(picked.map(key));
        const list = (name, items) => items.length ? `<h3>${name}</h3><div class="t-options">${items.map(o =>
            `<button type="button" class="t-option${chosen.has(key(o.slot)) ? ' picked' : ''}" data-build='${escapeHtml(key(o.slot))}'>${chosen.has(key(o.slot)) ? '✓ ' : ''}${o.html}</button>`).join('')}</div>` : '';
        const body = list('On the bench', opts.bench) + list("Winners that don't go anywhere yet", opts.winners);
        $('#t-modal-body').innerHTML = `<h2>New match in ${escapeHtml(roundName)}</h2>
            <p class="muted">Tap two fighters. ${against ? `Win chances are against ${escapeHtml(fighterName(against))}.` : ''}
            Already played it? Create the match, then pick the winner on its card.</p>
            ${body || '<p>Nobody available: add fighters to the bench first, or create an empty match and fill it later.</p>'}
            <div class="row" style="margin-top:.75rem">
                <button type="button" class="btn go" id="build-create" ${picked.length === 2 ? '' : 'disabled'}>Create match</button>
                <button type="button" class="btn secondary small" id="build-empty">${picked.length ? 'Create with one, fill the other later' : 'Create an empty match'}</button>
            </div>`;
        $$('#t-modal-body [data-build]').forEach(btn => btn.addEventListener('click', () => {
            const slot = JSON.parse(btn.dataset.build);
            const i = picked.findIndex(s => key(s) === key(slot));
            if (i >= 0) picked.splice(i, 1);
            else if (picked.length < 2) picked.push(slot);
            else picked[1] = slot;
            draw();
        }));
        const create = async () => {
            if (await op('add_match', { round_id: roundId, top: picked[0] || null, bot: picked[1] || null })) closeModal();
        };
        $('#build-create').addEventListener('click', create);
        $('#build-empty').addEventListener('click', create);
    };
    openModal('');
    draw();
}

/** Who will play which fighter of a match (optional): their point is then counted without asking. */
function openPlayerPicks(mid) {
    const draw = () => {
        const m = byMatch()[mid];
        if (!m || m.winner) { closeModal(); return; }
        const top = escapeHtml(fighterName(m.top_fighter)), bot = escapeHtml(fighterName(m.bot_fighter));
        const name = pid => escapeHtml(playerOf(pid) ? playerOf(pid).name : pid);
        const tag = pid => `<span class="t-player-tag" style="--pc:${playerColor(pid)}">${name(pid)}</span>`;
        let options;
        if (TOURNAMENT.players.length === 2) {
            const [a, b] = TOURNAMENT.players.map(p => p.id);
            const opt = (t, o) => `<button type="button" class="t-option${m.top_player === t && m.bot_player === o ? ' picked' : ''}"
                data-picks='${JSON.stringify({ top: t, bot: o })}'>${tag(t)} plays ${top} &nbsp;·&nbsp; ${tag(o)} plays ${bot}</button>`;
            options = `<div class="t-options">${opt(a, b)}${opt(b, a)}</div>`;
        } else {
            const row = (side, fname) => {
                const cur = side === 'top' ? m.top_player : m.bot_player;
                return `<h3>${fname}</h3><div class="t-player-btns">${TOURNAMENT.players.map(p =>
                    `<button type="button" class="t-player-btn${cur === p.id ? ' on' : ''}" style="--pc:${playerColor(p.id)}"
                        data-picks='${JSON.stringify({ [side]: cur === p.id ? null : p.id })}'>${escapeHtml(p.name)}</button>`).join('')}</div>`;
            };
            options = row('top', top) + row('bot', bot);
        }
        $('#t-modal-body').innerHTML = `<h2>Who plays ${escapeHtml(m.label)}?</h2>
            <p class="muted">Optional. When the winner is picked, the point goes straight to whoever plays them, without asking.</p>
            ${options}
            ${m.top_player || m.bot_player ? `<div class="t-options" style="margin-top:.5rem"><button type="button" class="t-option" data-picks='${JSON.stringify({ top: null, bot: null })}'>No picks</button></div>` : ''}`;
        $$('#t-modal-body [data-picks]').forEach(btn => btn.addEventListener('click', async () => {
            const ok = await op('set_picks', { mid, picks: JSON.parse(btn.dataset.picks) });
            if (ok && TOURNAMENT.players.length === 2) closeModal(); else if (ok) draw();
        }));
    };
    openModal('');
    draw();
}

/** Phone-friendly way to move a match to another round (dragging does the same on a computer). */
function openMoveToRound(mid) {
    const m = byMatch()[mid];
    openModal(`<h2>Move ${escapeHtml(m.label)}</h2>
        <p class="muted">Its result and fighters stay the same. A match has to come before the match its winner goes to,
        so some rounds may be refused.</p>
        <div class="t-options">${TOURNAMENT.rounds.map(r => `<button type="button" class="t-option" data-move-to="${r.id}"
            ${r.id === m.round ? 'disabled' : ''}>${escapeHtml(r.name)}${r.id === m.round ? ' <span class="muted">(where it is now)</span>' : ''}</button>`).join('')}</div>`);
    $$('#t-modal-body [data-move-to]').forEach(btn => btn.addEventListener('click', async () => {
        if (await op('move_to_round', { mid, round_id: btn.dataset.moveTo })) closeModal();
    }));
}

/*************************** DRAG AND DROP (edit mode; mouse and touch) ***************************/
// Grab anything with data-drag (⠿ on matches and slots, the bench chips):
//   a match   → onto another round (goes to the end) or onto another match (goes just before it)
//   a slot    → onto another slot of a match not played yet (they swap), or onto the bench
//   the bench → onto an empty slot (goes in), a filled slot (replace or play-in), or a round (new match)
// Built on pointer events rather than HTML drag-and-drop so it works with fingers too.
let drag = null;   // {kind, mid, side, fighter, el, ghost, startX, startY, x, y, started, target}
const DRAG_START_PX = 6;
const EDGE_PX = 70;

function dropTargetAt(x, y) {
    if (!drag) return null;
    const el = document.elementFromPoint(x, y);
    if (!el) return null;
    const slot = el.closest('.t-slot[data-open]');
    const card = el.closest('.t-card');
    const round = el.closest('.t-round');
    const bench = el.closest('#bench');
    if (drag.kind === 'match') {
        if (card && card.dataset.mid !== drag.mid) return { el: card, action: 'before', mid: card.dataset.mid };
        if (round && !card) return { el: round, action: 'to-round', round: round.dataset.round };
        return null;
    }
    if (drag.kind === 'slot') {
        if (slot && !(slot.dataset.mid === drag.mid && slot.dataset.side === drag.side)) {
            return { el: slot, action: 'swap', mid: slot.dataset.mid, side: slot.dataset.side };
        }
        const m = byMatch()[drag.mid];
        if (bench && m && m[drag.side] && m[drag.side].fighter) return { el: $('#bench'), action: 'to-bench' };
        return null;
    }
    if (drag.kind === 'bench') {
        if (slot) return { el: slot, action: 'into-slot', mid: slot.dataset.mid, side: slot.dataset.side };
        if (round && !card) return { el: round, action: 'new-match', round: round.dataset.round };
    }
    return null;
}

function markTarget(target) {
    $$('.drop-target').forEach(el => { if (!target || el !== target.el) el.classList.remove('drop-target'); });
    if (target) target.el.classList.add('drop-target');
}

function dragTick() {
    if (!drag || !drag.started) return;
    // Scroll the page while holding near the top or bottom edge
    if (drag.y < EDGE_PX) window.scrollBy(0, -Math.ceil((EDGE_PX - drag.y) / 4));
    else if (drag.y > window.innerHeight - EDGE_PX) window.scrollBy(0, Math.ceil((drag.y - window.innerHeight + EDGE_PX) / 4));
    drag.target = dropTargetAt(drag.x, drag.y);
    markTarget(drag.target);
    requestAnimationFrame(dragTick);
}

document.addEventListener('pointerdown', e => {
    const src = e.target.closest('[data-drag]');
    if (!src || !editing() || e.button > 0 || e.target.closest('button')) return;
    e.preventDefault();
    drag = { kind: src.dataset.drag, mid: src.dataset.mid, side: src.dataset.side, fighter: src.dataset.fighter,
             el: src.dataset.drag === 'match' ? src.closest('.t-card') : src.closest('.t-slot, .t-bench-chip'),
             startX: e.clientX, startY: e.clientY, x: e.clientX, y: e.clientY, started: false, target: null };
});

document.addEventListener('pointermove', e => {
    if (!drag) return;
    drag.x = e.clientX;
    drag.y = e.clientY;
    if (!drag.started) {
        if (Math.hypot(e.clientX - drag.startX, e.clientY - drag.startY) < DRAG_START_PX) return;
        drag.started = true;
        const ghost = drag.el.cloneNode(true);
        ghost.classList.add('t-ghost');
        ghost.style.width = `${Math.min(drag.el.offsetWidth, 280)}px`;
        document.body.appendChild(ghost);
        drag.ghost = ghost;
        drag.el.classList.add('dragging');
        document.body.classList.add('t-dragging');
        requestAnimationFrame(dragTick);
    }
    drag.ghost.style.transform = `translate(${e.clientX + 8}px, ${e.clientY + 8}px)`;
});

function endDrag() {
    if (drag && drag.ghost) drag.ghost.remove();
    $$('.dragging, .drop-target').forEach(el => el.classList.remove('dragging', 'drop-target'));
    document.body.classList.remove('t-dragging');
    drag = null;
}

document.addEventListener('pointercancel', endDrag);
document.addEventListener('pointerup', async e => {
    if (!drag) return;
    const d = drag;
    const target = d.started ? dropTargetAt(e.clientX, e.clientY) : null;
    endDrag();
    if (!target) return;
    if (d.kind === 'match') {
        if (target.action === 'before') await op('move_to_round', { mid: d.mid, round_id: byMatch()[target.mid].round, before: target.mid });
        else await op('move_to_round', { mid: d.mid, round_id: target.round });
    } else if (d.kind === 'slot') {
        if (target.action === 'swap') await op('swap_slots', { mid_a: d.mid, side_a: d.side, mid_b: target.mid, side_b: target.side });
        else await op('set_slot', { mid: d.mid, side: d.side, slot: null });
    } else if (d.kind === 'bench') {
        if (target.action === 'new-match') {
            await op('add_match', { round_id: target.round, top: { fighter: d.fighter } });
            return;
        }
        const m = byMatch()[target.mid];
        const holder = target.side === 'top' ? m.top_fighter : m.bot_fighter;
        if (!m[target.side]) {
            await op('set_slot', { mid: target.mid, side: target.side, slot: { fighter: d.fighter } });
            return;
        }
        // A filled slot: ask whether the newcomer replaces them or has to beat them first
        const who = holder ? escapeHtml(fighterName(holder)) : 'whoever wins the earlier match';
        const pct = holder && matchup(d.fighter, holder) ? ` (${matchup(d.fighter, holder)[0]}% to win)` : '';
        openModal(`<h2>${escapeHtml(fighterName(d.fighter))} → ${escapeHtml(m.label)}</h2>
            <div class="t-options">
                <button type="button" class="t-option" data-choice="playin"><strong>Play-in:</strong> ${escapeHtml(fighterName(d.fighter))}
                    has to beat ${who} first${pct}; the winner takes the slot</button>
                ${m[target.side].fighter ? `<button type="button" class="t-option" data-choice="replace"><strong>Replace:</strong>
                    ${escapeHtml(fighterName(d.fighter))} takes the slot and ${who} goes to the bench</button>` : ''}
            </div>`);
        $$('#t-modal-body [data-choice]').forEach(btn => btn.addEventListener('click', async () => {
            const ok = btn.dataset.choice === 'playin'
                ? await op('insert_play_in', { mid: target.mid, side: target.side, challenger: { fighter: d.fighter } })
                : await op('set_slot', { mid: target.mid, side: target.side, slot: { fighter: d.fighter } });
            if (ok) closeModal();
        }));
    }
});

function openAddFighters() {
    const inTournament = new Set([...TOURNAMENT.bench, ...TOURNAMENT.matches.flatMap(m => [m.top, m.bot])
        .filter(s => s && s.fighter).map(s => s.fighter)]);
    const sets = ALL_SETS.map(s => {
        const fs = ALL_FIGHTERS_JS.filter(f => f.sets.includes(s) && !inTournament.has(f.id));
        if (!fs.length) return '';
        return `<div class="t-add-set"><label><input type="checkbox" class="add-set"> <strong>${escapeHtml(s)}</strong></label>
            <div>${fs.map(f => `<label class="t-pick"><input type="checkbox" class="add-fighter" value="${f.id}">${fighterHTML(f.id)}</label>`).join('')}</div></div>`;
    }).join('');
    openModal(`<h2>Add fighters to the bench</h2>
        <p class="muted">They wait on the bench until you put them in the bracket: use <strong>change</strong> on an empty slot,
        <strong>+ play-in</strong> to have them challenge someone for a place, or <strong>+ match</strong> to make a new match.</p>
        ${sets || '<p>Every fighter is already in this tournament.</p>'}
        <button type="button" class="btn go" id="confirm-add" style="margin-top:.75rem">Add to the bench</button>`);
    $$('.add-set').forEach(cb => cb.addEventListener('change', () => {
        $$('.add-fighter', cb.closest('.t-add-set')).forEach(f => f.checked = cb.checked);
    }));
    $('#confirm-add').addEventListener('click', async () => {
        const fighters = [...new Set($$('.add-fighter:checked').map(cb => cb.value))];
        if (!fighters.length) return;
        if (await op('add_to_bench', { fighters })) closeModal();
    });
}

async function openHistory() {
    openModal('<h2>History</h2><p class="muted">Loading…</p>');
    const items = await fetch(`${API}/history`).then(r => r.json()).catch(() => []);
    $('#t-modal-body').innerHTML = `<h2>History</h2>
        <p class="muted">Every change is a version. Restoring one saves it again as the newest version, so you can always come back.</p>
        <table class="data"><tbody>${items.map(h => `<tr><td class="num">v${h.version}</td><td>${escapeHtml(named(h.summary))}</td>
            <td class="muted">${escapeHtml(h.saved_at.slice(0, 16).replace('T', ' '))}</td>
            <td>${h.version === TOURNAMENT.version ? '<span class="muted">current</span>'
                : `<button type="button" class="btn secondary small" data-restore="${h.version}">Restore</button>`}</td></tr>`).join('')}</tbody></table>`;
    $$('[data-restore]').forEach(b => b.addEventListener('click', async () => {
        if (!confirm(`Go back to version ${b.dataset.restore}? (This is saved as a new version, so it can be undone.)`)) return;
        const r = await fetch(`${API}/restore`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ restore: Number(b.dataset.restore) }) });
        const data = await r.json().catch(() => ({}));
        if (data.tournament) TOURNAMENT = data.tournament;
        if (!r.ok) alert(data.error || 'Restore failed.');
        else setStatus(data.summary);
        closeModal();
    }));
}

/*************************** CLICKS ***************************/
document.addEventListener('click', async e => {
    const btn = e.target.closest('[data-act]');
    if (!btn) return;
    const { act, mid, side, round } = btn.dataset;
    const m = mid ? byMatch()[mid] : null;
    switch (act) {
        case 'win': await op('set_result', { mid, winner: side }); break;
        case 'player': await op('set_player', { mid, player: btn.dataset.player || null, role: btn.dataset.role || 'winner' }); break;
        case 'undo':
            if (confirm(`Undo the result of ${m.label}?`)) await op('undo_result', { mid });
            break;
        case 'change': openSlotPicker(mid, side); break;
        case 'picks': openPlayerPicks(mid); break;
        case 'playin': openPlayInPicker(mid, side); break;
        case 'swap':
            if (!pendingSwap) { pendingSwap = { mid, side }; setStatus('Now pick the slot to swap with (⇄ on another slot).'); render(); }
            else {
                const first = pendingSwap;
                pendingSwap = null;
                if (first.mid === mid && first.side === side) { setStatus(''); render(); break; }
                await op('swap_slots', { mid_a: first.mid, side_a: first.side, mid_b: mid, side_b: side });
            }
            break;
        case 'delete-match':
            if (confirm(`Delete ${m.label}? Its fighters go back to the bench.`)) await op('delete_match', { mid });
            break;
        case 'rename-match': {
            const label = prompt('Match name', m.label);
            if (label) await op('rename_match', { mid, label });
            break;
        }
        case 'move': await op('move_match', { mid, direction: btn.dataset.dir }); break;
        case 'move-round': openMoveToRound(mid); break;
        case 'add-match': openMatchBuilder(round); break;
        case 'rebalance': await op('rebalance_round', { round_id: round }); break;
        case 'rename-round': {
            const r = TOURNAMENT.rounds.find(x => x.id === round);
            const name = prompt('Round name', r.name);
            if (name) await op('rename_round', { round_id: round, name });
            break;
        }
        case 'add-round': {
            const name = prompt('Name of the new round', 'Play-in');
            if (name) await op('add_round', { name, before: round });
            break;
        }
        case 'delete-round': await op('delete_round', { round_id: round }); break;
        case 'remove-adjustment':
            if (confirm('Remove this score adjustment?') && await op('remove_adjustment', { adjustment_id: btn.dataset.adj })) {
                setStatus('Saved.');
                await loadAdjustments();
            }
            break;
        case 'toggle-round':
            folded.set(round, !folded.get(round));
            renderRounds();
            break;
        case 'unbench':
            if (confirm(`Take ${fighterName(btn.dataset.fighter)} out of the tournament?`)) await op('remove_fighter', { fighter: btn.dataset.fighter });
            break;
    }
});

$('#show-adjustments').addEventListener('click', () => {
    if (adjustments) { adjustments = null; renderAdjustments(); } else loadAdjustments();
});
$('#edit-mode').addEventListener('change', () => {
    storeSet(EDIT_KEY, editing());
    adjustments = null;  // hidden again next time
    pendingSwap = null;
    render();
});
$$('.t-segment [data-scoring]').forEach(b => b.addEventListener('click', () => {
    if (b.dataset.scoring !== TOURNAMENT.scoring) op('set_scoring', { scoring: b.dataset.scoring });
}));
$('#add-adjustment').addEventListener('click', async () => {
    const points = parseFloat($('#adj-points').value);
    if (!points) { alert('Enter the points (with a minus to take points away).'); return; }
    const ok = await op('add_adjustment', { player: $('#adj-player').value, points, scoring: $('#adj-scoring').value, note: $('#adj-note').value });
    if (ok) {
        $('#adj-points').value = ''; $('#adj-note').value = '';
        setStatus('Saved.');  // not the summary, which names the points and the player
        if (adjustments) await loadAdjustments();
    }
});
$('#rebalance-current').addEventListener('click', () => {
    if (!TOURNAMENT.current_round) { alert('Every match has been played.'); return; }
    op('rebalance_round', { round_id: TOURNAMENT.current_round });
});
$('#open-history').addEventListener('click', openHistory);
$('#save-name').addEventListener('click', () => op('rename', { name: $('#edit-name').value }));
$('#add-player').addEventListener('click', () => {
    $('#edit-players').insertAdjacentHTML('beforeend', '<input type="text" class="edit-player" placeholder="New player" style="width:8rem">');
});
$('#save-players').addEventListener('click', () => op('set_players', { names: $$('.edit-player').map(i => i.value) }));
$('#open-add-fighters').addEventListener('click', openAddFighters);
$('#pair-bench').addEventListener('click', () => {
    const v = $('#pair-round').value;
    op('pair_bench', v.startsWith('new:') ? { before: v.slice(4) } : { round_id: v });
});
$('#slot-in').addEventListener('click', () => {
    const round = TOURNAMENT.rounds.find(r => r.id === $('#slot-in-round').value);
    if (round && confirm(`Give every benched fighter a play-in for a place in ${round.name}?`)) {
        op('slot_in', { round_id: round.id });
    }
});
$('#add-round-end').addEventListener('click', async () => {
    const name = prompt('Name of the new round', 'New round');
    if (name) await op('add_round', { name });
});
$('#round-nav').addEventListener('click', e => {
    const link = e.target.closest('[data-round-link]');
    if (!link) return;
    e.preventDefault();
    const rid = link.dataset.roundLink;
    if (folded.get(rid)) { folded.set(rid, false); renderRounds(); }
    const target = document.getElementById(`round-${rid}`);
    if (target) window.scrollTo({ top: target.getBoundingClientRect().top + window.scrollY - 70, behavior: 'smooth' });
});
$('#t-modal-close').addEventListener('click', closeModal);
$('#t-modal').addEventListener('click', e => { if (e.target.id === 't-modal') closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape' && modalOpen) closeModal(); });

$('#edit-mode').checked = storeGet(EDIT_KEY, false) === true;
render();
setInterval(poll, 3000);
