/* ==============================================================
   GLOBAL UI HELPERS
================================================================*/
function qs(selector, scope = document) { return scope.querySelector(selector); }
function qsa(selector, scope = document) { return [...scope.querySelectorAll(selector)]; }

function getCookie(name) {
    const match = document.cookie.split('; ').find(row => row.startsWith(name + '='));
    return match ? decodeURIComponent(match.split('=')[1]) : null;
}

function setCookie(name, value, days) {
    let expires = '';
    if (days) {
        const date = new Date(Date.now() + days * 24 * 60 * 60 * 1000);
        expires = '; expires=' + date.toUTCString();
    }
    document.cookie = name + '=' + encodeURIComponent(value) + expires + '; path=/';
}

/* ==============================================================
   EVENT LISTENERS
================================================================*/
document.addEventListener('DOMContentLoaded', () => {
    // Setup for UI components that are always present
    setupSetSelection();
    setupPlaystyleToggles();
    setupP1SelectionToggle();

    // Setup for dynamically generated result cards
    setupResultCardActions();
});


/* ==============================================================
   SET-SELECTION
================================================================*/
function setupSetSelection() {
    const setSelectionWrapper = qs('.set-selection');
    if (!setSelectionWrapper) return;

    const setToggleBtn = qs('#toggle-set-selection-btn');
    const LOCAL_KEY_COLLAPSED = 'unmatchedChooserSetSelectionCollapsed';
    const selectAllSetsButton = qs('#select-all-sets-btn');
    const deselectAllSetsButton = qs('#deselect-all-sets-btn');
    const setCheckboxes = qsa('#set-checkboxes input[type="checkbox"]');
    const COOKIE_KEY = 'owned_sets';

    // Load any saved sets from cookie and apply them
    const cookieVal = getCookie(COOKIE_KEY);
    if (cookieVal) {
        let sets = [];
        try { sets = JSON.parse(cookieVal); } catch (e) { sets = cookieVal.split('|'); }
        setCheckboxes.forEach(cb => { cb.checked = sets.includes(cb.value); });
    }

    function saveOwnedSetsToCookie() {
        const selected = setCheckboxes.filter(cb => cb.checked).map(cb => cb.value);
        setCookie(COOKIE_KEY, JSON.stringify(selected), 365);
    }

    if (localStorage.getItem(LOCAL_KEY_COLLAPSED) === 'true') {
        setSelectionWrapper.classList.add('collapsed');
        setToggleBtn.setAttribute('aria-expanded', 'false');
    } else {
        setSelectionWrapper.classList.remove('collapsed');
        setToggleBtn.setAttribute('aria-expanded', 'true');
    }

    setToggleBtn?.addEventListener('click', () => {
        const collapsed = setSelectionWrapper.classList.toggle('collapsed');
        setToggleBtn.setAttribute('aria-expanded', String(!collapsed));
        localStorage.setItem(LOCAL_KEY_COLLAPSED, String(collapsed));
    });

    selectAllSetsButton?.addEventListener('click', () => {
        setCheckboxes.forEach(cb => cb.checked = true);
        saveOwnedSetsToCookie();
    });
    deselectAllSetsButton?.addEventListener('click', () => {
        setCheckboxes.forEach(cb => cb.checked = false);
        saveOwnedSetsToCookie();
    });

    setCheckboxes.forEach(cb => cb.addEventListener('change', saveOwnedSetsToCookie));
}


/* ==============================================================
   PLAY-STYLE COLLAPSIBLE PANELS
================================================================*/
function setupPlaystyleToggles() {
    qsa('.toggle-playstyle-btn').forEach(btn => {
        const targetId = btn.dataset.target;
        const options = qs(`#${targetId}`);
        if (!options) return;

        // Set initial state from class
        const isCollapsed = options.classList.contains('collapsed');
        btn.setAttribute('aria-expanded', String(!isCollapsed));

        btn.addEventListener('click', () => {
            const collapsed = options.classList.toggle('collapsed');
            btn.setAttribute('aria-expanded', String(!collapsed));
        });
    });
}


/* ==============================================================
   PLAYER 1 SELECTION METHOD TOGGLE
================================================================*/
function setupP1SelectionToggle() {
    const p1SelectionMethod = qs('#p1_selection_method');
    const p1DirectChoiceSection = qs('#p1-direct-choice-section');
    const p1PreferencesSection = qs('#p1-preferences-section');
    const opponentTopDummy = qs('#opponent-controls .top-control-wrapper');


    function toggleP1Mode() {
        if (!p1SelectionMethod || !p1DirectChoiceSection || !p1PreferencesSection || !opponentTopDummy) {
            return;
        }

        if (p1SelectionMethod.value === 'direct_choice') {
            p1DirectChoiceSection.style.display = 'block';
            p1PreferencesSection.style.display = 'none';
            opponentTopDummy.classList.add('hidden');
        } else { // 'suggest'
            p1DirectChoiceSection.style.display = 'none';
            p1PreferencesSection.style.display = 'grid';
            opponentTopDummy.classList.remove('hidden');
        }
    }

    p1SelectionMethod?.addEventListener('change', toggleP1Mode);
    toggleP1Mode(); // Run on page load
}

/* ==============================================================
   HANDLE DYNAMIC RESULT CARD ACTIONS
================================================================*/
function setupResultCardActions() {
    const resultsArea = qs('#results-display-area');
    if (!resultsArea) return;

    resultsArea.addEventListener('click', (e) => {
        // Check if a "Select for Matchup" button was clicked
        if (e.target.matches('.select-alternative-btn')) {
            const button = e.target;
            const fighterId = button.dataset.fighterId;
            const playerPrefix = button.dataset.playerPrefix;
            const form = qs('#fighter-chooser-form');

            if (!fighterId || !playerPrefix || !form) return;
            
            // Create a hidden input to tell the backend which fighter to lock
            const actionInput = document.createElement('input');
            actionInput.type = 'hidden';
            actionInput.name = 'action';
            actionInput.value = `lock_${playerPrefix}:${fighterId}`;
            form.appendChild(actionInput);

            // Submit the form to regenerate the matchup with the new selection
            form.submit();
        }
        
        // Note: The regular Lock/Unlock buttons have type="submit", so they
        // trigger a form submission automatically without needing JS.
    });
}