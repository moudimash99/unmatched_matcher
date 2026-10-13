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
const PLAYSTYLE_HELP_SEEN_KEY = 'ufc_playstyle_help_seen';
const THEME_FILTER_HELP_SEEN_KEY = 'ufc_theme_filter_help_seen';

/*************************** ANALYTICS & CONSENT ***************************/
let analyticsEnabled = false;
let sessionMatchupCount = 0;

function enableAnalytics() {
    analyticsEnabled = true;
    window.ufcAnalyticsEvents = window.ufcAnalyticsEvents || [];
    if (typeof gtag === 'function') {
        gtag('consent', 'update', { analytics_storage: 'granted' });
        gtag('event', 'page_view');
    }
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
    setupPlaystyleHelpButtons();
    setupP1SelectionToggle();
    setupModeControls();
    setupThemeChips();
    setupModalCloseHandlers(); // Set up all modal close handlers first
    setupIntroModal();
    setupAnalyticsListeners();
    annotateLockButtons();
    setupResultCardActions();
    setupShareButton();
    setupExplanations();
    updateAllWinPercentages();  // also draws the map panel
    renderMapPanel();
    trackMatchupResult();
});

function setupThemeChips() {
    const panel = qs('#theme-filter-panel');
    const toggleBtn = qs('#toggle-theme-filter-btn');

    // Collapse/expand toggle — mirrors Matchup Mode behaviour
    if (panel && toggleBtn) {
        // Ensure it starts collapsed (also applied via HTML class)
        panel.classList.add('collapsed');
        toggleBtn.setAttribute('aria-expanded', 'false');

        // If a theme chip is already checked (POST back) expand the panel so the state is visible
        const anyChecked = qsa('.theme-chip input[type="checkbox"]:checked').length > 0;
        if (anyChecked) {
            panel.classList.remove('collapsed');
            toggleBtn.setAttribute('aria-expanded', 'true');
            toggleBtn.textContent = '⬆ Hide';
        }

        toggleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const isCollapsed = panel.classList.contains('collapsed');
            if (isCollapsed) {
                panel.classList.remove('collapsed');
                toggleBtn.setAttribute('aria-expanded', 'true');
                toggleBtn.textContent = '⬆ Hide';
                // Show help popup the first time the panel is opened
                showThemeFilterHelpOnce();
                recordAnalytics('panel_toggle', { panel: 'theme_filter', expanded: true });
            } else {
                panel.classList.add('collapsed');
                toggleBtn.setAttribute('aria-expanded', 'false');
                toggleBtn.textContent = '⬇ Show';
                recordAnalytics('panel_toggle', { panel: 'theme_filter', expanded: false });
            }
        });
    }

    const chips = qsa('.theme-chip');
    chips.forEach(chip => {
        const cb = chip.querySelector('input[type="checkbox"]');
        if (!cb) return;
        // Sync active class on change
        cb.addEventListener('change', () => {
            chip.classList.toggle('active', cb.checked);
        });
    });

    // Wire up theme filter help button (always shows the modal)
    const themeHelpBtn = qs('#theme-filter-help-btn');
    if (themeHelpBtn) {
        themeHelpBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const modal = qs('#theme-filter-help-modal');
            if (modal) {
                modal.classList.remove('hidden');
                recordAnalytics('modal_view', { modal: 'theme_filter_help' });
            }
        });
    }
}

/*************************** UI SETUP FUNCTIONS  ***************************/
function setupSetSelection() {
    const wrapper = qs('.set-selection');
    if (!wrapper) return;

    const toggleBtn = qs('#toggle-set-selection-btn');
    const SELECT_COLLAPSE_KEY = 'ufs_sets_collapsed';
    const ALL_SETS_KEY = 'ufs_owned_sets';
    const DEFAULT_SETS_KEY = 'ufs_default_owned_sets';
    const selectAllBtn = qs('#select-all-sets-btn');
    const deselectAllBtn = qs('#deselect-all-sets-btn');
    const loadDefaultBtn = qs('#load-default-sets-btn');
    const checkboxes = qsa('#set-checkboxes input[type="checkbox"]');
    const getCheckedSetValues = () => checkboxes
        .filter(cb => cb.checked)
        .map(cb => cb.value);
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
        recordAnalytics('panel_toggle', { panel: 'owned_sets', expanded: !collapsed });
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
        setCookie(ALL_SETS_KEY, JSON.stringify(getCheckedSetValues()));
    };

    const getSavedDefaultSets = () => {
        const storedDefault = getCookie(DEFAULT_SETS_KEY);
        if (!storedDefault) return [];
        try {
            const parsed = JSON.parse(storedDefault);
            return Array.isArray(parsed) ? parsed : [];
        } catch (e) {
            console.error("Could not parse default owned sets cookie:", e);
            return [];
        }
    };

    // DEFAULT_SETS_KEY is the collection saved on /collection
    const updateDefaultButtons = () => {
        if (!loadDefaultBtn) return;
        const none = getSavedDefaultSets().length === 0;
        loadDefaultBtn.disabled = none;
        loadDefaultBtn.title = none ? 'No collection saved yet: set it up on the My collection page'
            : 'Tick exactly the sets saved on the My collection page';
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

    loadDefaultBtn?.addEventListener('click', () => {
        const defaultSetValues = new Set(getSavedDefaultSets());
        if (!defaultSetValues.size) return;
        checkboxes.forEach(cb => {
            cb.checked = defaultSetValues.has(cb.value);
        });
        persist();
        recordAnalytics('collection_loaded', { total: defaultSetValues.size });
    });

    updateDefaultButtons();
}

function setupPlaystyleToggles() {
    qsa('.toggle-playstyle-btn').forEach(btn => {
        const target = qs(`#${btn.dataset.target}`);
        if (!target) return;
        btn.setAttribute('aria-expanded', String(!target.classList.contains('collapsed')));
        btn.addEventListener('click', () => {
            const collapsed = target.classList.toggle('collapsed');
            btn.setAttribute('aria-expanded', String(!collapsed));
            if (!collapsed) {
                showPlaystyleHelpOnce();
            }
        });
    });
}

function showPlaystyleHelpOnce() {
    const modal = qs('#playstyle-help-modal');
    if (!modal) return;
    if (window.localStorage && localStorage.getItem(PLAYSTYLE_HELP_SEEN_KEY) === '1') return;
    modal.classList.remove('hidden');
    recordAnalytics('modal_view', { modal: 'playstyle_help', first_time: true });
}

function setupPlaystyleHelpButtons() {
    const modal = qs('#playstyle-help-modal');
    if (!modal) return;
    qsa('.playstyle-help-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            modal.classList.remove('hidden');
            recordAnalytics('modal_view', { modal: 'playstyle_help' });
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
                recordAnalytics('panel_toggle', { panel: 'matchup_mode', expanded: true });
            } else {
                modePanel.classList.add('collapsed');
                modeToggleBtn.setAttribute('aria-expanded', 'false');
                modeToggleBtn.textContent = '⬇ Show';
                recordAnalytics('panel_toggle', { panel: 'matchup_mode', expanded: false });
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
                recordAnalytics('modal_view', { modal: 'matchup_mode_help' });
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
                recordAnalytics('modal_view', { modal: 'advanced_mode_help' });
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

    // Playstyle help modal close handler
    const playstyleHelpModal = qs('#playstyle-help-modal');
    const playstyleHelpClose = qs('#playstyle-help-close');
    if (playstyleHelpModal && playstyleHelpClose) {
        playstyleHelpClose.addEventListener('click', () => {
            playstyleHelpModal.classList.add('hidden');
            try { localStorage.setItem(PLAYSTYLE_HELP_SEEN_KEY, '1'); } catch (e) { /* ignore */ }
        });
        // Also close when clicking the overlay backdrop
        playstyleHelpModal.addEventListener('click', (e) => {
            if (e.target === playstyleHelpModal) {
                playstyleHelpModal.classList.add('hidden');
                try { localStorage.setItem(PLAYSTYLE_HELP_SEEN_KEY, '1'); } catch (e) { /* ignore */ }
            }
        });
    }
    // Theme filter help modal close handler
    const themeFilterHelpModal = qs('#theme-filter-help-modal');
    const themeFilterHelpClose = qs('#theme-filter-help-close');
    if (themeFilterHelpModal && themeFilterHelpClose) {
        themeFilterHelpClose.addEventListener('click', () => {
            themeFilterHelpModal.classList.add('hidden');
            try {
                localStorage.setItem(THEME_FILTER_HELP_SEEN_KEY, '1');
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
            recordAnalytics('modal_view', { modal: 'intro' });
        });
        introHelpBtn.dataset.clickHandlerSetup = '1';
    }

    // Only show once per browser (using localStorage)
    if (window.localStorage && localStorage.getItem(INTRO_SEEN_KEY) === '1') {
        return;
    }

    introModal.classList.remove('hidden');
    recordAnalytics('modal_view', { modal: 'intro', first_time: true });
}

function setupAnalyticsListeners() {
    const generateBtn = qs('#generate-matchup-btn');
    generateBtn?.addEventListener('click', () => {
        sessionMatchupCount++;
        recordAnalytics('generate_matchup', {
            locked_p1: !!qs('#current_locked_p1_id')?.value,
            locked_opp: !!qs('#current_locked_opp_id')?.value,
            mode: qs('input[name="mode"]:checked')?.value || 'discovery',
            p1_selection_method: qs('#p1_selection_method')?.value || 'suggest',
            owned_sets_count: qsa('#set-checkboxes input[type="checkbox"]:checked').length,
            session_matchup_number: sessionMatchupCount
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

function trackMatchupResult() {
    const p1Card = qs('#p1-main-suggestion');
    const oppCard = qs('#opp-main-suggestion');
    if (!p1Card || !oppCard) return;

    const p1Id = extractFighterIdFromCard(p1Card);
    const oppId = extractFighterIdFromCard(oppCard);
    const p1Info = ALL_FIGHTERS_JS.find(f => f.id === p1Id);
    const oppInfo = ALL_FIGHTERS_JS.find(f => f.id === oppId);
    const entry = MATCHUPS[p1Id] && MATCHUPS[p1Id][oppId];

    recordAnalytics('matchup_result_shown', {
        p1_fighter_id: p1Id,
        p1_fighter_name: p1Info?.name || p1Id,
        opp_fighter_id: oppId,
        opp_fighter_name: oppInfo?.name || oppId,
        win_rate: entry ? entry[0] : null,
        games_played: entry ? entry[1] : null,
        p1_alternatives_count: qsa('[data-player-prefix="p1"].alternative-suggestion').length,
        opp_alternatives_count: qsa('[data-player-prefix="opp"].alternative-suggestion').length
    });
}

function showMatchupModeHelpOnce() {
    const modal = qs('#matchup-mode-help-modal');
    if (!modal) return;

    if (window.localStorage && localStorage.getItem(MATCHUP_MODE_HELP_SEEN_KEY) === '1') {
        return;
    }

    modal.classList.remove('hidden');
    recordAnalytics('modal_view', { modal: 'matchup_mode_help', first_time: true });
}

function showAdvancedModeHelpOnce() {
    const modal = qs('#advanced-mode-help-modal');
    if (!modal) return;

    if (window.localStorage && localStorage.getItem(ADVANCED_MODE_HELP_SEEN_KEY) === '1') {
        return;
    }

    modal.classList.remove('hidden');
    recordAnalytics('modal_view', { modal: 'advanced_mode_help', first_time: true });
}

function showThemeFilterHelpOnce() {
    const modal = qs('#theme-filter-help-modal');
    if (!modal) return;

    if (window.localStorage && localStorage.getItem(THEME_FILTER_HELP_SEEN_KEY) === '1') {
        return;
    }

    modal.classList.remove('hidden');
    recordAnalytics('modal_view', { modal: 'theme_filter_help', first_time: true });
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
    renderMapPanel();
}

/**
 * Updates the win percentage text for a single card.
 * @param {HTMLElement} card - The fighter card to update.
 * @param {string} opponentId - The ID of the fighter it is facing.
 */
function updateCardWinPct(card, opponentId) {
    const cardFighterId = extractFighterIdFromCard(card);
    const winHtmlElement = card.querySelector('.win-percentage-text');
    if (winHtmlElement) {
        winHtmlElement.innerHTML = winLineHTML(cardFighterId, opponentId);
    }
}

/**
 * Builds the "Win vs X" line from the server-computed MATCHUPS estimates.
 * Mirrors the win-percentage block in index.html.
 * @param {string} fighterId - The ID of the first fighter.
 * @param {string} opponentId - The ID of the fighter they face.
 * @returns {string} HTML for the win line.
 */
function winLineHTML(fighterId, opponentId) {
    const byId = id => ALL_FIGHTERS_JS.find(f => f.id === id);
    const fighter = byId(fighterId);
    const opponent = byId(opponentId);
    const entry = MATCHUPS[fighterId] && MATCHUPS[fighterId][opponentId];
    if (!fighter || !opponent || !entry) return '';

    const clubUrl = `${CLUB_MATCHUP_URL}?h1=${fighter.club_key}&h2=${opponent.club_key}`;
    const clubLink = `<a class="club-link" href="${clubUrl}" target="_blank" rel="noopener" title="See this matchup on The Unmatched Club">stats ↗</a>`;
    const mapKey = chosenMap();
    const onMap = mapWinPct(fighterId, opponentId, mapKey);
    if (onMap) {
        const [mpct, mgames, mlow] = onMap;
        return `<strong>Win vs ${opponent.name} on ${escapeHTML(MAP_INFO[mapKey].name)}:</strong> ${mlow ? '~' : ''}${mpct}% ` +
            `${mapNote(mgames, mlow, `map|${fighterId}|${opponentId}|${mapKey}`)} ${clubLink}`;
    }

    const [pct, games] = entry;
    const low = games < FULL_CONFIDENCE_GAMES;
    const explain = explainData('base', fighterId, opponentId) ? `base|${fighterId}|${opponentId}` : '';
    const value = `${low ? '~' : ''}${pct}% ${gamesNote(games, low, explain)}`;
    return `<strong>Win vs ${opponent.name}:</strong> ${value} ${clubLink}`;
}

/*************************** MAPS & TURN ORDER  ***************************/
const escapeHTML = s => String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

function noteHTML(text, low, explain) {
    const cls = `games-note${low ? ' low-data' : ''}`;
    return explain
        ? `<button type="button" class="${cls} explain-btn" data-explain="${escapeHTML(explain)}" title="How is this worked out?">· ${text} <span aria-hidden="true">ⓘ</span></button>`
        : `<span class="${cls}">· ${text}</span>`;
}

function gamesNote(games, low, explain) {
    const text = games === 0 ? 'estimate, no games yet'
        : `${low ? 'estimate, ' : ''}${games.toLocaleString('en-US')} game${games === 1 ? '' : 's'}`;
    return noteHTML(text, low, explain);
}

// A note for a pairing's record on a map; with no games there, it's built from each fighter's record on the map
function mapNote(games, low, explain) {
    return games ? gamesNote(games, low, explain) : noteHTML("estimate, from each fighter's record here", true, explain);
}

// The map chosen in the picker (a key of MAP_INFO), kept in the form's hidden "map" input
function chosenMap() {
    const input = qs('#chosen_map');
    const key = input ? input.value : '';
    return typeof MAP_INFO !== 'undefined' && MAP_INFO[key] ? key : '';
}

function setChosenMap(key) {
    const input = qs('#chosen_map');
    if (input) input.value = key || '';
    if (key) recordAnalytics('map_chosen', { map: key });
    updateAllWinPercentages();
}

/**
 * [win %, games, low data] for a fighter vs an opponent on a map, from whichever MAP_PANELS
 * pairing holds them (P1 cards are keyed "p1|opp"; opponent cards are read from the other side).
 */
function mapWinPct(fighterId, opponentId, mapKey) {
    if (typeof MAP_PANELS === 'undefined' || !mapKey) return null;
    const direct = MAP_PANELS[`${fighterId}|${opponentId}`];
    if (direct && direct.by_map[mapKey]) return direct.by_map[mapKey];
    const reverse = MAP_PANELS[`${opponentId}|${fighterId}`];
    if (reverse && reverse.by_map[mapKey]) {
        const [pct, games, low] = reverse.by_map[mapKey];
        return [100 - pct, games, low];
    }
    return null;
}

function mapThumbHTML(key, cls) {
    const info = MAP_INFO[key];
    return info && info.thumb
        ? `<img class="${cls}" src="${STATIC_URL}${escapeHTML(info.thumb)}" alt="${escapeHTML(info.name)} map" loading="lazy">`
        : `<div class="${cls} map-thumb-missing" aria-hidden="true">🗺️</div>`;
}

// rows hold P1's win %; flip shows the opponent's side instead
function mapListHTML(title, rows, fighterName, flip = false, pair = '') {
    if (!rows.length) return '';
    const note = r => mapNote(r.games, r.low, pair && `map|${pair}|${r.key}`);
    const items = rows.map(r =>
        `<li><button type="button" class="map-name map-pick" data-map="${escapeHTML(r.key)}" title="${escapeHTML(r.set || '')}">${escapeHTML(r.name)}</button> ` +
        `${escapeHTML(fighterName)} ${r.low ? '~' : ''}${flip ? 100 - r.pct : r.pct}% ${note(r)}</li>`).join('');
    return `<div class="map-list"><h5>${escapeHTML(title)}</h5><ul>${items}</ul></div>`;
}

function fighterSets(f) {
    return [].concat(f.set || [], f.sets || []);
}

function suggestedMapsHTML(rows, a, b, chosen) {
    if (!rows.length) return '';
    const homeOf = r => {
        const owners = [a, b].filter(f => fighterSets(f).includes(r.set)).map(f => f.name);
        return owners.length ? `<span class="map-home">${escapeHTML(owners.join(' & '))}'s box</span>` : '';
    };
    const tiles = rows.map(r =>
        `<li><button type="button" class="map-tile map-pick${r.key === chosen ? ' chosen' : ''}" data-map="${escapeHTML(r.key)}" aria-pressed="${r.key === chosen}">` +
        mapThumbHTML(r.key, 'map-thumb') +
        `<span class="map-tile-name">${escapeHTML(r.name)}</span>` +
        `<span class="map-tile-pct">${escapeHTML(a.name)} ${r.low ? '~' : ''}${r.pct}%</span>` +
        homeOf(r) + `</button></li>`).join('');
    return `<div class="map-suggested"><h5>Suggested maps <span class="games-note">· fairest first, ${escapeHTML(a.name)}'s win %</span></h5><ul class="map-tiles">${tiles}</ul></div>`;
}

function chosenMapHTML(panel, a, b, chosen) {
    const keys = Object.keys(panel.by_map).sort((x, y) => MAP_INFO[x].name.localeCompare(MAP_INFO[y].name));
    const options = keys.map(k =>
        `<option value="${escapeHTML(k)}"${k === chosen ? ' selected' : ''}>${escapeHTML(MAP_INFO[k].name)} (${escapeHTML(a.name)} ${panel.by_map[k][0]}%)</option>`).join('');
    let detail = '';
    if (chosen && panel.by_map[chosen]) {
        const info = MAP_INFO[chosen];
        const [pct, games, low] = panel.by_map[chosen];
        const layout = [info.size && `${info.size.toUpperCase()} map`, info.zones && `${info.zones} zones`,
                        info.spaces && `${info.spaces} spaces`].filter(Boolean).join(' · ');
        detail = `<div class="map-chosen">${mapThumbHTML(chosen, 'map-chosen-img')}<div>` +
            `<strong>${escapeHTML(info.name)}</strong> <span class="games-note">${escapeHTML(info.set || '')}</span>` +
            (layout ? `<div class="games-note">${escapeHTML(layout)}</div>` : '') +
            `<div>${escapeHTML(a.name)} ${low ? '~' : ''}${pct}% · ${escapeHTML(b.name)} ${low ? '~' : ''}${100 - pct}% ` +
            `${mapNote(games, low, `map|${a.id}|${b.id}|${chosen}`)}</div></div></div>`;
    }
    return `<div class="map-choice"><label for="map-choice-select"><strong>Map (optional):</strong></label> ` +
        `<select id="map-choice-select"><option value="">No map chosen</option>${options}</select>${detail}</div>`;
}

/**
 * Shows the map picker, suggested maps, first-player and closeness stats for the current main
 * matchup (server-computed in MAP_PANELS for every P1 x opponent card pairing).
 */
function renderMapPanel() {
    const el = qs('#map-panel');
    if (!el || typeof MAP_PANELS === 'undefined') return;
    const p1 = extractFighterIdFromCard(qs('#p1-main-suggestion'));
    const opp = extractFighterIdFromCard(qs('#opp-main-suggestion'));
    const panel = MAP_PANELS[`${p1}|${opp}`];
    const byId = id => ALL_FIGHTERS_JS.find(f => f.id === id);
    const a = byId(p1), b = byId(opp);
    if (!panel || !a || !b) { el.innerHTML = ''; return; }
    const chosen = panel.by_map[chosenMap()] ? chosenMap() : '';

    const first = panel.first;
    let facts = `<li><strong>Going first:</strong> ${first.low ? '~' : ''}${first.pct}% win ${gamesNote(first.games, first.low, `first|${p1}|${opp}`)}</li>`;
    if (panel.closeness) {
        const c = panel.closeness;
        facts += `<li><strong>Winner ends on:</strong> ${c.low ? '~' : ''}${c.hp} HP on average ${gamesNote(c.games, c.low, `close|${p1}|${opp}`)}</li>`;
    }
    const lists = mapListHTML(`Maps that favor ${a.name}`, panel.favor_a, a.name, false, `${p1}|${opp}`) +
        mapListHTML(`Maps that favor ${b.name}`, panel.favor_b, b.name, true, `${p1}|${opp}`);
    el.innerHTML = `<h3>Maps &amp; turn order</h3>` +
        (Object.keys(panel.by_map).length ? chosenMapHTML(panel, a, b, chosen) : '') +
        suggestedMapsHTML(panel.suggested, a, b, chosen) +
        `<ul class="map-facts">${facts}</ul>` +
        (lists ? `<div class="map-lists">${lists}</div>` : '');

    const select = el.querySelector('#map-choice-select');
    if (select) select.addEventListener('change', () => setChosenMap(select.value));
    el.querySelectorAll('.map-pick').forEach(btn => btn.addEventListener('click', () =>
        setChosenMap(btn.dataset.map === chosenMap() ? '' : btn.dataset.map)));
}

/*************************** "HOW IS THIS WORKED OUT" POPUP  ***************************/
const pctText = v => `${Math.round(v)}%`;
const recordText = (wins, games) => `${wins}–${games - wins}`;
const gamesText = n => `${n.toLocaleString('en-US')} game${n === 1 ? '' : 's'}`;
const signedPts = v => `${v >= 0 ? '+' : '−'}${Math.abs(Math.round(v))} point${Math.abs(Math.round(v)) === 1 ? '' : 's'}`;
const fighterName = id => (ALL_FIGHTERS_JS.find(f => f.id === id) || { name: id }).name;

function trustText(games, conf, full) {
    if (games >= full) return `${gamesText(games)} is enough to trust the record as it is (we fully trust a record from ${full} games).`;
    return `With only ${gamesText(games)} it counts ${Math.round(conf * 100)}%; the other ${100 - Math.round(conf * 100)}% comes from the broader estimate. ` +
        `(A record is fully trusted from ${full} games; trust grows fast over the first few games, then slower.)`;
}

/**
 * The numbers behind an estimate, oriented so "a" is the fighter whose win % is shown.
 * Map explanations live on the "p1|opp" panel; an opponent card's view is the same data flipped.
 */
function explainData(kind, a, b, map) {
    if (kind === 'base') return (typeof MATCHUP_EXPLAIN !== 'undefined' && MATCHUP_EXPLAIN[`${a}|${b}`]) || null;
    if (typeof MAP_PANELS === 'undefined') return null;
    const direct = MAP_PANELS[`${a}|${b}`];
    const reverse = MAP_PANELS[`${b}|${a}`];
    if (kind === 'first' || kind === 'close') {
        const panel = direct || reverse;
        return panel ? panel.explain[kind === 'first' ? 'first' : 'closeness'] : null;
    }
    if (direct && direct.explain.maps[map]) return direct.explain.maps[map];
    const e = reverse && reverse.explain.maps[map];
    if (!e) return null;
    return { ...e, a: e.b, b: e.a, base: 100 - e.base, shift_a: -e.shift_b, shift_b: -e.shift_a,
             expected: 100 - e.expected, final: 100 - e.final, pair_wins: e.pair_games - e.pair_wins };
}

function explainBaseHTML(e, a, b) {
    const A = escapeHTML(fighterName(a)), B = escapeHTML(fighterName(b));
    const strength = e.a_overall == null || e.b_overall == null
        ? `We don't have overall records for both, so this starts from 50%.`
        : `${A} wins ${pctText(e.a_overall)} of all ${gamesText(e.a_total)} and ${B} wins ${pctText(e.b_overall)} of ${gamesText(e.b_total)}. ` +
          `Two fighters that strong would be expected to split about ${pctText(e.expected)}–${pctText(100 - e.expected)}.`;
    let steps;
    if (!e.games) {
        steps = `<li><strong>No recorded games</strong> between them, so the estimate comes only from how strong each fighter is overall.</li>` +
            `<li>${strength}</li>`;
    } else if (e.conf >= 1) {
        steps = `<li><strong>Recorded games:</strong> ${A} won ${pctText(e.observed)} of ${gamesText(e.games)} against ${B}.</li>` +
            `<li>${trustText(e.games, e.conf, e.full_games)}</li>`;
    } else {
        steps = `<li><strong>Recorded games:</strong> ${A} won ${pctText(e.observed)} of ${gamesText(e.games)} against ${B}.</li>` +
            `<li>${trustText(e.games, e.conf, e.full_games)}</li>` +
            `<li><strong>Broader estimate:</strong> ${strength}</li>` +
            `<li><strong>Blend:</strong> ${Math.round(e.conf * 100)}% × ${pctText(e.observed)} + ${100 - Math.round(e.conf * 100)}% × ${pctText(e.expected)} = <strong>${pctText(e.final)}</strong>.</li>`;
    }
    return `<h2>${A} vs ${B}: ${pctText(e.final)}</h2><p class="explain-sub">${A}'s chance to win, all maps combined.</p><ol class="explain-steps">${steps}</ol>` +
        `<p class="explain-source">Win rates from The Unmatched Club (Tabletop League and UnmatchedRu games).</p>`;
}

function explainSideText(side, name, isA) {
    if (!side.games) return `<strong>${name}</strong> has no recorded games on this map, so it doesn't move the number.`;
    const vs = side.all_maps == null ? '' : ` against ${pctText(side.all_maps)} across all ${gamesText(side.all_games)}`;
    let text = `<strong>${name} on this map: ${recordText(side.wins, side.games)}</strong> (${pctText(side.on_map)})${vs}.`;
    if (side.conf < 1) {
        text += ` Only ${gamesText(side.games)} here, so it counts ${Math.round(side.conf * 100)}% and is treated as ${pctText(side.blended)}.`;
    }
    const better = side.blended > side.all_maps;
    text += isA ? (better ? ` ${name} does better here than usual.` : ` ${name} does worse here than usual.`)
                : (better ? ` ${name} does better here than usual, which hurts the other side.` : ` ${name} does worse here than usual, which helps the other side.`);
    return text;
}

// Same clamp as the server (map_stats.py): 1% to 99%
const clampPct = v => Math.min(99, Math.max(1, v));
const odds = pct => clampPct(pct) / (100 - clampPct(pct));
const oddsText = v => v >= 10 ? v.toFixed(0) : v >= 1 ? v.toFixed(2) : v.toFixed(2);

/**
 * The "Together" step worked out by hand: percentages become odds (wins per loss), each fighter's
 * map record multiplies them, and the result is turned back into a percentage. This is the
 * log-odds math in map_stats.py, written as multiplying odds.
 */
function oddsMathHTML(e, A, B) {
    const factor = side => (side.games && side.all_maps != null) ? odds(side.blended) / odds(side.all_maps) : 1;
    const fa = factor(e.a), fb = factor(e.b);
    const start = odds(e.base), end = start * fa / fb;
    const sideLine = (side, name, f, verb) => side.games && side.all_maps != null
        ? `<li>${name}: ${pctText(side.blended)} on this map vs ${pctText(side.all_maps)} usually → odds ` +
          `${oddsText(odds(side.blended))} vs ${oddsText(odds(side.all_maps))} → <strong>${verb} ${f.toFixed(2)}</strong></li>`
        : `<li>${name}: no games on this map → ${verb} 1 (no change)</li>`;
    return `<details class="explain-math"><summary>Show the math</summary>` +
        `<p>Percentages are turned into <em>odds</em> (wins per loss), the map effects multiply the odds, then the odds are turned back into a percentage:</p>` +
        `<ol>` +
        `<li>Start: ${pctText(e.base)} → odds ${Math.round(clampPct(e.base))} ÷ ${100 - Math.round(clampPct(e.base))} = <strong>${oddsText(start)}</strong></li>` +
        sideLine(e.a, A, fa, '×') +
        sideLine(e.b, B, fb, '÷') +
        `<li>${oddsText(start)} × ${fa.toFixed(2)} ÷ ${fb.toFixed(2)} = <strong>${oddsText(end)}</strong></li>` +
        `<li>Back to a percentage: ${oddsText(end)} ÷ (1 + ${oddsText(end)}) = <strong>${pctText(100 * end / (1 + end))}</strong></li>` +
        `</ol>` +
        `<p class="explain-note">Why not just add the points? Take a map that turns a 50% matchup into 65%: ` +
        `it multiplies the odds by 1.86 (1 to 1 becomes 1.86 to 1). Adding its +15 points to a 90% matchup would give 105%, ` +
        `which is impossible. With odds, 90% is 9 to 1, × 1.86 is 16.7 to 1, which is 94%. ` +
        `So the same map edge moves a close matchup a lot and a lopsided one only a little.</p>` +
        `</details>`;
}

function explainMapHTML(e, a, b, map) {
    const A = escapeHTML(fighterName(a)), B = escapeHTML(fighterName(b));
    const M = escapeHTML(MAP_INFO[map] ? MAP_INFO[map].name : map);
    let steps = `<li><strong>Start from the overall matchup:</strong> ${A} wins ${pctText(e.base)} against ${B}, all maps combined. ` +
        `<button type="button" class="explain-link" data-explain="base|${a}|${b}">How is that worked out?</button></li>` +
        `<li>${explainSideText(e.a, A, true)} Effect on ${A}'s chance: <strong>${signedPts(e.shift_a)}</strong>.</li>` +
        `<li>${explainSideText(e.b, B, false)} Effect on ${A}'s chance: <strong>${signedPts(e.shift_b)}</strong>.</li>` +
        `<li><strong>Together:</strong> ${pctText(e.base)} → <strong>${pctText(e.expected)}</strong>.` +
        oddsMathHTML(e, A, B) + `</li>`;
    if (!e.pair_games) {
        steps += `<li><strong>${A} vs ${B} on ${M} itself:</strong> never recorded, so ${pctText(e.expected)} is the estimate.</li>`;
    } else {
        const own = 100 * e.pair_wins / e.pair_games;
        steps += `<li><strong>${A} vs ${B} on ${M} itself:</strong> ${A} is ${recordText(e.pair_wins, e.pair_games)} (${pctText(own)}). ` +
            `${trustText(e.pair_games, e.pair_conf, e.full_games)}` +
            (e.pair_conf >= 1 ? ` So the answer is <strong>${pctText(e.final)}</strong>.`
                : ` Blend: ${Math.round(e.pair_conf * 100)}% × ${pctText(own)} + ${100 - Math.round(e.pair_conf * 100)}% × ${pctText(e.expected)} = <strong>${pctText(e.final)}</strong>.`) + `</li>`;
    }
    return `<h2>${A} vs ${B} on ${M}: ${pctText(e.final)}</h2>` +
        `<p class="explain-sub">Most pairings have few or no games on any one map, so this mostly uses how each fighter does on the map against everyone.</p>` +
        `<ol class="explain-steps">${steps}</ol>` +
        `<p class="explain-source">Map records: every Tabletop League game, from each fighter's stats page.</p>`;
}

function explainFirstHTML(e, a, b) {
    const A = escapeHTML(fighterName(a)), B = escapeHTML(fighterName(b));
    let steps = `<li><strong>In general:</strong> whoever went first won ${pctText(e.overall)} of ${gamesText(e.overall_games)} in our sample of recent matches.</li>`;
    if (!e.games) {
        steps += `<li><strong>${A} vs ${B}:</strong> no games in the sample yet, so the general ${pctText(e.overall)} is used.</li>`;
    } else {
        const own = 100 * e.wins / e.games;
        steps += `<li><strong>${A} vs ${B}:</strong> the first player won ${e.wins} of ${gamesText(e.games)} (${pctText(own)}). ${trustText(e.games, e.conf, e.full_games)}` +
            (e.conf >= 1 ? '' : ` Blend: ${Math.round(e.conf * 100)}% × ${pctText(own)} + ${100 - Math.round(e.conf * 100)}% × ${pctText(e.overall)} = <strong>${pctText(e.final)}</strong>.`) + `</li>`;
    }
    return `<h2>Going first: ${pctText(e.final)} win</h2><p class="explain-sub">The chance that whoever takes the first turn wins, either fighter.</p>` +
        `<ol class="explain-steps">${steps}</ol>` +
        `<p class="explain-source">Turn order is only shown on individual Tabletop League match pages, so this comes from a smaller sample of recent matches.</p>`;
}

function explainCloseHTML(e, a, b) {
    const A = escapeHTML(fighterName(a)), B = escapeHTML(fighterName(b));
    const hp = v => `${Math.round(v * 10) / 10} HP`;
    let steps = `<li><strong>In general:</strong> the winner ends on ${hp(e.overall)} on average in our sample of recent matches.</li>`;
    if (!e.games) {
        steps += `<li><strong>${A} vs ${B}:</strong> no games in the sample yet, so the general ${hp(e.overall)} is used.</li>`;
    } else {
        steps += `<li><strong>${A} vs ${B}:</strong> the winner ended on ${hp(e.pair)} on average over ${gamesText(e.games)}. ${trustText(e.games, e.conf, e.full_games)}` +
            (e.conf >= 1 ? '' : ` Blend: ${Math.round(e.conf * 100)}% × ${hp(e.pair)} + ${100 - Math.round(e.conf * 100)}% × ${hp(e.overall)} = <strong>${hp(e.final)}</strong>.`) + `</li>`;
    }
    return `<h2>Winner ends on ${hp(e.final)}</h2><p class="explain-sub">How much health the winner has left: lower means closer games.</p>` +
        `<ol class="explain-steps">${steps}</ol>` +
        `<p class="explain-source">End health is only shown on individual Tabletop League match pages, so this comes from a smaller sample of recent matches.</p>`;
}

function openExplanation(spec) {
    const [kind, a, b, map] = spec.split('|');
    const e = explainData(kind, a, b, map);
    const modal = qs('#explain-modal');
    if (!e || !modal) return;
    const html = { base: explainBaseHTML, map: explainMapHTML, first: explainFirstHTML, close: explainCloseHTML }[kind](e, a, b, map);
    qs('#explain-body').innerHTML = html;
    modal.classList.remove('hidden');
    qs('#explain-close').focus();
    recordAnalytics('explanation_opened', { kind });
}

function setupExplanations() {
    const modal = qs('#explain-modal');
    if (!modal) return;
    document.addEventListener('click', ev => {
        const btn = ev.target.closest('[data-explain]');
        if (btn) { ev.preventDefault(); openExplanation(btn.dataset.explain); }
    });
    const close = () => modal.classList.add('hidden');
    qs('#explain-close').addEventListener('click', close);
    modal.addEventListener('click', ev => { if (ev.target === modal) close(); });
    document.addEventListener('keydown', ev => { if (ev.key === 'Escape' && !modal.classList.contains('hidden')) close(); });
}

/*************************** SHARE LINK  ***************************/
/**
 * Copies a link that reopens the current main matchup with the owned sets.
 */
function setupShareButton() {
    const btn = qs('#share-matchup-btn');
    if (!btn) return;
    const status = qs('#share-status');

    btn.addEventListener('click', async () => {
        const p1 = extractFighterIdFromCard(qs('#p1-main-suggestion'));
        const opp = extractFighterIdFromCard(qs('#opp-main-suggestion'));
        if (!p1 || !opp) return;

        const params = new URLSearchParams({ p1, opp });
        qsa('input[name="owned_sets"]:checked').forEach(cb => params.append('sets', cb.value));
        if (chosenMap()) params.set('map', chosenMap());
        const url = `${window.location.origin}${window.location.pathname}?${params}`;

        try {
            await navigator.clipboard.writeText(url);
            status.textContent = 'Link copied!';
        } catch (e) {
            // Clipboard can be blocked (e.g. non-HTTPS); show the link to copy by hand
            status.textContent = url;
        }
        recordAnalytics('matchup_shared', { p1, opp });
    });
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
