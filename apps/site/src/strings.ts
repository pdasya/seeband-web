/** Every string the site shows. English only for now; another language gets its own routes. */
export const REPOSITORY_URL = "https://github.com/pdasya/seeband-web";
export const ISSUES_URL = `${REPOSITORY_URL}/issues`;
export const ORIGINAL_URL = "https://github.com/xAngelswordx/SeeBand";
// The app is a separate build on the same origin, at /fit and /results, so links to it are plain
// links. Its own header links back here at /.
export const APP_FIT_URL = "/fit";
export const APP_RESULTS_URL = "/results";

export const LANGUAGE = "en";

export const STRINGS = {
  siteName: "SeeBand",
  stage: "web · prototype",
  navigationLabel: "Sections",
  navigation: {
    overview: "Overview",
    fit: "Model fit",
    results: "Results",
    conventions: "Conventions",
  },
  skipToContent: "Skip to content",
  home: {
    title: "SeeBand Web",
    description:
      "Fit single and double parabolic band models to Seebeck, resistivity and Hall data against temperature.",
    heading: "Band models for thermoelectric transport data",
    lead: "SeeBand Web fits single parabolic band (SPB) and double parabolic band (DPB) models to measured S(T), ρ(T) and R_H(T), and shows the fitted parameters, the curves calculated from them and how far those are from your data.",
    serverNote:
      "Calculations run on our server, so your measurements are sent to it. The server uses them only for the calculation you ask for and does not save them. Its logs record the route, status and duration of each request, not your data.",
    openApp: "Open the app",
    status:
      "This is a prototype. Some known errors of the desktop SeeBand are corrected here, so results can differ from it on purpose, and a physicist has not yet confirmed the corrections. Other known limitations are flagged next to the results they affect. A fit that converges does not show that the model suits your sample: check the residuals and any parameter at its bound.",
  },
  notFound: {
    title: "Page not found · SeeBand",
    heading: "Page not found",
    text: "There is no page at this address.",
    back: "Go to the overview",
  },
  footer: {
    label: "Site information",
    repository: "Source code",
    contact: "Questions and problems: GitHub issues",
    original:
      "Based on SeeBand by Michael Parzer and Alexander Riss, MIT licence",
  },
};
