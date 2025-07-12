/* ==============================================================
   GLOBAL UI HELPERS
================================================================*/
function qs(selector, scope = document) { return scope.querySelector(selector); }
function qsa(selector, scope = document) { return [...scope.querySelectorAll(selector)]; }

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

    selectAllSetsButton?.addEventListener('click', () => setCheckboxes.forEach(cb => cb.checked = true));
    deselectAllSetsButton?.addEventListener('click', () => setCheckboxes.forEach(cb => cb.checked = false));
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
        const btn = e.target.closest('button');
        if (!btn) return;

        if (btn.matches('.select-alternative-btn') && !btn.disabled) {
            e.preventDefault();
            const fighterId = btn.dataset.fighterId;
            const playerPrefix = btn.dataset.playerPrefix;
            if (!fighterId || !playerPrefix) return;
            submitMatchupAction(`lock_${playerPrefix}:${fighterId}`);
        }

        if (btn.matches('.lock-button')) {
            e.preventDefault();
            const actionVal = btn.value;
            if (!actionVal) return;
            submitMatchupAction(actionVal);
        }
    });
}

async function submitMatchupAction(actionValue) {
    const form = qs('#fighter-chooser-form');
    if (!form) return;
    const formData = new FormData(form);
    if (actionValue) {
        formData.set('action', actionValue);
    }

    const resp = await fetch(form.action, { method: 'POST', body: formData });
    if (!resp.ok) return;
    const text = await resp.text();
    const parser = new DOMParser();
    const doc = parser.parseFromString(text, 'text/html');
    const newResults = doc.querySelector('#results-display-area');
    const newLockP1 = doc.querySelector('#current_locked_p1_id');
    const newLockOpp = doc.querySelector('#current_locked_opp_id');
    if (newResults) {
        const current = qs('#results-display-area');
        if (current) {
            current.replaceWith(newResults);
            setupResultCardActions();
        }
    }
    if (newLockP1) qs('#current_locked_p1_id').value = newLockP1.value;
    if (newLockOpp) qs('#current_locked_opp_id').value = newLockOpp.value;
}