/* ==============================================================
   Shared helpers for the tool pages (collection, fighters, draft, log…)
   Needs ALL_FIGHTERS_JS, MATCHUPS, FULL_CONFIDENCE_GAMES, CLUB_MATCHUP_URL
   from base.html.
================================================================*/

const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

/*************************** COOKIES (same format as script.js) ***************************/
function setCookie(name, value, days = 3650) {
    const exp = new Date(Date.now() + days * 864e5).toUTCString();
    document.cookie = `${encodeURIComponent(name)}=${encodeURIComponent(value)}; expires=${exp}; path=/; SameSite=Lax`;
}

function getCookie(name) {
    return document.cookie.split('; ').reduce((v, c) => {
        const [k, val] = c.split('=');
        return k === encodeURIComponent(name) ? decodeURIComponent(val) : v;
    }, '');
}

/*************************** COLLECTION ***************************/
const COLLECTION_KEY = 'ufs_default_owned_sets';  // "My collection" = the matcher's saved default
const CURRENT_SETS_KEY = 'ufs_owned_sets';         // the matcher's current selection

function saveCollection(sets) {
    const value = JSON.stringify(sets);
    setCookie(COLLECTION_KEY, value);
    setCookie(CURRENT_SETS_KEY, value);  // so the matcher opens with the same sets
}

/*************************** BROWSER STORAGE (may be blocked) ***************************/
function storeGet(key, fallback) {
    try {
        const raw = localStorage.getItem(key);
        return raw === null ? fallback : JSON.parse(raw);
    } catch (e) {
        return fallback;
    }
}

function storeSet(key, value) {
    try {
        localStorage.setItem(key, JSON.stringify(value));
        return true;
    } catch (e) {
        return false;
    }
}

/*************************** FIGHTERS & MATCHUPS ***************************/
const FIGHTER_BY_ID = Object.fromEntries(ALL_FIGHTERS_JS.map(f => [f.id, f]));

function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/** [estimated win % for a vs b, games played], or null. */
function matchup(a, b) {
    return (MATCHUPS[a] && MATCHUPS[a][b]) || null;
}

function clubUrl(a, b) {
    return `${CLUB_MATCHUP_URL}?h1=${FIGHTER_BY_ID[a].club_key}&h2=${FIGHTER_BY_ID[b].club_key}`;
}

/** "62% · 140 games" or "~48% · estimate, 3 games" (mirrors the matcher's win line). */
function winText(a, b) {
    const m = matchup(a, b);
    if (!m) return '';
    const [pct, games] = m;
    if (games === 0) return `~${pct}% <span class="games-note low-data">· estimate, no games yet</span>`;
    if (games < FULL_CONFIDENCE_GAMES) {
        return `~${pct}% <span class="games-note low-data">· estimate, ${games} game${games === 1 ? '' : 's'}</span>`;
    }
    return `${pct}% <span class="games-note">· ${games.toLocaleString('en-US')} games</span>`;
}

/** Background colour for a win % cell: red (bad) → white (50) → green (good), faded when unproven. */
function winColor(pct, games) {
    const d = Math.max(-1, Math.min(1, (pct - 50) / 25));
    const alpha = 0.15 + 0.6 * Math.abs(d) * (games >= FULL_CONFIDENCE_GAMES ? 1 : 0.45);
    return d >= 0 ? `rgba(40, 167, 69, ${alpha})` : `rgba(220, 53, 69, ${alpha})`;
}

function fighterChip(id) {
    const f = FIGHTER_BY_ID[id];
    return `<a class="fighter-chip" href="/fighter/${f.id}"><img src="${f.image_url}" alt="">${escapeHtml(f.name)}</a>`;
}

/*************************** PAGE BOOT ***************************/
document.addEventListener('DOMContentLoaded', () => {
    // Paint server-rendered heatmap / win cells
    $$('[data-win]').forEach(el => {
        el.style.background = winColor(Number(el.dataset.win), Number(el.dataset.games || 0));
    });
});
