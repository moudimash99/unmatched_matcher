/* ==============================================================
   Unmatched Fighter Chooser – Client‑side UX helpers
   ————————————————————————————————————————————————
   ✨ Refactored to use a local win-percentage matrix and
      a centralized UI update function for robust, instant
      matchup changes.
================================================================*/

/*************************** DOM SHORTCUTS  ***************************/
const qs = (sel, ctx = document) => ctx.querySelector(sel);
const qsa = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

/*************************** COOKIE HELPERS  ***************************/
function setCookie(name, value, days = 3650) { // ~10 years
    const exp = new Date(Date.now() + days * 864e5).toUTCString();
    document.cookie = `${encodeURIComponent(name)}=${encodeURIComponent(value)}; expires=${exp}; path=/; SameSite=Lax`;
}

function getCookie(name) {
    return document.cookie.split('; ').reduce((v, c) => {
        const [k, val] = c.split('=');
        return k === encodeURIComponent(name) ? decodeURIComponent(val) : v;
    }, '');
}

/*************************** INITIALIZATION  ***************************/
document.addEventListener('DOMContentLoaded', () => {
    setupSetSelection();
    setupPlaystyleToggles();
    setupP1SelectionToggle();
    annotateLockButtons();
    setupResultCardActions();
});

/*************************** UI SETUP FUNCTIONS  ***************************/
function setupSetSelection() {
    const wrapper = qs('.set-selection');
    if (!wrapper) return;

    const toggleBtn = qs('#toggle-set-selection-btn');
    const SELECT_COLLAPSE_KEY = 'ufs_sets_collapsed';
    const ALL_SETS_KEY = 'ufs_owned_sets';
    const selectAllBtn = qs('#select-all-sets-btn');
    const deselectAllBtn = qs('#deselect-all-sets-btn');
    const checkboxes = qsa('#set-checkboxes input[type="checkbox"]');

    // Restore collapse state from cookie
    const wasCollapsed = getCookie(SELECT_COLLAPSE_KEY) === '1';
    wrapper.classList.toggle('collapsed', wasCollapsed);
    toggleBtn.setAttribute('aria-expanded', String(!wasCollapsed));

    toggleBtn.addEventListener('click', () => {
        const collapsed = wrapper.classList.toggle('collapsed');
        toggleBtn.setAttribute('aria-expanded', String(!collapsed));
        setCookie(SELECT_COLLAPSE_KEY, collapsed ? '1' : '0');
    });
    // Restore checkboxes from cookie (JSON)
    const storedSets = getCookie(ALL_SETS_KEY);
    if (storedSets) {
        try {
            const arr = JSON.parse(storedSets);
            checkboxes.forEach(cb => {
                cb.checked = arr.includes(cb.value);
            });
        } catch (e) {
            console.error("Could not parse owned sets cookie:", e);
        }
    }


    // Persist checkbox state on change (JSON)
    const persist = () => {
        const checked = checkboxes
            .filter(cb => cb.checked)
            .map(cb => cb.value);
        setCookie(ALL_SETS_KEY, JSON.stringify(checked));
    };

    checkboxes.forEach(cb => cb.addEventListener('change', persist));
    selectAllBtn?.addEventListener('click', () => { checkboxes.forEach(cb => cb.checked = true); persist(); });
    deselectAllBtn?.addEventListener('click', () => { checkboxes.forEach(cb => cb.checked = false); persist(); });
}

function setupPlaystyleToggles() {
    qsa('.toggle-playstyle-btn').forEach(btn => {
        const target = qs(`#${btn.dataset.target}`);
        if (!target) return;
        btn.setAttribute('aria-expanded', String(!target.classList.contains('collapsed')));
        btn.addEventListener('click', () => {
            const collapsed = target.classList.toggle('collapsed');
            btn.setAttribute('aria-expanded', String(!collapsed));
        });
    });
}

function setupP1SelectionToggle() {
    const selMethod = qs('#p1_selection_method');
    const directSec = qs('#p1-direct-choice-section');
    const prefSec = qs('#p1-preferences-section');
    const oppDummy = qs('#opponent-controls .top-control-wrapper');

    function toggle() {
        if (!selMethod || !directSec || !prefSec || !oppDummy) return;
        if (selMethod.value === 'direct_choice') {
            directSec.style.display = 'block';
            prefSec.style.display = 'none';
            oppDummy.classList.add('hidden');
        } else {
            directSec.style.display = 'none';
            prefSec.style.display = 'grid';
            oppDummy.classList.remove('hidden');
        }
    }
    selMethod?.addEventListener('change', toggle);
    toggle(); // Initial state
}

/*************************** CORE INTERACTION LOGIC  ***************************/

/**
 * Changes server-side lock buttons to client-side JS buttons to prevent reloads.
 */
function annotateLockButtons() {
    qsa('.lock-button').forEach(btn => {
        const val = btn.value || '';
        let m = val.match(/^(lock|unlock)_(p1|opp):?([^:]*)$/);
        if (m) {
            btn.dataset.action = m[1];
            btn.dataset.playerPrefix = m[2];
            btn.dataset.fighterId = m[3] || qs(`#current_locked_${m[2]}_id`).value;
            btn.dataset.locked = (m[1] === 'unlock').toString();
            btn.type = 'button'; // CRITICAL: Prevent form submission
        }
    });
}

/**
 * Sets up a single event listener on the results area to handle all card interactions.
 */
function setupResultCardActions() {
    const results = qs('#results-display-area');
    if (!results) return;

    results.addEventListener('click', (e) => {
        const tgt = e.target;
        if (tgt.closest('.select-alternative-btn')) {
            e.preventDefault();
            promoteAlternative(tgt.closest('.fighter-card'));
        } else if (tgt.closest('.lock-button')) {
            e.preventDefault();
            toggleLock(tgt.closest('.lock-button'));
        }
    });
}

/**
 * Promotes an alternative card to the main slot and updates the UI.
 * @param {HTMLElement} altCard - The alternative fighter card that was clicked.
 */
function promoteAlternative(altCard) {
    const player = altCard.dataset.playerPrefix;
    const mainCard = qs(`#${player}-main-suggestion`);
    if (!mainCard) return;

    const mainClone = mainCard.cloneNode(true);
    const altClone = altCard.cloneNode(true);

    // Configure the newly promoted card
    altClone.id = `${player}-main-suggestion`;
    altClone.classList.replace('alternative-suggestion', 'main-suggestion');
    altClone.querySelector('.fighter-card-footer').innerHTML = lockButtonHTML(player, altCard.dataset.fighterId);

    // Configure the newly demoted card
    mainClone.id = '';
    mainClone.classList.replace('main-suggestion', 'alternative-suggestion');
    mainClone.querySelector('.fighter-card-footer').innerHTML = selectButtonHTML();

    // Swap the cards in the DOM
    mainCard.replaceWith(altClone);
    altCard.replaceWith(mainClone);

    // Annotate the new buttons and update all win percentages
    annotateLockButtons();
    updateAllWinPercentages();
}

/**
 * Toggles the lock state of a fighter card both visually and in the hidden form input.
 * @param {HTMLElement} btn - The lock/unlock button that was clicked.
 */
function toggleLock(btn) {
    const player = btn.dataset.playerPrefix;
    const fid = btn.dataset.fighterId;
    const hidden = qs(`#current_locked_${player}_id`);

    if (btn.dataset.locked === 'true') { // --- UNLOCK ---
        btn.dataset.locked = 'false';
        hidden.value = '';
        btn.classList.replace('btn-unlock', 'btn-lock');
        btn.textContent = '🔒 Lock Fighter';
    } else {                              // --- LOCK ---
        btn.dataset.locked = 'true';
        hidden.value = fid;
        btn.classList.replace('btn-lock', 'btn-unlock');
        btn.textContent = '🔓 Fighter Locked';
    }
}

/*************************** WIN PERCENTAGE & UI UPDATES  ***************************/

/**
 * Central function to update all win percentages on the page based on the current main matchup.
 */
function updateAllWinPercentages() {
    const p1_main_id = extractFighterIdFromCard(qs('#p1-main-suggestion'));
    const opp_main_id = extractFighterIdFromCard(qs('#opp-main-suggestion'));
    if (!p1_main_id || !opp_main_id) return;

    // Update all cards on Player 1's side
    qsa(`[data-player-prefix="p1"]`).forEach(card => {
        updateCardWinPct(card, opp_main_id);
    });

    // Update all cards on the Opponent's side
    qsa(`[data-player-prefix="opp"]`).forEach(card => {
        updateCardWinPct(card, p1_main_id);
    });
}

/**
 * Updates the win percentage text for a single card.
 * @param {HTMLElement} card - The fighter card to update.
 * @param {string} opponentId - The ID of the fighter it is facing.
 */
function updateCardWinPct(card, opponentId) {
    const cardFighterId = extractFighterIdFromCard(card);
    const winPctData = getWinPctFromMatrix(cardFighterId, opponentId);
    const winHtmlElement = card.querySelector('.win-percentage-text');
    if (winHtmlElement) {
        winHtmlElement.innerHTML = `<strong>Win vs ${winPctData.opponent_name}:</strong> ${winPctData.percentage}%`;
    }
}

/**
 * Looks up a win percentage from the global matrix.
 * Mirrors the server-side _get_win_rate() logic.
 * @param {string} fighterId - The ID of the first fighter.
 * @param {string} opponentId - The ID of the second fighter.
 * @returns {number} The win percentage (0-100) for fighterId vs opponentId.
 */
function getWinRate(fighterId, opponentId) {
    if (!fighterId || !opponentId || typeof WIN_MATRIX !== 'object') {
        return 50; // Default to fair
    }
    
    // Check A vs B
    if (WIN_MATRIX[fighterId] && WIN_MATRIX[fighterId][opponentId] !== undefined) {
        return WIN_MATRIX[fighterId][opponentId];
    }
    
    // Check B vs A (and invert)
    if (WIN_MATRIX[opponentId] && WIN_MATRIX[opponentId][fighterId] !== undefined) {
        return 100 - WIN_MATRIX[opponentId][fighterId];
    }
    
    return 50; // Default to fair if unknown
}

/**
 * Looks up a win percentage from the global matrix and returns display info.
 * @param {string} fighterId - The ID of the first fighter.
 * @param {string} opponentId - The ID of the second fighter.
 * @returns {{percentage: number|string, opponent_name: string}}
 */
function getWinPctFromMatrix(fighterId, opponentId) {
    if (!fighterId || !opponentId || typeof WIN_MATRIX !== 'object') {
        return { percentage: 'N/A', opponent_name: 'Opponent' };
    }
    
    const winRate = getWinRate(fighterId, opponentId);
    const opponentInfo = ALL_FIGHTERS_JS.find(f => f.id === opponentId);
    const opponentName = opponentInfo ? opponentInfo.name : 'Opponent';
    
    return { percentage: Math.round(winRate), opponent_name: opponentName };
}

/*************************** HTML HELPERS  ***************************/
function lockButtonHTML(player, fid) {
    return `<button type="button" class="lock-button btn-lock" data-action="lock" data-player-prefix="${player}" data-fighter-id="${fid}" data-locked="false">🔒 Lock Fighter</button>`;
}

function selectButtonHTML() {
    return `<button type="button" class="select-alternative-btn">Select for Matchup</button>`;
}

function extractFighterIdFromCard(card) {
    return card?.dataset.fighterId || '';
}
