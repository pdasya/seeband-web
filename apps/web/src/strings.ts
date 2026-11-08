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
  parameters: {
    title: "Parameters",
    subtitle: "The curve follows the values",
    fixed: "not fitted",
    // How a parameter is written. Any other shows its name, so a new one needs no change here.
    symbols: {
      band_mass: "m",
      m_eff: "m₂/m₁",
      band_gap: "E_g",
      fermi_energy: "E_F",
      m1: "m₁",
    },
    units: {
      m_e: "in mₑ",
      K: "in K",
      dimensionless: "",
      unknown: "unit not known",
    },
    editBounds: "Edit bounds",
    boundsTitle: "Bounds of the fit",
    boundsDone: "Done",
    closeBounds: "Close",
    defaultBounds: "Default bounds",
    boundsHint:
      "What a fit of this mode may reach. Values do not move with them, and each slider follows.",
    boundLowerTitle: "Lower",
    boundUpperTitle: "Upper",
    boundLower: (symbol: string) => `${symbol}, lower bound`,
    boundUpper: (symbol: string) => `${symbol}, upper bound`,
    boundsInvalid:
      "The lower bound must be below the upper. The last valid bounds stay in use.",
    outOfRange: (minimum: string, maximum: string) =>
      `enter a number from ${minimum} to ${maximum}. The last valid value stays in use.`,
  },
  model: {
    title: "Model",
    subtitle: "Parabolic bands and scattering mechanism",
    loading: "Loading the models…",
    loadFailed: "The models could not be loaded. Reload the page to try again.",
    bands: "Number of bands",
    fitMode: "Fit mode",
    scattering: "Scattering",
    scatteringNames: {
      acPh: "Acoustic phonons (acPh)",
      dis: "Alloy disorder (dis)",
      acPhDis: "Both mechanisms (acPhDis)",
    },
    disabledReason: "not available until a known error is fixed.",
    disabledReasons: {
      "known_issue.spb_hall_mode_disabled":
        "not available until a known error is fixed. This fit fails on the desktop, and its mass and scales are wrong.",
    },
    degeneracyHint: "Band degeneracies are not fitted.",
    degeneracyInvalid:
      "N₁ and N₂ must be above 0. The last valid value stays in use.",
    range: "Fit range, K",
    rangeMin: "Lower bound, K",
    rangeMax: "Upper bound, K",
    rangeInvalid:
      "The lower bound must be below the upper, and both above 0 K. The last valid range stays in use.",
    missingTitle: "Missing data:",
    missingText: "Load a file or assign a column to run this fit mode.",
  },
  data: {
    title: "Data",
    subtitle: {
      separate:
        "Each file: T in K and the value. S in V/K, ρ in Ω·m, R_H in m³/C.",
      single:
        "One table: a column for T in K, and for each quantity. S in V/K, ρ in Ω·m, R_H in m³/C.",
    },
    dropHint: "Drop a file or browse",
    source: {
      label: "Data source",
      separate: "Separate files",
      single: "Single file",
    },
    interpolation: {
      title: "Interpolation",
      hint: "Chebyshev, degree 10, step ≈20 K",
      working: "Interpolating…",
      range: "Fit range",
      noRange: "The fit range is not known yet.",
      invalidRange:
        "This fit range cannot be interpolated. It must start above 0 K, and span 20 to 200000 K.",
      flags: {
        failed: "could not be interpolated, so a fit cannot use it.",
        notFinite: "the polynomial overflowed, so a fit cannot use it.",
        noMeasuredPoints:
          "no measured point lies in the fit range, so every value is made up.",
        extrapolated:
          "the grid goes beyond the data, so some values are made up.",
        underdetermined: "too few points set the polynomial.",
      },
    },
    single: {
      dropTitle: "A table with several columns",
      rows: "rows",
      columns: "columns",
      column: "Column",
      columnRole: "Quantity for column",
      mapTitle: "Column mapping",
      mapHint: "Detected from the header. Change it if needed.",
      ignore: "Ignore",
      notFound: "not found",
      preview: "Preview, first rows",
      errorTitle: "Check the mapping.",
      fileErrorTitle: "Check the file.",
      noQuantity: "No column holds a quantity yet. Choose one above.",
    },
    reading: "Reading…",
    remove: "Remove file",
    cancel: "Cancel reading",
    points: "points",
    line: "Line",
    column: "Column",
    andMore: "More problems:",
    demoSource: "Demo data",
    demoLoading: "Loading the demo data…",
    demoFailed:
      "The demo data could not be loaded. Reload to try again, or load your own data.",
    demoClear: "Clear demo data",
    demoTry: "Try demo data",
    demoNoticeOther: "These are demo data, not a measurement.",
    demoNotices: {
      "demo_dataset.synthetic":
        "Synthetic data, generated with the DPB model and added noise. They are not a measurement of any material.",
    },
    oneFile: "Drop one file at a time.",
    quantityNotFound: "This file has no column for this quantity.",
    tooManyRows: "This file has more than 2000 rows.",
    rateLimited: "Too many files in a short time. Try again in a minute.",
    networkError: "The server could not be reached. Check your connection.",
    parseFailed: "The file could not be read. Try again.",
    serverUnavailable:
      "The server is not responding, so the file was not read. Try again shortly.",
    fileProblems: {
      wrong_file_type: "Choose a .txt, .csv or .dat file.",
      file_too_large: "This file is too large.",
      read_failed: "This could not be read. Choose a single file.",
    },
    quantities: {
      seebeck: { symbol: "S", title: "Seebeck coefficient", unit: "V/K" },
      resistivity: { symbol: "ρ", title: "Resistivity", unit: "Ω·m" },
      hall: { symbol: "R_H", title: "Hall coefficient", unit: "m³/C" },
    },
    issues: {
      no_data: "No rows of numbers.",
      wrong_encoding: "This text has unreadable characters. Save it as UTF-8.",
      line_too_long: "This line is too long.",
      too_many_problems: "Too many problems. Stopped here.",
      too_few_columns: "This row has one number.",
      wrong_column_count: "This row has a different number of columns.",
      missing_value: "An empty field.",
      not_numeric: "A value that is not a number.",
      not_finite: "A value that is not finite.",
      decimal_comma: "This looks like decimal commas. Use a decimal point.",
      too_few_rows: "Fewer than 2 rows.",
      missing_temperature: "No column holds the temperature.",
      non_positive_temperature: "A temperature of 0 K or below.",
      repeated_role: "A quantity is assigned twice.",
      preamble_skipped: "A line of text before the header was left out.",
      header_mismatch: "The header has a different number of columns.",
      unit_differs: "A column with another unit was not used.",
      repeated_header: "A second column for one quantity was not used.",
      columns_need_assigning: "More than two columns with no header.",
      expected_not_found: "This file has no column for this quantity.",
      no_quantity: "No column holds a quantity.",
      few_rows:
        "Fewer than 6 temperatures, so a neural net guess means little.",
      unsorted_temperature:
        "Rows were not in order of T, and have been sorted.",
      duplicate_temperature: "A temperature is repeated.",
    },
  },
  chart: {
    temperatureAxis: "T, K",
    toggleMeasurements: "Show measurements",
    failed: "The chart could not be shown. Try reloading the page.",
    tabsLabel: "Charts",
    tabs: {
      seebeck: "S(T)",
      resistivity: "ρ(T)",
      hall: "R_H(T)",
      chemical_potential: "μ(T)",
      bands: "Band contributions",
      band_diagram: "E(k)",
    },
    diagramCurves: {
      band_1_energy_k: "Band 1",
      band_2_energy_k: "Band 2",
      fermi_energy_k: "E_F",
    },
    diagramDescription: "Sketch of the band energies against wavevector",
    wavevectorAxis: "k",
    axes: {
      seebeck: "S, µV/K",
      resistivity: "ρ, µΩ·m",
      hall: "R_H, m³/C",
      chemicalPotential: "μ, K",
      energy: "E, K",
    },
    quantityTabs: {
      seebeck: {
        description: "Chart of S against temperature",
        noDataTitle: "No data for this quantity",
        noDataText:
          "Load a file or assign a column in the single-file mapping.",
        notInMode: "The S model is not calculated in this fit mode.",
      },
      resistivity: {
        description: "Chart of ρ against temperature",
        noDataTitle: "No data for this quantity",
        noDataText:
          "Load a file or assign a column in the single-file mapping.",
        notInMode: "The ρ model is not calculated in this fit mode.",
      },
      hall: {
        description: "Chart of R_H against temperature",
        noDataTitle: "No R_H(T) data",
        noDataText:
          "Load a Hall coefficient file (m³/C). R_H sets the overall scale E = m₁^(3/2) and determines the absolute mass m₁.",
        notInMode: "The R_H model is not calculated in this fit mode.",
      },
    },
    chemicalPotential: "μ",
    chemicalPotentialDescription:
      "Chart of the chemical potential μ against temperature, with band edges",
    bandEdge: "band edge",
    band1Top: "band 1 top",
    band2Bottom: "band 2 bottom (E_g)",
    bandsDescription:
      "Chart of the total S and the contribution of each band against temperature",
    totalS: "Total S",
    band1Contribution: "band 1 contribution",
    band2Contribution: "band 2 contribution",
    notInThisMode: {
      title: "Not available in this mode",
      text: "This fit mode has no such curve.",
    },
    unavailable: {
      single_band: {
        title: "DPB only",
        text: "Band contributions are computed for the two-parabolic-band model.",
      },
    },
    model: "Model",
    measurements: "Measurements",
    measurementsDemo: "Measurements (demo)",
    interpolated: "Interpolated",
    updating: "Updating…",
    lastCurveStays: "The last curve stays on the chart.",
    noResult: "The calculation has no result for these parameters.",
    rateLimited: "Too many updates in a short time. Trying again shortly.",
    rateLimitedWait:
      "Too many updates in a short time. Change a value to try again.",
    networkError: "The server could not be reached.",
    serverUnavailable: "The server is not responding.",
    calcFailed: "The curve could not be calculated.",
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
    charts: "Charts",
    result: "Result",
    guess: "Initial guess",
    guessHint: "The neural net proposes m₂/m₁, E_g and E_F from S(T)",
    guessOnlyWithNets: "The neural net is used for DPB only",
    guessNeedsData: "Load S data to use the neural net",
    guessNet: (minK: string, maxK: string) => `· net ${minK}–${maxK} K`,
    guessNoNet: (firstK: string, lastK: string, available: string) =>
      `No neural net covers ${firstK}–${lastK} K, so the values stay as they are. The nets cover ${available}.`,
    guessNotFinite:
      "The neural net gave no usable values for these data, so the values stay as they are.",
    guessNeedsMass:
      "The neural net predicts m₂/m₁ of about 0, which cannot be calculated, so the values stay as they are. Set a mass by hand.",
    guessFailed:
      "The initial guess could not be calculated, so the values stay as they are.",
    guessLimited:
      "Too many initial guesses in a short time, so the values stay as they are. Try again in a moment.",
    guessWarnings: {
      unsorted_temperature:
        "The temperatures in these data do not rise, so the net may not suit them.",
      underdetermined_fit:
        "These data have too few temperatures to set the net's input, so its values mean little.",
    },
    reset: "Reset",
    run: "Run fit",
    stop: "Stop",
    queued: "waiting in the queue",
    atIteration: (iteration: number) => `iteration ${String(iteration)}`,
    stoppedAt: (iteration: number) => `at iteration ${String(iteration)}`,
    convergedIn: (iterations: number) => `in ${String(iterations)} iter.`,
    resultFailed: "The fit could not finish. Change the values, and try again.",
    // The API's fixed text for a fit that ends without a result.
    resultFailures: {
      "The start values do not fit the bounds.":
        "The start values do not fit the bounds.",
      "The model gave values that are not finite during the fit.":
        "The model gave values that are not finite during the fit.",
      "The fit reached its limit of function evaluations.":
        "The fit reached its limit of function evaluations.",
    },
    failures: {
      fit_timeout: "The fit ran past its time limit, and has ended.",
      fit_process_died: "The fit stopped unexpectedly. Try again.",
      fit_queue_full: "Too many fits are running. Try again in a moment.",
      client_fit_limit:
        "You have too many fits running. Wait a moment, and try again.",
      invalid_fit: "The server refused this fit. Check the data and values.",
      rate_limited: "Too many fits in a short time. Try again in a moment.",
      network_error: "The connection was lost during the fit. Try again.",
      stream_ended: "The connection was lost during the fit. Try again.",
    },
    failureOther: "The fit failed on the server. Try again.",
    blockers: {
      noMode: "Choose a fit mode to run a fit.",
      interpolating: "Waiting for interpolated values.",
      missingData: "This fit mode needs data for",
      notInterpolated: "No usable interpolated values for",
      noPointsInRange: "No points in the fit range for",
      startOutsideBounds: "A fit cannot start outside its bounds:",
    },
    rmse: "RMSE",
    noRmse: "The RMSE appears here once measurements are loaded.",
    rmseNotFinite: "not finite",
    rmseFailed: "The RMSE could not be calculated for the current values.",
    rmseOutdated: "These are from the last curve, not from the current values.",
    noPointsInRange: "no points in the fit range, so no RMSE.",
    notInterpolated: "no usable interpolated values, so no RMSE.",
    zerosLeftOut:
      "points with a value of 0 are left out of the RMSE, as it is relative.",
    rmseUnits: { "uV/K": "µV/K" },
    issueSeverity: {
      disabled: "Not available",
      unreliable: "Unreliable",
      caution: "Caution",
    },
    issueMark: {
      disabled: "not available",
      unreliable: "unreliable",
      caution: "caution",
    },
    knownIssueOther: "A known error applies to this result.",
    knownIssueTexts: {
      "known_issue.spb_hall_mode_disabled":
        "This fit fails on the desktop, and its mass and scales are wrong.",
      "known_issue.spb_hall_uses_fermi_energy":
        "SPB R_H uses the Fermi energy at 0 K instead of the chemical potential, which also affects this fit.",
      "known_issue.dpb_hall_prefactor":
        "DPB R_H is half of what it should be, so m₁ and n from it are too low.",
      "known_issue.acphdis_curve_scale":
        "With acPhDis, σ, κ and S by band use another scale of C and D than ρ and S, so σ·ρ is not 1, and band contributions do not sum to S.",
      "known_issue.acphdis_band_weight":
        "With acPhDis, the band weight of the last temperature applies to all of S.",
      "known_issue.acphdis_early_stop":
        "With acPhDis, this fit stops when C and D alone settle, so it can end before the other values do.",
      "known_issue.dpb_s_degeneracy":
        "With N₂/N₁ other than 1, a fitted m₂/m₁ does not match its curves.",
      "known_issue.dpb_loop_degeneracy":
        "With N₂/N₁ other than 1, the fit returns m₂/m₁ times N₂/N₁, so the value shown can leave its bounds. The bounds and the at-bound mark apply to the value before that factor.",
      "known_issue.negative_m_eff_weight":
        "With m₂/m₁ below 0, band 2 gets a negative weight, for a physicist to check.",
      "known_issue.collapsed_m_eff":
        "With m₂/m₁ near 0, the other band has no weight left, so the data do not settle the fit, and it can differ between machines.",
      "known_issue.no_chemical_potential":
        "With the Fermi energy outside the band, there are no carriers, so the chemical potential and the curves from it mean nothing.",
      "known_issue.hall_dis_no_reference":
        "This fit fails on the desktop, and runs here with other bounds of G, so there is no desktop result to compare with.",
      "known_issue.band_diagram_formula":
        "This is a sketch, as on the desktop. Its curves do not follow E = ħ²k²/(2m) in any stated units, and in DPB band 1 has a mass of −1 whatever the values. Only E_F and where each band starts are exact.",
      "known_issue.interpolation_extrapolates":
        "Interpolation made up points beyond the data, and they count in the RMSE and in a fit.",
    },
    iterations: "Iterations",
    noIterations: "—",
    iterationLimit: (limit: number) => `limit ${String(limit)}`,
    rangeSummary: (minK: string, maxK: string) => `range ${minK}–${maxK} K`,
    endNotes: {
      iterationLimit: (limit: number | null) =>
        limit === null
          ? "The fit reached its iteration limit before it converged, so these values are not a converged result."
          : `The fit reached its limit of ${String(limit)} iterations before it converged, so these values are not a converged result.`,
      stopped:
        "The fit was stopped, so these are its last values, not a converged result.",
      stoppedAtStart:
        "The fit was stopped before its first result, so these are the values it started from.",
      failed:
        "The fit failed, so these are not a fitted result: they are its start values or those of its last iteration.",
    },
    parameterTable: "Parameters in use",
    columns: { parameter: "Parameter", value: "Value", bounds: "Bounds" },
    valueUnits: { K: "K", m_e: "mₑ" },
    boundsRange: (lower: string, upper: string) => `${lower} … ${upper}`,
    noBounds: "—",
    atBound: "at bound",
    atBoundNote:
      "A value at a bound may have been set by that bound, not by the data.",
    moreGraphs: "More graphs",
    openResults: "Open results",
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
