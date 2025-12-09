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

/*************************** CONSTANTS ***************************/
const CONSENT_COOKIE_KEY = 'ufc_cookie_consent';
const INTRO_SEEN_KEY = 'ufc_intro_seen';
const MATCHUP_MODE_HELP_SEEN_KEY = 'ufc_matchup_mode_help_seen';
const ADVANCED_MODE_HELP_SEEN_KEY = 'ufc_advanced_mode_help_seen';

/*************************** ANALYTICS & CONSENT ***************************/
let analyticsEnabled = false;

function enableAnalytics() {
    analyticsEnabled = true;
    window.ufcAnalyticsEvents = window.ufcAnalyticsEvents || [];
    recordAnalytics('analytics_enabled', { source: 'cookie_accept' });
}

function recordAnalytics(eventName, payload = {}) {
    if (!analyticsEnabled) return;
    // Keep analytics client-side and focused on UX improvements only
    const entry = { event: eventName, at: new Date().toISOString(), ...payload };
    window.ufcAnalyticsEvents.push(entry);
    console.debug('[ufc-analytics]', entry);

      // 2. Send to GA4 if available
    if (typeof gtag === 'function') {
        gtag('event', eventName, payload);
    }
}

function initCookieConsent() {
    const banner = qs('#cookie-consent');
    if (!banner) return;

    const acceptBtn = qs('#cookie-accept', banner);
    const declineBtn = qs('#cookie-decline', banner);
    const consent = getCookie(CONSENT_COOKIE_KEY);

    if (consent === 'accepted') {
        banner.classList.add('hidden');
        enableAnalytics();
    } else if (consent === 'declined') {
        banner.classList.add('hidden');
    } else {
        banner.classList.remove('hidden');
    }

    acceptBtn?.addEventListener('click', () => {
        setCookie(CONSENT_COOKIE_KEY, 'accepted', 365);
        banner.classList.add('hidden');
        enableAnalytics();
    });

    declineBtn?.addEventListener('click', () => {
        setCookie(CONSENT_COOKIE_KEY, 'declined', 365);
        banner.classList.add('hidden');
        analyticsEnabled = false;
    });
}

/*************************** INITIALIZATION  ***************************/
document.addEventListener('DOMContentLoaded', () => {
    initCookieConsent();
    setupSetSelection();
    setupPlaystyleToggles();
    setupP1SelectionToggle();
    setupModeControls();
    setupModalCloseHandlers(); // Set up all modal close handlers first
    setupIntroModal();
    setupAnalyticsListeners();
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
    const updateToggleButton = (collapsed) => {
        if (!toggleBtn) return;
        toggleBtn.setAttribute('aria-expanded', String(!collapsed));
        toggleBtn.textContent = collapsed ? '⬇ Show' : '⬆ Hide';
    };

    // Restore collapse state from cookie
    const wasCollapsed = getCookie(SELECT_COLLAPSE_KEY) === '1';
    wrapper.classList.toggle('collapsed', wasCollapsed);
    updateToggleButton(wasCollapsed);

    toggleBtn?.addEventListener('click', () => {
        const collapsed = wrapper.classList.toggle('collapsed');
        updateToggleButton(collapsed);
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

    checkboxes.forEach(cb => cb.addEventListener('change', () => {
        persist();
        recordAnalytics('set_toggle', { set: cb.value, checked: cb.checked });
    }));
    selectAllBtn?.addEventListener('click', () => {
        checkboxes.forEach(cb => cb.checked = true);
        persist();
        recordAnalytics('sets_select_all', { total: checkboxes.length });
    });
    deselectAllBtn?.addEventListener('click', () => {
        checkboxes.forEach(cb => cb.checked = false);
        persist();
        recordAnalytics('sets_deselect_all', { total: checkboxes.length });
    });
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
    selMethod?.addEventListener('change', () => {
        toggle();
        recordAnalytics('p1_selection_mode', { mode: selMethod.value });
    });
    toggle(); // Initial state
}

function setupModeControls() {
    const modePanel = qs('#mode-settings-panel');
    const modeToggleBtn = qs('#show-mode-settings-btn');
    const modeHelpBtn = qs('#matchup-mode-help-btn');
    const advBtn = qs('#advanced-mode-toggle');
    const advHelpBtn = qs('#advanced-help-btn');
    const customBlock = qs('#custom-mode-settings');
    const fairnessInput = qs('#fairness_weight');

    // Matchup Mode panel toggle (default hidden)
    if (modePanel && modeToggleBtn) {
        // Ensure it starts collapsed
        modePanel.classList.add('collapsed');
        modeToggleBtn.setAttribute('aria-expanded', 'false');
        
        modeToggleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const isCollapsed = modePanel.classList.contains('collapsed');
            if (isCollapsed) {
                modePanel.classList.remove('collapsed');
                modeToggleBtn.setAttribute('aria-expanded', 'true');
                modeToggleBtn.textContent = '⬆ Hide';
                // Show the matchup mode help modal when opening
                showMatchupModeHelpOnce();
            } else {
                modePanel.classList.add('collapsed');
                modeToggleBtn.setAttribute('aria-expanded', 'false');
                modeToggleBtn.textContent = '⬇ Show';
            }
        });
    }

    // Matchup Mode help button (always shows the modal without localStorage lock)
    if (modeHelpBtn) {
        modeHelpBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const modal = qs('#matchup-mode-help-modal');
            if (modal) {
                modal.classList.remove('hidden');
            }
        });
    }

    // Advanced (custom weight) toggle
    if (advBtn && customBlock) {
        // If a custom weight already exists (POST back), show it
        if (fairnessInput && fairnessInput.value.trim() !== '') {
            customBlock.classList.remove('collapsed');
        }

        advBtn.addEventListener('click', (e) => {
            e.preventDefault();
            customBlock.classList.toggle('collapsed');
            // Show the advanced mode help modal when clicking Advanced
            showAdvancedModeHelpOnce();
        });
    }

    // Advanced help button (always shows the modal without localStorage lock)
    if (advHelpBtn) {
        advHelpBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const modal = qs('#advanced-mode-help-modal');
            if (modal) {
                modal.classList.remove('hidden');
            }
        });
    }
}

/**
 * Set up all modal close handlers. This is called once during initialization
 * to ensure all modal close buttons work regardless of how the modal was opened.
 */
function setupModalCloseHandlers() {
    // Intro modal close handler
    const introModal = qs('#intro-modal');
    const introClose = qs('#intro-modal-close');
    if (introModal && introClose) {
        introClose.addEventListener('click', () => {
            introModal.classList.add('hidden');
            try {
                localStorage.setItem(INTRO_SEEN_KEY, '1');
            } catch (e) {
                // ignore storage errors
            }
        });
    }

    // Matchup mode help modal close handler
    const matchupModeHelpModal = qs('#matchup-mode-help-modal');
    const matchupModeHelpClose = qs('#matchup-mode-help-close');
    if (matchupModeHelpModal && matchupModeHelpClose) {
        matchupModeHelpClose.addEventListener('click', () => {
            matchupModeHelpModal.classList.add('hidden');
            try {
                localStorage.setItem(MATCHUP_MODE_HELP_SEEN_KEY, '1');
            } catch (e) {
                // ignore storage errors
            }
        });
    }

    // Advanced mode help modal close handler
    const advancedModeHelpModal = qs('#advanced-mode-help-modal');
    const advancedModeHelpClose = qs('#advanced-mode-help-close');
    if (advancedModeHelpModal && advancedModeHelpClose) {
        advancedModeHelpClose.addEventListener('click', () => {
            advancedModeHelpModal.classList.add('hidden');
            try {
                localStorage.setItem(ADVANCED_MODE_HELP_SEEN_KEY, '1');
            } catch (e) {
                // ignore storage errors
            }
        });
    }
}

function setupIntroModal() {
    const introModal = qs('#intro-modal');
    if (!introModal) return;

    // Wire up intro help button (always shows the modal without localStorage lock)
    const introHelpBtn = qs('#intro-help-btn');
    if (introHelpBtn && !introHelpBtn.dataset.clickHandlerSetup) {
        introHelpBtn.addEventListener('click', (e) => {
            e.preventDefault();
            introModal.classList.remove('hidden');
        });
        introHelpBtn.dataset.clickHandlerSetup = '1';
    }

    // Only show once per browser (using localStorage)
    if (window.localStorage && localStorage.getItem(INTRO_SEEN_KEY) === '1') {
        return;
    }

    introModal.classList.remove('hidden');
}

function setupAnalyticsListeners() {
    const generateBtn = qs('#generate-matchup-btn');
    generateBtn?.addEventListener('click', () => {
        recordAnalytics('generate_matchup', {
            locked_p1: !!qs('#current_locked_p1_id')?.value,
            locked_opp: !!qs('#current_locked_opp_id')?.value
        });
    });

    qsa('input[name="mode"]').forEach(r => {
        r.addEventListener('change', () => recordAnalytics('mode_change', { mode: r.value }));
    });

    const fairnessInput = qs('#fairness_weight');
    fairnessInput?.addEventListener('change', () => {
        recordAnalytics('fairness_weight_set', { value: fairnessInput.value });
    });

    const p1DirectSelect = qs('#p1_chosen_fighter');
    p1DirectSelect?.addEventListener('change', () => {
        recordAnalytics('p1_direct_choice', { fighter_id: p1DirectSelect.value });
    });

    qsa('input[name="p1_playstyles"], input[name="opp_playstyles"]').forEach(cb => {
        cb.addEventListener('change', () => {
            const group = cb.name.startsWith('p1') ? 'p1' : 'opp';
            recordAnalytics('playstyle_pref', { player: group, style: cb.value, checked: cb.checked });
        });
    });

    const p1Range = qs('#p1_range');
    p1Range?.addEventListener('change', () => recordAnalytics('range_pref', { player: 'p1', range: p1Range.value }));
    const oppRange = qs('#opp_range');
    oppRange?.addEventListener('change', () => recordAnalytics('range_pref', { player: 'opp', range: oppRange.value }));
}

function showMatchupModeHelpOnce() {
    const modal = qs('#matchup-mode-help-modal');
    if (!modal) return;

    if (window.localStorage && localStorage.getItem(MATCHUP_MODE_HELP_SEEN_KEY) === '1') {
        return;
    }

    modal.classList.remove('hidden');
}

function showAdvancedModeHelpOnce() {
    const modal = qs('#advanced-mode-help-modal');
    if (!modal) return;

    if (window.localStorage && localStorage.getItem(ADVANCED_MODE_HELP_SEEN_KEY) === '1') {
        return;
    }

    modal.classList.remove('hidden');
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

    recordAnalytics('alternative_promoted', {
        player,
        from_fighter: extractFighterIdFromCard(altCard),
        to_fighter: extractFighterIdFromCard(mainCard)
    });

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
        recordAnalytics('fighter_unlocked', { player, fighter_id: fid });
    } else {                              // --- LOCK ---
        btn.dataset.locked = 'true';
        hidden.value = fid;
        btn.classList.replace('btn-lock', 'btn-unlock');
        btn.textContent = '🔓 Fighter Locked';
        recordAnalytics('fighter_locked', { player, fighter_id: fid });
    }
    // Refresh win percentages after lock state changes (main matchup may change)
    try { updateAllWinPercentages(); } catch (e) { /* graceful fallback */ }
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
        const v = WIN_MATRIX[fighterId][opponentId];
        // Some entries use -2 (sentinel) or other negative values to mean "unknown".
        if (typeof v === 'number' && v >= 0 && v <= 100) return v;
    }
    
    // Check B vs A (and invert)
    if (WIN_MATRIX[opponentId] && WIN_MATRIX[opponentId][fighterId] !== undefined) {
        const v2 = WIN_MATRIX[opponentId][fighterId];
        if (typeof v2 === 'number' && v2 >= 0 && v2 <= 100) return 100 - v2;
    }

    return null; // Unknown
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

    if (winRate === null || isNaN(winRate)) {
        return { percentage: 'N/A', opponent_name: opponentName };
    }
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
