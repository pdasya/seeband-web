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
    fixed: "not fitted",
    held: "held",
    hold: (symbol: string) => `Hold ${symbol} at its value in a fit`,
    about: (symbol: string) => `About ${symbol}`,
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
      eV: "in eV",
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
    disabledReasons: {},
    degeneracyHint: "Band degeneracies are not fitted.",
    degeneracyInvalid:
      "N₁ and N₂ must be above 0. The last valid value stays in use.",
    range: "Fit range, K",
    rangeMin: "Lower bound, K",
    rangeMax: "Upper bound, K",
    rangeInvalid:
      "The lower bound must be below the upper, and both above 0 K. The last valid range stays in use.",
  },
  data: {
    title: "Data",
    subtitle: {
      separate:
        "Each file: T and the value, in the units its header names or the ones you choose. With neither: T in K, S in V/K, ρ in Ω·m, R_H in m³/C.",
      single:
        "One table: a column for T, and for each quantity, in the units its header names or the ones you choose. With neither: T in K, S in V/K, ρ in Ω·m, R_H in m³/C.",
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
        // Why the server refused, by its reason code.
        failedBecause: {
          no_overlap:
            "its measured range does not overlap the fit range, so a fit cannot use it.",
          overlap_too_short:
            "its measured range overlaps the fit range too little to interpolate, so a fit cannot use it.",
          fit_failed:
            "the polynomial could not be fitted to its data, so a fit cannot use it.",
        },
        notFinite: "the polynomial overflowed, so a fit cannot use it.",
        noMeasuredPoints:
          "no measured point lies in the fit range, so every value comes from the polynomial alone, which can be far off between measurements.",
        rangeLimited: (minK: string, maxK: string) =>
          `the measured range limits interpolation to ${minK}–${maxK} K, and a fit uses only that.`,
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
    bar: {
      loaded: "Data loaded",
      details: "Details",
      hide: "Hide",
      points: (symbol: string, points: number) =>
        `${symbol} · ${String(points)} pts`,
      notLoaded: (symbol: string) => `${symbol} · not loaded`,
    },
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
    noHeaderQuestion:
      "This file has no column names. Choose what its columns hold.",
    nameSuggests: (title: string) => `Its name suggests ${title}.`,
    headerMismatchQuestion:
      "The column names of this file do not match its columns. Choose what its columns hold.",
    belowZeroForRho:
      "Some values are below 0, which a resistivity cannot have.",
    chooseColumns: (symbol: string) =>
      `Choose the column that holds ${symbol}, or another quantity. The file loads once T and one quantity are chosen.`,
    slotBusy: (title: string) =>
      `The slot of ${title} has a file on its way. Finish there first, or choose another quantity.`,
    slotTaken: (title: string) =>
      `The slot of ${title} holds a file. Remove it first, or choose another quantity.`,
    tryAgain: "Try again",
    tableSize: (rows: number, columns: number) =>
      `${String(rows)} rows · ${String(columns)} columns`,
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
    units: {
      K: "K",
      C: "°C",
      "V/K": "V/K",
      "uV/K": "µV/K",
      "Ohm*m": "Ω·m",
      "mOhm*cm": "mΩ·cm",
      "uOhm*m": "µΩ·m",
      "m^3/C": "m³/C",
      "cm^3/C": "cm³/C",
    },
    unitOf: (name: string) => `Unit of ${name}`,
    temperature: "Temperature",
    inSi: (written: string, si: string) => `${written} = ${si} in SI`,
    checkUnitTitle: "Check the unit",
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
      non_positive_temperature:
        "A temperature of 0 K or below. If this column is in °C, choose °C for it.",
      negative_resistivity:
        "A resistivity below 0, which no measurement gives.",
      repeated_role: "A quantity is assigned twice.",
      preamble_skipped: "A line of text before the header was left out.",
      header_mismatch: "The header has a different number of columns.",
      unit_differs: "A column in a unit SeeBand cannot read was not used.",
      unit_assumed:
        "Its header names a unit SeeBand cannot read, so the values are read in SI. Choose the unit they are in, or convert the column to one listed here.",
      unit_not_allowed: "This unit does not fit the quantity of this column.",
      implausible_magnitude:
        "These values are far from any usual size in SI, as when µV/K is read as V/K. Check the unit of this column.",
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
    failed: "The chart could not be shown. Try reloading the page.",
    tabs: {
      seebeck: "Seebeck S(T)",
      conductivity: "Conductivity σ(T)",
      resistivity: "Resistivity ρ(T)",
      hall: "Hall coefficient R_H(T)",
      chemical_potential: "Chemical potential μ(T)",
      thermal_conductivity: "Thermal conductivity κ_e(T)",
      bands: "Band contributions",
      carrier_concentration: "Carrier concentration by band",
      band_diagram: "Band diagram E(k)",
    },
    panelLabel: (index: number) => `Chart ${String(index)}`,
    panelSelect: (index: number) => `Quantity shown in chart ${String(index)}`,
    bandGapMetric: (gap: string, unit: string) => `E_g = ${gap} ${unit}`,
    conductivityDescription: "Chart of σ against temperature",
    conductivityPoints: "1/ρ of the data",
    conductivityPointsInterpolated: "1/ρ of the interpolated data",
    conductivityPointsNote:
      "Points are 1/ρ of the ρ data in the fit range, which the server calculates. The line is the model's σ.",
    conductivityNote:
      "The model's σ only: measured points would be 1/ρ, which the ρ data give.",
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
      chemicalPotential: (unit: string) => `μ, ${unit}`,
      energy: (unit: string) => `E, ${unit}`,
      conductivity: "σ, S/m",
      thermalConductivity: "κ_e, W/(m·K)",
      carrierConcentration: "n, cm⁻³",
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
      needs_resistivity: {
        title: "Needs ρ(T)",
        text: "This curve takes the scattering, which only a fit mode with ρ finds.",
      },
      not_on_desktop: {
        title: "Not in SeeBand",
        text: "The desktop application has no such curve for this model.",
      },
    },
    thermalConductivity: "κ_e",
    thermalConductivityDescription: "Chart of κ_e against temperature",
    thermalConductivityNote:
      "The electronic part only, with the bipolar part in a two-band model. The lattice part is not modelled.",
    carrierConcentrationDescription:
      "Chart of the carrier concentration of each band against temperature",
    carrierConcentrationRelative:
      "With no R_H data, n uses m₁ = 1, so its size is not measured. Compare the bands, not the values.",
    band1: "band 1",
    band2: "band 2",
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
    running: "Fitting…",
    converged: "Converged",
    iterationLimit: "Iteration limit reached",
    stopped: "Stopped",
    failed: "Failed",
    suggested: "Initial guess",
  },
  fit: {
    pageTitle: "Model fit",
    data: "Data",
    charts: "Charts",
    result: "Result",
    panelTitle: "Fit",
    guess: "Initial guess",
    guessHint:
      "Estimate band parameters from S(T); SPB mass magnitude is preserved",
    guessUnsupported: {
      sign_change:
        "S(T) changes sign; a single-band estimate is unavailable. Try DPB.",
      too_few_temperatures:
        "At least three distinct usable temperatures are needed.",
      zero_seebeck: "Zero Seebeck does not determine a finite Fermi energy.",
    },
    guessNumerical:
      "Estimated from S(T); mass magnitude is preserved. Check the calculated curve before fitting.",
    guessNumericalBadge: "· numerical S(T) estimate",
    guessUnavailable: "Initial guess is available for SPB and DPB",
    guessNeedsData: "Load S data to estimate start values",
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
      estimate_at_bound:
        "The estimate reached a search bound; inspect the curve before fitting.",
      large_estimate_residual:
        "The estimated curve has an RMS residual above 20% of the measured RMS signal. This is a quality heuristic, not a band-count diagnosis.",
      low_temperature_omitted:
        "Very low-temperature rows were omitted to avoid overflow in the existing SPB formula.",
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
      "The sign of the start band mass does not match the sign of R_H.":
        "The sign of the start band mass does not match the sign of R_H. A positive mass is an electron band, with R_H below 0.",
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
    missingData: (symbols: string) => `Missing data: ${symbols}`,
    blockers: {
      noMode: "Choose a fit mode to run a fit.",
      interpolating: "Waiting for interpolated values.",
      notInterpolated: "No usable interpolated values for",
      noPointsInRange: "No points in the fit range for",
      startOutsideBounds: "A fit cannot start outside its bounds:",
      allHeld: "Every fitted parameter is held. Release one to fit.",
    },
    rmse: "RMSE",
    degeneracySymbol: "N₁, N₂",
    degeneracyMeaning: "band degeneracies",
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
      "known_issue.acphdis_band_weight":
        "With acPhDis, the band weight of the last temperature applies to all of S.",
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
    limitedRangeSummary: (symbol: string, minK: string, maxK: string) =>
      `${symbol} only ${minK}–${maxK} K`,
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
    valueUnits: { K: "K", eV: "eV", m_e: "mₑ" },
    boundsRange: (lower: string, upper: string) => `${lower} … ${upper}`,
    noBounds: "—",
    atBound: "at bound",
    atBoundNote:
      "A value at a bound may have been set by that bound, not by the data.",
    moreGraphs: "More graphs",
    openResults: "Open results",
  },
  export: {
    data: "Data to file",
    parameters: "Parameters to file",
    graph: (graph: string) => `Download the data of ${graph}`,
    failed:
      "The file could not be made, as the server did not answer. Try again.",
    dataFile: "seeband-data.txt",
    parametersFile: "seeband-parameters.txt",
    graphFile: (graph: string) => `seeband-${graph}.txt`,
    header: {
      app: (app: string, api: string | null) =>
        api === null ? `SeeBand Web ${app}` : `SeeBand Web ${app}, API ${api}`,
      date: (date: string) => `Exported ${date}`,
      demo: "Demo data: synthetic, made with the DPB model and noise. Not a measurement.",
      model: (model: string, mode: string) =>
        `Model ${model}, fit mode ${mode}`,
      scattering: (scattering: string) => `Scattering ${scattering}`,
      range: (minK: string, maxK: string) => `Fit range ${minK}-${maxK} K`,
      limitedRange: (quantity: string, minK: string, maxK: string) =>
        `Interpolated ${quantity} only over ${minK}-${maxK} K, where its data end`,
      degeneracies: (n1: string, n2: string) =>
        `Band degeneracies N1 = ${n1}, N2 = ${n2}`,
      fit: (status: string, iterations: number | null) =>
        iterations === null
          ? `Fit ${status}`
          : `Fit ${status}, ${String(iterations)} iterations`,
      noFit: "No fit: the values are those on the screen",
      running: (iteration: number | null) =>
        iteration === null
          ? "A fit is running: no fitted curve yet"
          : `A fit is running, at iteration ${String(iteration)}: no fitted curve yet`,
      failed: "The fit failed: no fitted curve",
      issue: (severity: string, issue: string, id: string) =>
        `${severity}: ${issue} (${id})`,
    },
    columns: {
      temperature: "Temperature [K]",
      experimental: (quantity: string) => `Experimental ${quantity}`,
      interpolated: (quantity: string) => `Interpolated ${quantity}`,
      preFit: (quantity: string) => `Pre-fit ${quantity}`,
      fit: (quantity: string) => `Fit ${quantity}`,
    },
    // As the desktop names them, in SI units.
    quantities: {
      seebeck: "Seebeck coefficient [V/K]",
      resistivity: "electrical resistivity [Ohm*m]",
      hall: "Hall coefficient [m^3/C]",
    },
    // Each column of an additional graph. Any other keeps the API's name, which states its unit.
    curves: {
      electrical_conductivity_s_per_m: "Electrical conductivity [S/m]",
      thermal_conductivity_w_per_m_k:
        "Electronic thermal conductivity [W/(m*K)]",
      seebeck_v_per_k: "Total Seebeck coefficient [V/K]",
      seebeck_band_1_v_per_k: "Seebeck coefficient of band 1 [V/K]",
      seebeck_band_2_v_per_k: "Seebeck coefficient of band 2 [V/K]",
      carrier_concentration_band_1_per_cm3:
        "Carrier concentration of band 1 [1/cm^3]",
      carrier_concentration_band_2_per_cm3:
        "Carrier concentration of band 2 [1/cm^3]",
    },
    // Curves of an energy, which the API gives in K, in the unit the screen shows them in.
    energyCurves: {
      chemical_potential_k: (unit: string) => `Chemical potential [${unit}]`,
    },
    parameterColumns: "Parameter\tValue\tStatus",
    parameterCsvColumns: "parameter,symbol,meaning,unit,value,status",
    parametersCsvFile: "seeband-parameters.csv",
    parameterFormats: {
      data: {
        label: "Text",
        text: "A line for each parameter, with its unit and status, as the desktop's file has them.",
      },
      csv: {
        label: "CSV, one table",
        text: "A row for each parameter, N1 and N2 included, for pandas or R.",
      },
    },
    parameter: (symbol: string, meaning: string, unit: string) =>
      unit === ""
        ? `${symbol} (${meaning})`
        : `${symbol} (${meaning}) [${unit}]`,
    status: {
      fitted: "fitted",
      fixed: "fixed",
      held: "held at its value",
      atBound: "fitted, at bound",
      free: "not fitted yet",
    },
    // A unit as a file writes it, plain text.
    units: {
      m_e: "m_e",
      K: "K",
      eV: "eV",
      dimensionless: "",
      unknown: "unit not known",
    },
    quantityUnits: { seebeck: "V/K", resistivity: "Ohm*m", hall: "m^3/C" },
    dialogText:
      "Every file starts with lines on the fit and its known issues. Values are in SI, with a decimal point.",
    parametersDialogText:
      "Every file starts with lines on the fit and its known issues. Values are as the screen shows them, with a decimal point.",
    format: "Format",
    download: "Download",
    close: "Close",
    formats: {
      data: {
        label: "Text",
        text: "Pairs of temperature and value columns for each quantity, for a spreadsheet or Origin.",
      },
      csv: {
        label: "CSV, one table",
        text: "A row for each point, with its quantity, curve and unit, for pandas or R.",
      },
      zip: {
        label: "ZIP, a file each",
        text: "Plain tables of the data, curves, parameters and additional graphs. The app loads the data and curves again.",
      },
    },
    csvFile: "seeband-data.csv",
    zipFile: "seeband-export.zip",
    csvColumns: "quantity,curve,temperature_k,value,unit",
    // Names the app's parser reads, so that a file of them loads again.
    readable: {
      temperature: "T [K]",
      seebeck: "S [V/K]",
      resistivity: "rho [Ohm*m]",
      hall: "R_H [m^3/C]",
    },
    zip: {
      metadata: "metadata.txt",
      parameters: "parameters.txt",
      data: (quantity: string, interpolated: boolean) =>
        interpolated
          ? `data/${quantity}-interpolated.txt`
          : `data/${quantity}.txt`,
      preFit: "curves/pre-fit.txt",
      fit: "curves/fit.txt",
      graph: (kind: string) => `graphs/${kind}.txt`,
      missing: (file: string) =>
        `Not in this ZIP: ${file}, as its curve could not be asked for`,
    },
  },
  report: {
    button: "Report (PDF)",
    preparing: "Preparing…",
    failed: "The report could not be prepared. Try again.",
    title: "SeeBand Web report",
    made: (date: string, app: string, api: string | null) =>
      api === null
        ? `Made ${date} with SeeBand Web ${app}`
        : `Made ${date} with SeeBand Web ${app}, API ${api}`,
    data: "Data",
    file: (
      symbol: string,
      name: string,
      points: number,
      minK: number,
      maxK: number,
    ) =>
      `${symbol}: ${name}, ${String(points)} points, ${String(minK)}–${String(maxK)} K`,
    charts: "Charts",
    chartAlt: (title: string) => `Chart: ${title}`,
    notDrawn: (reason: string, detail: string) =>
      `not drawn. ${reason}: ${detail}`,
    waiting: "The report waits for the curves.",
    preparingStatus: "Preparing the report's charts…",
    legend: (labels: readonly string[]) => labels.join(" · "),
  },
  results: {
    pageTitle: "Results",
    title: "Results",
    noFit: "No fit for the current values. Run one on the model fit page.",
    noValue: "—",
    summary: (parts: readonly string[]) => parts.join(" · "),
    modeLabel: (symbols: readonly string[]) => symbols.join(" + "),
    issue: (severity: string, issue: string) => `${severity}: ${issue}`,
    running: "A fit is running. Its results appear here once it ends.",
    noValues: "The last fit gave no values. The model fit page says why.",
    toFit: "Run a fit",
    model: "Model",
    scattering: "Scattering",
    rmse: (symbol: string) => `RMSE ${symbol}`,
    inRange: "in the fit range",
    noRmse: "needs measurements",
    rmseCalculating: "calculating…",
    rmseFailed: "could not be calculated",
    iterations: "Iterations",
    parametersTitle: "Fit parameters",
    parametersSubtitle:
      "The values in use, with what they mean and how they were found",
    parameterTable: "Fit parameters",
    columns: {
      parameter: "Parameter",
      meaning: "Meaning",
      value: "Value",
      bounds: "Bounds",
      status: "Status",
    },
    status: {
      fitted: "fitted",
      fixed: "fixed",
      held: "held",
      needs: (symbols: string) => `needs ${symbols}`,
    },
    notes: "Notes",
    graphs: {
      title: "Additional graphs",
      subtitle: "From the values in use, for the fit mode and scattering",
    },
    log: {
      title: "Fit log",
      subtitle: "The solver runs of this fit, in their order",
      start: "Start values",
      fromNet: (minK: string, maxK: string) =>
        `The neural net's guess, from its net for ${minK}–${maxK} K`,
      fromNumerical: "Numerical estimate from S(T)",
      fromValues: "The values on the fit screen",
      stage: (symbol: string) => `Fit to ${symbol}`,
      finds: (symbols: string) => `Finds ${symbols}`,
      findsEach: (symbols: string, iterations: number) =>
        `Finds ${symbols}, in each of ${String(iterations)} ${iterations === 1 ? "iteration" : "iterations"}`,
      converged: "Converged",
      convergedText: "The fit met its stop rule.",
      convergedBelow: (percent: string, iterations: number | null) =>
        iterations === null
          ? `The fit met its stop rule, a change of at most ${percent} %.`
          : `The fit met its stop rule, a change of at most ${percent} %, in iteration ${String(iterations)}.`,
      done: "Done",
      singlePass: "One pass: this fit mode does not iterate.",
      limit: "Iteration limit",
      limitText: (limit: number) =>
        `The fit reached its limit of ${String(limit)} iterations before every parameter settled.`,
      stopped: "Stopped",
      stoppedText: "Stopped by the user.",
      stoppedAt: (iteration: number) =>
        `Stopped by the user after iteration ${String(iteration)}.`,
    },
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
