/* latexport @VERSION@ */

// ── i18n ──────────────────────────────────────────────────────────────
// Override any of these strings before this script loads, e.g.:
//   <script>window.latexportI18n = { widthLabel: 'Breite' };</script>

const i18n = Object.assign({
    widthLabel:       'Width',
    widthAriaLabel:   'Page width in ch units',
    toolbarAriaLabel: 'Page settings',
    mathOn:           'Math \u2713',
    mathOff:          'Math \u2717',
    mathAriaOn:       'MathJax rendering on',
    mathAriaOff:      'MathJax rendering off',
    goToTop:          '\u2191',
    goToTopAria:      'Go to top of page',
}, window.latexportI18n || {});

// ── Constants ─────────────────────────────────────────────────────────
const PAGE_WIDTH_KEY    = 'latexport-page-width';
const PAGE_WIDTH_DEFAULT = 80;
const PAGE_WIDTH_MIN    = 40;
const PAGE_WIDTH_MAX    = 160;
const PAGE_WIDTH_STEP   = 10;

const MATHJAX_KEY       = 'latexport-mathjax';

// ── Page width ────────────────────────────────────────────────────────

function getSavedWidth() {
    const raw = parseInt(localStorage.getItem(PAGE_WIDTH_KEY), 10);
    if (isNaN(raw)) return PAGE_WIDTH_DEFAULT;
    return Math.min(PAGE_WIDTH_MAX, Math.max(PAGE_WIDTH_MIN, raw));
}

function applyWidth(ch) {
    document.documentElement.style.setProperty('--page-width', ch + 'ch');
}

// ── MathJax ───────────────────────────────────────────────────────────

function isMathJaxEnabled() {
    return localStorage.getItem(MATHJAX_KEY) !== 'false';
}

async function setMathJaxEnabled(enabled) {
    localStorage.setItem(MATHJAX_KEY, enabled ? 'true' : 'false');
    if (typeof MathJax === 'undefined') return;
    try {
        await MathJax.startup.promise;
        if (enabled) {
            await MathJax.typesetPromise([document.body]);
        } else {
            MathJax.typesetClear([document.body]);
        }
    } catch (_) {
        // MathJax not available or not yet fully initialised
    }
}

// Block MathJax context menu when math rendering is off.
// MathJax v4 attaches a contextmenu listener to the assistive-MathML element
// that survives typesetClear, so we intercept at the capture phase before
// MathJax's handler runs.
document.addEventListener('contextmenu', (e) => {
    if (!isMathJaxEnabled() && e.target.closest('math, mjx-container')) {
        e.preventDefault();
        e.stopImmediatePropagation();
    }
}, true);

// ── Toolbar ───────────────────────────────────────────────────────────

function buildToolbar(currentWidth, mathEnabled) {
    const aside = document.createElement('aside');
    aside.id = 'latexport-toolbar';
    aside.setAttribute('aria-label', i18n.toolbarAriaLabel);

    // Width control
    const widthGroup = document.createElement('div');
    widthGroup.className = 'toolbar-width-group';
    widthGroup.style.cssText = 'display:flex;align-items:center;gap:0.3rem';

    const label = document.createElement('label');
    label.htmlFor = 'page-width-input';
    label.textContent = i18n.widthLabel;

    const slider = document.createElement('input');
    slider.type = 'range';
    slider.id = 'page-width-input';
    slider.min = String(PAGE_WIDTH_MIN);
    slider.max = String(PAGE_WIDTH_MAX);
    slider.step = String(PAGE_WIDTH_STEP);
    slider.value = String(currentWidth);
    slider.setAttribute('aria-label', i18n.widthAriaLabel);
    slider.setAttribute('aria-valuemin', String(PAGE_WIDTH_MIN));
    slider.setAttribute('aria-valuemax', String(PAGE_WIDTH_MAX));
    slider.setAttribute('aria-valuenow', String(currentWidth));
    slider.setAttribute('aria-valuetext', currentWidth + 'ch');

    const valueDisplay = document.createElement('output');
    valueDisplay.id = 'page-width-value';
    valueDisplay.setAttribute('for', 'page-width-input');
    valueDisplay.textContent = currentWidth + 'ch';
    valueDisplay.setAttribute('aria-live', 'polite');

    slider.addEventListener('input', () => {
        const val = parseInt(slider.value, 10);
        slider.setAttribute('aria-valuenow', String(val));
        slider.setAttribute('aria-valuetext', val + 'ch');
        valueDisplay.textContent = val + 'ch';
        applyWidth(val);
    });

    slider.addEventListener('change', () => {
        localStorage.setItem(PAGE_WIDTH_KEY, slider.value);
    });

    widthGroup.append(label, slider, valueDisplay);

    // Separator
    const sep = document.createElement('div');
    sep.className = 'toolbar-sep';
    sep.setAttribute('aria-hidden', 'true');

    // MathJax toggle
    const mathBtn = document.createElement('button');
    mathBtn.type = 'button';
    mathBtn.id = 'mathjax-toggle';
    mathBtn.setAttribute('aria-pressed', String(mathEnabled));
    mathBtn.setAttribute('aria-label', mathEnabled ? i18n.mathAriaOn : i18n.mathAriaOff);
    mathBtn.title = mathEnabled ? i18n.mathAriaOn : i18n.mathAriaOff;
    mathBtn.textContent = mathEnabled ? i18n.mathOn : i18n.mathOff;

    mathBtn.addEventListener('click', () => {
        const nowEnabled = mathBtn.getAttribute('aria-pressed') !== 'true';
        mathBtn.setAttribute('aria-pressed', String(nowEnabled));
        mathBtn.setAttribute('aria-label', nowEnabled ? i18n.mathAriaOn : i18n.mathAriaOff);
        mathBtn.title = nowEnabled ? i18n.mathAriaOn : i18n.mathAriaOff;
        mathBtn.textContent = nowEnabled ? i18n.mathOn : i18n.mathOff;
        setMathJaxEnabled(nowEnabled);
    });

    aside.append(widthGroup, sep, mathBtn);
    document.body.appendChild(aside);
}

// ── Go to top ─────────────────────────────────────────────────────────

function buildGoToTopButton() {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'go-to-top';
    btn.setAttribute('aria-label', i18n.goToTopAria);
    btn.setAttribute('hidden', '');
    btn.textContent = i18n.goToTop;

    btn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
        // Return focus to the first heading so screen reader users land somewhere useful
        const target = document.querySelector('h1, h2, [role="main"], main');
        if (target) {
            if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
            target.focus({ preventScroll: true });
        }
    });

    document.body.appendChild(btn);
    return btn;
}

// ── Safari workaround ─────────────────────────────────────────────────

function enableSafariOnly() {
    const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
    if (isSafari) {
        document.body.classList.add('is-safari');
    }
}

// ── Initialisation ────────────────────────────────────────────────────

window.addEventListener('load', () => {
    enableSafariOnly();

    // Apply saved (or default) page width
    const width = getSavedWidth();
    applyWidth(width);

    // Build toolbar and go-to-top button
    buildToolbar(width, isMathJaxEnabled());

    const goTopBtn = buildGoToTopButton();
    window.addEventListener('scroll', () => {
        if (window.scrollY > 300) {
            goTopBtn.removeAttribute('hidden');
        } else {
            goTopBtn.setAttribute('hidden', '');
        }
    }, { passive: true });

    // If MathJax was disabled in a previous session, clear it once it loads
    if (!isMathJaxEnabled() && typeof MathJax !== 'undefined') {
        MathJax.startup.promise
            .then(() => MathJax.typesetClear([document.body]))
            .catch(() => {});
    }
});
