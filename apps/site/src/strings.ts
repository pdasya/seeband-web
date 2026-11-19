/** Every string the site shows. English only for now; another language gets its own routes. */
export const REPOSITORY_URL = "https://github.com/pdasya/seeband-web";
export const ISSUES_URL = `${REPOSITORY_URL}/issues`;
export const ORIGINAL_URL = "https://github.com/xAngelswordx/SeeBand";
// The app is a separate build on the same origin, at /fit and /results, so links to it are plain
// links. Its own header links back here at /.
export const APP_FIT_URL = "/fit";
export const APP_RESULTS_URL = "/results";
export const APP_DEMO_URL = "/fit?demo=1";
export const CONVENTIONS_URL = "/conventions/";
export const RESULTS_CHANGED_URL = "/results-changed/";
export const GUIDE_URL = "/guide/";

export const LANGUAGE = "en";
// Open Graph's form of the language.
export const LOCALE = "en_GB";
// The app's screens and the API: robots.txt keeps search engines out of them. A new app screen
// needs its path here.
export const NOT_FOR_SEARCH = [APP_FIT_URL, APP_RESULTS_URL, "/api/"];

export const STRINGS = {
  siteName: "SeeBand",
  // schema.org's description of the app, on the overview.
  application: {
    name: "SeeBand Web",
    category: "Scientific data analysis",
    operatingSystem: "Any, in a web browser",
    licence: "https://opensource.org/license/mit",
  },
  stage: "web · prototype",
  navigationLabel: "Sections",
  navigation: {
    overview: "Overview",
    fit: "Model fit",
    results: "Results",
    conventions: "Conventions",
    guide: "Guide",
  },
  skipToContent: "Skip to content",
  onThisPage: "On this page",
  home: {
    title: "SeeBand Web",
    description:
      "Fit single and double parabolic band models to Seebeck, resistivity and Hall data against temperature.",
    eyebrow: "Thermoelectric transport analysis",
    heading: "Parabolic band models for transport measurements",
    lead: "SeeBand Web fits single parabolic band (SPB) and double parabolic band (DPB) models to measured S(T), ρ(T) and R_H(T), and shows the fitted parameters, the curves calculated from them and how far those are from your data.",
    startFit: "Start a fit",
    readConventions: "Read the conventions",
    ctaNote: "Calculations run on the server · synthetic demo data included",
    figure: {
      label:
        "Schematic of one DPB case: a valence band 1 with its top at zero, a conduction band 2 starting at E_g, and E_F between them",
      energy: "E",
      wavevector: "k",
      // A symbol and its subscript, which the sketch sets lower.
      fermi: ["E", "F"],
      gap: ["E", "g"],
      band2Bottom: "band 2 bottom",
      band1Top: "band 1 top",
      // A band's name, and its kind, which a phone leaves out for room.
      band1: ["band 1", " · valence"],
      band2: ["band 2", " · conduction"],
      caption:
        "Schematic, not to scale, of one DPB case. Energies are measured from the top of band 1, a valence band; here band 2 is a conduction band starting at E_g, with E_F in the gap. With m₂/m₁ < 0, band 2 is a second valence band, and E_g < 0 means the bands overlap. E_F can also lie inside a band.",
    },
    how: {
      title: "How it works",
      steps: [
        {
          title: "Load data",
          text: "Separate files for S, ρ (or σ) and R_H, or one table whose columns you assign.",
        },
        {
          title: "Choose the model",
          text: "One or two parabolic bands, a scattering mechanism and the fit range.",
        },
        {
          title: "Fit and review",
          text: "Get the parameters, check the curves against the data and export the results.",
        },
      ],
    },
    inputs: {
      title: "Input data",
      quantity: "Quantity",
      unit: "SI unit",
      determines: "Fitted to it",
      rows: [
        {
          quantity: "T",
          unit: "K",
          determines: "the temperature of every point, of each quantity",
        },
        {
          quantity: "S(T)",
          unit: "V/K",
          determines: "band parameters: E_F (SPB); m₂/m₁, E_g, E_F (DPB)",
        },
        {
          quantity: "ρ(T) or σ(T)",
          unit: "Ω·m, S/m",
          determines:
            "conductivity scale: A (acoustic phonons, ionized impurities) or F (alloy disorder); for DPB also B or G, band 2 relative to band 1",
        },
        {
          quantity: "R_H(T)",
          unit: "m³/C",
          determines: "absolute mass: m (SPB); m₁ (DPB)",
        },
      ],
      notes: [
        "Files may use other common units, such as µV/K, µΩ·cm or °C: each column's unit is read from its header or chosen when loading. With no unit given, values are read in SI.",
        "In DPB with ρ, the S and ρ fits repeat until they agree. Whether the data pin a parameter down is shown for each fit.",
      ],
    },
    outputs: {
      title: "What you get",
      items: [
        "Fitted parameters, with how each was found and any bound it reached",
        "Model curves over the measurements, with the RMSE of each",
        "Chemical potential μ(T); for DPB, carrier concentration per band, in absolute terms only with R_H data",
        "With ρ data: conductivity σ(T), electronic thermal conductivity κ_e(T) and the Lorenz number L(T)",
        "Export of data, curves, parameters and a fit log",
        "A session file to reopen later, and a comparison of earlier runs",
      ],
    },
    data: {
      title: "Your data",
      text: "Calculations run on our server, so your measurements are sent to it. The server uses them only for the calculation you ask for and does not save them. Its logs record the route, status and duration of each request, not your data.",
    },
    status: {
      title: "Status",
      text: "This is a prototype. Some known errors of the desktop SeeBand are corrected here, so results can differ from it on purpose, and a physicist has not yet confirmed the corrections. Other known limitations are flagged next to the results they affect. A fit that converges does not show that the model suits your sample: check the RMSE, the curves against the data, and any parameter at its bound.",
      changed: "Results that changed",
    },
    demo: {
      title: "No data at hand?",
      text: "Open the fit with a synthetic data set, made with the DPB model and added noise, and try the controls.",
      action: "Open the demo",
    },
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
