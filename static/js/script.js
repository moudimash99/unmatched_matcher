/* ==============================================================
   Unmatched Fighter Chooser – Client‑side UX helpers
   ————————————————————————————————————————————————
   ✨ 2025‑07 – Re‑worked to address:
      1. Selecting an alternative should *not* auto‑lock.
      2. The 🔒/🔓 button must toggle instantly (no full reload).
      3. Locking must leave *all* current suggestions visible.
      4. Owned‑sets collapse + checkbox state persist 10 yrs via cookies.
================================================================*/

/***************************  DOM SHORTCUTS  ***************************/
const qs  = (sel, ctx = document) => ctx.querySelector(sel);
const qsa = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

/***************************  COOKIE HELPERS  ***************************/
function setCookie(name, value, days = 3650) { // ≈10 yrs
    const exp = new Date(Date.now() + days * 864e5).toUTCString();
    document.cookie = `${encodeURIComponent(name)}=${encodeURIComponent(value)}; expires=${exp}; path=/`;
}
function getCookie(name) {
    return document.cookie.split('; ').reduce((v, c) => {
        const [k, val] = c.split('=');
        return k === encodeURIComponent(name) ? decodeURIComponent(val) : v;
    }, '');
}

/***************************  DOMContentLoaded  ***************************/
document.addEventListener('DOMContentLoaded', () => {
    setupSetSelection();
    setupPlaystyleToggles();
    setupP1SelectionToggle();
    annotateLockButtons();
    setupResultCardActions();
});

/***************************  OWNED–SET PANEL  ***************************/
function setupSetSelection() {
    const wrapper = qs('.set-selection');
    if (!wrapper) return;

    const toggleBtn = qs('#toggle-set-selection-btn');
    const SELECT_COLLAPSE_KEY = 'ufs_sets_collapsed';
    const ALL_SETS_KEY        = 'ufs_owned_sets';
    const selectAllBtn        = qs('#select-all-sets-btn');
    const deselectAllBtn      = qs('#deselect-all-sets-btn');
    const checkboxes          = qsa('#set-checkboxes input[type="checkbox"]');

    // —— Restore collapse state
    const wasCollapsed = getCookie(SELECT_COLLAPSE_KEY) === '1';
    wrapper.classList.toggle('collapsed', wasCollapsed);
    toggleBtn.setAttribute('aria-expanded', String(!wasCollapsed));

    toggleBtn.addEventListener('click', () => {
        const collapsed = wrapper.classList.toggle('collapsed');
        toggleBtn.setAttribute('aria-expanded', String(!collapsed));
        setCookie(SELECT_COLLAPSE_KEY, collapsed ? '1' : '0');
    });

    // —— Restore checkboxes
    const storedSets = getCookie(ALL_SETS_KEY);
    if (storedSets) {
        const arr = storedSets.split(',');
        checkboxes.forEach(cb => cb.checked = arr.includes(cb.value));
    }

    // —— Persist on change
    const persist = () => {
        const checked = checkboxes.filter(cb => cb.checked).map(cb => cb.value);
        setCookie(ALL_SETS_KEY, checked.join(','));
    };
    checkboxes.forEach(cb => cb.addEventListener('change', persist));
    selectAllBtn?.addEventListener('click', () => { checkboxes.forEach(cb => cb.checked = true); persist(); });
    deselectAllBtn?.addEventListener('click', () => { checkboxes.forEach(cb => cb.checked = false); persist(); });
}

/***************************  PLAY‑STYLE PANELS  ***************************/
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

/***************************  P1 MODE SWITCH  ***************************/
function setupP1SelectionToggle() {
    const selMethod = qs('#p1_selection_method');
    const directSec = qs('#p1-direct-choice-section');
    const prefSec   = qs('#p1-preferences-section');
    const oppDummy  = qs('#opponent-controls .top-control-wrapper');

    function toggle() {
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
    toggle();
}

/***************************  LOCK BUTTON ANNOTATION  ***************************/
function annotateLockButtons() {
    qsa('.lock-button').forEach(btn => {
        const val = btn.value || ''; // may be undefined if JS‑generated
        let m = val.match(/^lock_(p1|opp):(\d+)/);
        if (m) {
            btn.dataset.playerPrefix = m[1];
            btn.dataset.fighterId   = m[2];
            btn.dataset.locked      = 'false';
            btn.type = 'button'; // prevent implicit form submit
        } else if ((m = val.match(/^unlock_(p1|opp)$/))) {
            btn.dataset.playerPrefix = m[1];
            btn.dataset.fighterId   = qs(`#current_locked_${m[1]}_id`).value;
            btn.dataset.locked      = 'true';
            btn.type = 'button';
        }
    });
}

/***************************  RESULT‑CARD INTERACTIONS  ***************************/
function setupResultCardActions() {
    const results = qs('#results-display-area');
    if (!results) return;

    results.addEventListener('click', (e) => {
        const tgt = e.target;
        if (tgt.closest('.select-alternative-btn')) {
            e.preventDefault();
            promoteAlternative(tgt.closest('.select-alternative-btn'));
        } else if (tgt.closest('.lock-button')) {
            e.preventDefault();
            toggleLock(tgt.closest('.lock-button'));
        }
    });
}

/***********  WIN PERCENTAGE MATRIX  ***********/
let WIN_PERCENTAGE_MATRIX = {};

function getWinPercentageFromMatrix(fighterId, opponentId) {
    if (!fighterId || !opponentId || !WIN_PERCENTAGE_MATRIX) {
        return { percentage: 'N/A', opponent_name: 'Opponent' };
    }
    const key = [fighterId, opponentId].sort().join(':');
    const matrixEntry = WIN_PERCENTAGE_MATRIX[key];
    // Find the opponent's name for display purposes
    const opponent = ALL_FIGHTERS_JS.find(f => f.id === opponentId);
    const opponentName = opponent ? opponent.name : 'Opponent';
    if (matrixEntry && matrixEntry[fighterId] !== undefined) {
        return { percentage: matrixEntry[fighterId], opponent_name: opponentName };
    }
    return { percentage: 'N/A', opponent_name: opponentName };
}

/*********** ALT → MAIN (USING LOCAL MATRIX)  ***********/
function promoteAlternative(selBtn) {
    const player = selBtn.dataset.playerPrefix;
    const promotedFighterId = selBtn.dataset.fighterId;
    const altCard = selBtn.closest('.fighter-card');
    const mainCard = qs(`#${player}-main-suggestion`);
    if (!altCard || !mainCard) return;

    // --- Get the ID of the fighter this new card will be facing
    const opponentPlayer = (player === 'p1') ? 'opp' : 'p1';
    const opponentCard = qs(`#${opponentPlayer}-main-suggestion`);
    const opponentFighterId = extractFighterIdFromCard(opponentCard);

    // --- Clone nodes and rebuild the buttons
    const altClone = altCard.cloneNode(true);
    const mainClone = mainCard.cloneNode(true);
    
    altClone.id = `${player}-main-suggestion`;
    altClone.classList.replace('alternative-suggestion', 'main-suggestion');
    altClone.querySelector('.fighter-card-footer').innerHTML = 
        lockButtonHTML(player, promotedFighterId);

    const prevMainId = extractFighterIdFromCard(mainCard);
    mainClone.id = '';
    mainClone.classList.replace('main-suggestion', 'alternative-suggestion');
    mainClone.querySelector('.fighter-card-footer').innerHTML = 
        selectButtonHTML(player, prevMainId);
    
    // --- Swap in DOM
    mainCard.replaceWith(altClone);
    altCard.replaceWith(mainClone);
    
    // --- Annotate new buttons and update win percentages from the matrix
    annotateLockButtons();

    // Update the newly promoted card's win percentage text
    const { percentage: newPct, opponent_name: newOpponentName } = getWinPercentageFromMatrix(promotedFighterId, opponentFighterId);
    const newWinHtmlElement = altClone.querySelector('.fighter-details p:last-child');
    if(newWinHtmlElement) newWinHtmlElement.innerHTML = `<strong>Win vs ${newOpponentName}:</strong> ${newPct}%`;

    // Update the demoted card's win percentage text
    const { percentage: oldPct, opponent_name: oldOpponentName } = getWinPercentageFromMatrix(prevMainId, opponentFighterId);
    const oldWinHtmlElement = mainClone.querySelector('.fighter-details p:last-child');
    if(oldWinHtmlElement) oldWinHtmlElement.innerHTML = `<strong>Win vs ${oldOpponentName}:</strong> ${oldPct}%`;
}

/***********  LOCK / UNLOCK TOGGLE  ***********/
function toggleLock(btn) {
    const player = btn.dataset.playerPrefix;
    const fid    = btn.dataset.fighterId;
    const hidden = qs(`#current_locked_${player}_id`);

    if (btn.dataset.locked === 'true') { // ——— UNLOCK
        btn.dataset.locked = 'false';
        hidden.value = '';
        btn.classList.replace('btn-unlock', 'btn-lock');
        btn.textContent = '🔒 Lock Fighter';
    } else {                              // ——— LOCK
        btn.dataset.locked = 'true';
        hidden.value = fid;
        btn.classList.replace('btn-lock', 'btn-unlock');
        btn.textContent = '🔓 Fighter Locked';
    }
}

/***************************  HTML HELPERS  ***************************/
function lockButtonHTML(player, fid) {
    return `<button type="button" class="lock-button btn-lock" data-player-prefix="${player}" data-fighter-id="${fid}" data-locked="false">🔒 Lock Fighter</button>`;
}
function selectButtonHTML(player, fid) {
    return `<button type="button" class="select-alternative-btn" data-player-prefix="${player}" data-fighter-id="${fid}">Select for Matchup</button>`;
}
function extractFighterIdFromCard(card) {
    const lb = qs('.lock-button', card);
    if (lb) {
        return lb.dataset.fighterId || (lb.value && lb.value.split(':')[1]);
    }
    const sb = qs('.select-alternative-btn', card);
    return sb?.dataset.fighterId || '';
}
