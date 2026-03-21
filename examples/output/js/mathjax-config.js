/* latexport 2026.3.2 */

MathJax = {
  startup: {
    ready() {
      MathJax.startup.defaultReady();
      // Respect the saved MathJax preference — suppress the initial typeset
      // pass if the user had previously turned math rendering off.
      if (localStorage.getItem('latexport-mathjax') === 'false') {
        MathJax.startup.promise = MathJax.startup.promise
          .then(() => MathJax.typesetClear([document.body]));
      }
    },
  },
  options: {
    skipHtmlTags: [
      //  HTML tags that won't be searched for math
      "svg",
      "script",
      "noscript",
      "style",
      "textarea",
      "pre",
      "code",
      "math",
      "select",
      "option",
      "mjx-container",
    ],
    includeHtmlTags: {
      //  HTML tags that can appear within math
      br: "\n",
      wbr: "",
      "#comment": "",
    },
    ignoreHtmlClass: "ltx_eqn_cell", //  class that marks tags not to search
    processHtmlClass: "mathjax_process", //  class that marks tags that should be searched
    compileError: (doc, math, err) => doc.compileError(math, err),
    typesetError: (doc, math, err) => doc.typesetError(math, err),
  },
  output: {
    scale: 1, // global scaling factor for all expressions
    minScale: 0.5, // smallest scaling factor to use
    mtextInheritFont: false, // true to make mtext elements use surrounding font
    merrorInheritFont: false, // true to make merror text use surrounding font
    mtextFont: "", // font to use for mtext, if not inheriting (empty means use MathJax fonts)
    merrorFont: "serif", // font to use for merror, if not inheriting (empty means use MathJax fonts)
    unknownFamily: "serif", // font to use for character that aren't in MathJax's fonts
    mathmlSpacing: false, // true for MathML spacing rules, false for TeX rules
    skipAttributes: {}, // RFDa and other attributes NOT to copy to the output
    exFactor: 0.5, // default size of ex in em units
    displayAlign: "center", // default for indentalign when set to 'auto'
    displayIndent: "0", // default for indentshift when set to 'auto'
    displayOverflow: "overflow", // default for overflow (scroll/scale/truncate/elide/linebreak/overflow)
    linebreaks: {
      // options for when overflow is linebreak
      inline: true, // true for browser-based breaking of inline equations
      width: "100%", // a fixed size or a percentage of the container width
      lineleading: 0.2, // the default lineleading in em units
    },
    font: "mathjax-newcm", // the font component to load
    fontPath: "https://cdn.jsdelivr.net/npm/@mathjax/mathjax-newcm-font@4", // The path to the font definitions
    fontExtensions: [], // The font extensions to load
    htmlHDW: "auto", // 'use', 'force', or 'ignore' data-mjx-hdw attributes
    preFilters: [], // A list of pre-filters to add to the output jax
    postFilters: [], // A list of post-filters to add to the output jax
  },
};
