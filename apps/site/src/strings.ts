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
  navigation: { overview: "Overview", fit: "Model fit", results: "Results" },
  skipToContent: "Skip to content",
  home: {
    title: "SeeBand Web",
    description:
      "Fit single and two parabolic band models to Seebeck, resistivity and Hall data against temperature.",
    heading: "Band models for thermoelectric transport data",
    lead: "SeeBand Web fits single parabolic band (SPB) and two parabolic band (DPB) models to measured S(T), ρ(T) and R_H(T), and shows what the fitted parameters imply.",
    serverNote:
      "Calculations run on the server, so your measurements are sent to it. They are not stored, and they are not written to logs.",
    openApp: "Open the app",
    status:
      "This is a prototype. Results can differ from the desktop SeeBand while the port is checked against it.",
  },
  notFound: {
    title: "Page not found",
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
