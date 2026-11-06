/**
 * Every text the app shows, in one place until U3 brings i18n.
 *
 * Add new text here rather than in a component, so that U3 can move it all at once.
 */
export const STRINGS = {
  appName: "SeeBand",
  appStage: "web · prototype",
  skipToContent: "Skip to content",
  navigation: {
    label: "Sections",
    overview: "Overview",
    fit: "Model fit",
    results: "Results",
    conventions: "Conventions",
  },
  chart: {
    temperatureAxis: "T, K",
    toggleMeasurements: "Show measurements",
    failed: "The chart could not be shown. Try reloading the page.",
    noDataTitle: "No data yet",
    noDataText: "Curves appear here once measurements are loaded.",
    fitDescription: "Chart of the measurements and model against temperature",
    fitAxis: "S, µV/K",
  },
  status: {
    manual: "Manual parameters",
    running: "Fitting…",
    converged: "Converged",
    iterationLimit: "Iteration limit reached",
    stopped: "Stopped",
    failed: "Failed",
    suggested: "Initial guess",
  },
  fit: {
    pageTitle: "Model fit",
    title: "Transport property fit",
    subtitle: "Fit S(T), ρ(T) and R_H(T) with a parabolic band model",
    data: "Data",
    model: "Model",
    charts: "Charts",
    parameters: "Parameters",
    result: "Result",
  },
  results: {
    pageTitle: "Results",
    title: "Results",
    subtitle: "No fit yet. Run one on the model fit page.",
  },
  notFound: {
    pageTitle: "Page not found",
    title: "Page not found",
    text: "This page does not exist.",
    action: "Go to the model fit",
  },
  error: {
    pageTitle: "Something went wrong",
    title: "Something went wrong",
    text: "The page stopped working. Reloading it clears the data in this tab.",
    action: "Reload the page",
  },
} as const;
