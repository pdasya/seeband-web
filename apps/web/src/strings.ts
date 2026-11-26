/**
 * Every text the app shows, in one place until U3 brings i18n.
 *
 * Add new text here rather than in a component, so that U3 can move it all at once.
 */
export const STRINGS = {
  explicitDpb: {
    unoccupiedBands:
      "For VB + VB, set E_F below the higher valence-band edge. For CB + CB, set E_F above the lower conduction-band edge.",
    carrierMismatch:
      "The chosen E_F gives the opposite carrier excess to the session's carrier type. Adjust E_F.",
    fermiRepresentation: "Explicit bands · Fermi energy",
    carrierType: "Carrier type",
    fermiHint:
      "Set E_F relative to Band 1 in Parameters. For VB + CB, E_F may lie inside the band gap.",
    fermiIdentity: (configuration: string, carrier?: string) =>
      `Parameterization: explicit_fermi_v1; configuration: ${configuration}${carrier === undefined ? "" : `; carrier type: ${carrier}`}`,

    representation: "Explicit bands · fixed carrier excess",
    representationLabel: "Representation",
    densityMeaning: "Signed net electron density n − p",
    verifiedMethod: "Explicit bands use the verified joint method.",
    configuration: "Band configuration",
    bandLabel: (band: number, kind: string) => `Band ${band} (${kind})`,
    configurations: { vb_vb: "VB + VB", vb_cb: "VB + CB", cb_cb: "CB + CB" },
    density: "Net electron density n − p (m⁻³)",
    densityMagnitude: "Carrier excess magnitude |n − p| (m⁻³)",
    densityAbout: "About carrier excess",
    polarity: "Carrier excess polarity",
    p: "p",
    n: "n",
    polarities: { p: "p: excess holes", n: "n: excess electrons" },
    densityTooltip:
      "The signed net electron density n − p must remain fixed across the temperature sweep. The separate electron density n and hole density p may each vary with temperature. Choose p for excess holes (n − p < 0), or n for excess electrons (n − p > 0), then enter the nonnegative magnitude |n − p| in m⁻³ (per cubic metre). VB + CB permits either polarity and zero, where n = p. VB + VB requires p and CB + CB requires n; both same-type configurations require a positive magnitude.",
    branchDensityHints: {
      vb_vb:
        "VB + VB requires p: n − p = −|n − p|. The branch selects this sign and preserves the magnitude.",
      vb_cb: "VB + CB permits p or n, including intrinsic zero (n = p).",
      cb_cb:
        "CB + CB requires n: n − p = +|n − p|. The branch selects this sign and preserves the magnitude.",
    },
    densityRequired:
      "Enter a positive concentration for two bands of the same type.",
    invalidMagnitude: "Enter a finite, nonnegative carrier excess magnitude.",
    intrinsic: (polarity: "p" | "n") =>
      `Intrinsic: n = p (n − p = 0 m⁻³). Next nonzero excess: ${polarity === "p" ? "holes (p)" : "electrons (n)"}.`,
    zeroSameType:
      "n − p = 0 m⁻³; a positive magnitude is required for this configuration.",
    signedDensity: (polarity: "p" | "n", magnitude: string) =>
      `n − p = ${polarity === "p" ? "−" : "+"}${magnitude} m⁻³ (${polarity})`,
    migrationTitle: "Convert historical DPB session",
    migrationHint:
      "Confirm the positive single-valley mass and both valley multiplicities, excluding spin. Saved multiplicities may have been defaults. Original inputs and fit results are preserved; new fits use fresh bounds.",
    mass: "Single-valley |m₁| (mₑ)",
    hallMassConvention: "Saved Hall mass convention",
    chooseHallMassConvention: "Choose the saved mass convention",
    singleValleyMass: "Single-valley mass",
    allValleyMass: "All-valley density-of-states mass",
    savedHallMass: (mass: string, multiplicity: string) =>
      `Saved Hall |m₁|: ${mass} mₑ; saved N₁: ${multiplicity}.`,
    hallMassHint:
      "Confirm the convention used when this mass was saved. Core version 0.3.0 alone does not identify it. An all-valley mass is divided by the saved N₁^(2/3); the single-valley value used for conversion is shown below. This converts the saved point and does not guarantee reproduction of older Hall curves.",
    confirm: "Confirm scale and convert",
    cancel: "Cancel",
    migrationFailed:
      "Conversion failed. Check the legacy mass ratio and absolute scale, then retry.",
    legacyResult:
      "Original historical session and fit (legacy parameterization)",
    identity: (configuration: string, density: number) =>
      `Parameterization: explicit_density_v1; configuration: ${configuration}; net electron density: ${density} m⁻³`,
  },
  appName: "SeeBand",
  // The link that the header's logo and name make, for a screen reader.
  appHomeLabel: "SeeBand, overview",
  appStage: "web · prototype",
  skipToContent: "Skip to content",
  navigation: {
    label: "Sections",
    overview: "Overview",
    fit: "Model fit",
    results: "Results",
    conventions: "Conventions",
    guide: "Guide",
  },
  parameters: {
    title: "Parameters",
    fixed: "not fitted",
    held: "held",
    hold: (symbol: string) => `Hold ${symbol} at its value in a fit`,
    carried: (symbols: string, model: string) =>
      `${symbols} taken from ${model}, with any bounds and holds.`,
    fermiReference:
      "E_F counts from the band edge in SPB and from the top of band 1 in DPB, so check it.",
    about: (symbol: string) => `About ${symbol}`,
    // How a parameter is written. Any other shows its name, so a new one needs no change here.
    symbols: {
      band_mass: "m",
      mass_ratio: "m₂/m₁",
      band_offset_k: "Δ",
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
      ionized: "Ionized impurities",
    },
    disabledReason: "not available until a known error is fixed.",
    disabledReasons: {},
    degeneracyHint:
      "Valley multiplicities are positive integers and are not fitted.",
    degeneracyInvalid:
      "N₁ and N₂ must be positive integers. The last valid value stays in use.",
    range: "Fit range, K",
    rangeMin: "Lower bound, K",
    rangeMax: "Upper bound, K",
    rangeInvalid:
      "The lower bound must be below the upper, and both above 0 K. The last valid range stays in use.",
  },
  runs: {
    title: "Earlier runs",
    subtitle: (count: number) =>
      `${String(count)} fits of this session, each as it ended. Choose two to compare.`,
    oneRun: "One fit of this session so far. Run another to compare the two.",
    note: "Fits of this session, each kept as it was when it ended. Only a run marked as the current result is the result of the values now on the fit screen; the others are earlier fits.",
    runName: (number: number, time: string, what: string, current: boolean) =>
      `Run ${String(number)}, ${time}` +
      (what === "" ? "" : ` · ${what}`) +
      (current ? " · current result" : ""),
    runA: "Run A",
    runB: "Run B",
    table: "Runs compared",
    what: "Property",
    mode: "Fit mode",
    scattering: "Scattering",
    noScattering: "none",
    range: "Fit range",
    rangeValue: (low: string, high: string) => `${low}–${high} K`,
    interpolation: "Interpolation",
    on: "on",
    off: "off",
    method: "Fitting method",
    coreVersion: "Core version",
    status: "Status",
    iterations: "Iterations",
    rmse: (symbol: string) => `RMSE ${symbol}`,
    none: "–",
    dashNote:
      "– : the run's mode or scattering has no such parameter, or the value is not known.",
    notOffered: "not offered by this server",
    sameRun: "Run A and run B are the same run. Choose another to compare.",
    otherPoints:
      "These runs were fit to different points: other data, another fit range, or interpolation. Their RMSE and parameters are not of the same points, and each chart shows the points of each.",
    bothRuns: "both runs",
    pointsOf: (run: string) => `Points fitted, ${run}`,
    chartDescription: (quantity: string, a: string, b: string) =>
      `${quantity} against temperature: the points each run was fit to, the curve of ${a} as a solid line, and that of ${b} dashed.`,
    curveFailed:
      "The curve of a run could not be calculated, so its RMSE and curve are missing.",
  },
  session: {
    archivedDpb:
      "Historical DPB settings are archived with the original session. Switching to DPB starts fresh explicit bands; the active SPB settings and result stay in use. To convert a historical DPB state, save that state with DPB selected in the original application, then open that file here.",
    open: "Open session",
    openHint:
      "Load a session file saved with Session to file, in place of this session",
    waitFirst:
      "A fit or a file is on its way. Let it finish, or stop it, before opening a session.",
    opening: "Opening the session file…",
    problems: {
      too_large: "This session file is too large to open.",
      not_json: "This file is not a session file: it is not JSON.",
      not_a_session: "This file is not a SeeBand session file.",
      newer_version:
        "This session file comes from a newer version of SeeBand Web. Open it there.",
      invalid:
        "This session file is damaged, or misses parts, so it was not opened.",
      checksum:
        "The contents of this session file do not match the checksum stored with them, so it is damaged or was edited, and was not opened.",
      read_failed: "This file could not be read.",
    },
    restored: (saved: string, app: string) =>
      `Opened from a session file saved ${saved} with SeeBand Web ${app}.`,
    restoredFit: (core: string) =>
      `Its fit is shown as it was, from core ${core}; nothing was fitted again.`,
    otherCore: (core: string) =>
      `This server runs core ${core}, which draws the curves. Run the fit again to compare.`,
    coreUnknown:
      "The server did not say which core it runs, so whether it draws the curves with the fit's own is not known.",
    stale:
      "The fit in the file used other inputs than this server gives now, as it can interpolate otherwise or no longer offer the mode, so it is not shown. Run the fit again.",
  },
  data: {
    title: "Data",
    subtitle: {
      separate:
        "Each file: T and the value, in the units its header names or the ones you choose. With neither: T in K, S in V/K, ρ in Ω·m or σ in S/m, R_H in m³/C.",
      single:
        "One table: a column for T, and for each quantity, in the units its header names or the ones you choose. With neither: T in K, S in V/K, ρ in Ω·m or σ in S/m, R_H in m³/C.",
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
      checkUnit: (symbol: string, points: number) =>
        `${symbol} · ${String(points)} pts · check the unit`,
      checkTemperature: "T · check the unit",
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
    readAsLabel: "Load σ instead",
    readAsNote: "The fit uses ρ = 1/σ, which the server computes.",
    unitGroups: { metre: "Per metre", centimetre: "Per centimetre" },
    readAsInverse: "read as ρ = 1/σ",
    /** The symbol of ρ where it is 1/σ of a σ file, as an RMSE of it compares with 1/σ. */
    inverseSigma: "ρ = 1/σ",
    belowZeroForSigma:
      "Some values are 0 or below, which a conductivity cannot have.",
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
    serverBusy:
      "The server is busy with other calculations, so the file was not read. Try again shortly.",
    uploadTooSlow:
      "The file took too long to send. Check the connection and try again.",
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
      "mV/K": "mV/K",
      "Ohm*m": "Ω·m",
      "Ohm*cm": "Ω·cm",
      "mOhm*cm": "mΩ·cm",
      "uOhm*m": "µΩ·m",
      "uOhm*cm": "µΩ·cm",
      "S/m": "S/m",
      "S/cm": "S/cm",
      "m^3/C": "m³/C",
      "cm^3/C": "cm³/C",
    },
    unitOf: (name: string) => `Unit of ${name}`,
    temperature: "Temperature",
    inSi: (written: string, si: string) => `${written} = ${si} in SI`,
    checkUnitTitle: "Check the unit",
    confirmUnit: "Values are right",
    /** The button's name, which starts with its text and says whose values it confirms. */
    confirmUnitOf: (symbols: string) => `Values are right for ${symbols}`,
    unitConfirmed:
      "You confirmed these values despite the unit check, so a fit uses them as they are.",
    /** The name of a unit select whose unit is SI only because nothing named one. */
    unitAssumedOf: (name: string, unit: string) =>
      `Unit of ${name}: ${unit}, assumed`,
    firstRow: (values: string) => `First row: ${values}`,
    temperatureRanges: {
      title: "Check the unit of T",
      shifted: (lower: string, higher: string, lowerSymbol: string) =>
        `T of ${lower} is about 273 K below T of ${higher} at both ends, as when T in °C is read as K. If the file of ${lowerSymbol} gives T in °C, choose °C for its T. If both give T in K, nothing needs to change.`,
    },
    // Which way a wrong unit most likely went, by quantity, when values read in SI look far off.
    // Values far outside a quantity's usual size, by which limit they pass. Only a hint names a
    // unit to choose, where the usual lab unit read as SI would give that side.
    implausible: {
      size: { above: "larger", below: "smaller" },
      names: {
        seebeck: "Seebeck coefficient",
        resistivity: "resistivity",
        conductivity: "conductivity",
        hall: "Hall coefficient",
      },
      inSi: (size: string, name: string, unit: string) =>
        `These values are far ${size} than any usual ${name} in ${unit}, the unit assumed.`,
      hints: {
        seebeck: { above: "If the file is in µV/K or mV/K, choose it." },
        resistivity: {
          above:
            "If the file is in Ω·cm, mΩ·cm, µΩ·m or µΩ·cm, choose it. If the column holds σ, remove the file and load it as σ instead. Each unit gives other values in SI, so check the first row.",
        },
        conductivity: { below: "If the file is in S/cm, choose S/cm." },
        hall: { above: "If the file is in cm³/C, choose cm³/C." },
      } as Partial<Record<string, Partial<Record<"above" | "below", string>>>>,
      checkColumn:
        "Check that the column holds this quantity, and the unit its values are in.",
      inChosenUnit: (size: string, unit: string) =>
        `These values are far ${size} than any usual size in ${unit}, the unit chosen. Check that the file is in ${unit}, or choose the unit it is in.`,
      inHeaderUnit: (size: string, unit: string) =>
        `These values are far ${size} than any usual size in ${unit}, the unit the header names. Check the file: its header may name the wrong unit.`,
    },
    quantities: {
      seebeck: { symbol: "S", title: "Seebeck coefficient", unit: "V/K" },
      resistivity: { symbol: "ρ", title: "Resistivity", unit: "Ω·m" },
      conductivity: { symbol: "σ", title: "Conductivity", unit: "S/m" },
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
      non_positive_conductivity:
        "A conductivity of 0 or below, which has no resistivity.",
      resistivity_and_conductivity:
        "A file can hold ρ or σ, not both. Choose one of them.",
      repeated_role: "A quantity is assigned twice.",
      preamble_skipped: "A line of text before the header was left out.",
      header_mismatch: "The header has a different number of columns.",
      unit_differs: "A column in a unit SeeBand cannot read was not used.",
      unit_assumed:
        "Its header names a unit SeeBand cannot read, so the values are read in SI. Choose the unit they are in, or convert the column to one listed here.",
      unit_not_allowed: "This unit does not fit the quantity of this column.",
      implausible_magnitude:
        "These values are far from any usual size for this quantity. Check the unit of this column.",
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
      lorenz_number: "Lorenz number L(T)",
      bands: "Band contributions",
      carrier_concentration: "Carrier concentration by band",
      band_diagram: "Band diagram E(k)",
    },
    panelLabel: (index: number) => `Chart ${String(index)}`,
    panelSelect: (index: number) => `Quantity shown in chart ${String(index)}`,
    bandGapMetric: (gap: string, unit: string) => `E_g = ${gap} ${unit}`,
    conductivityDescription: "Chart of σ against temperature",
    conductivityPoints: "1/ρ of the data",
    conductivityPointsFromSigma: "σ data",
    conductivityPointsFromSigmaNote:
      "Points are the loaded σ data in the fit range, as 1/ρ of the ρ = 1/σ a fit uses. The line is the model's σ.",
    conductivityPointsInterpolated: "1/ρ of the interpolated data",
    conductivityPointsNote:
      "Points are 1/ρ of the ρ data in the fit range, which the server calculates. The line is the model's σ.",
    conductivityNote:
      "The model's σ only: measured points would be 1/ρ, which the ρ data give.",
    diagramCurves: {
      band_1_energy_k: "Band 1",
      band_2_energy_k: "Band 2",
      fermi_energy_k: "E_F",
      fermi_energy_lower_k: "E_F lower endpoint",
      fermi_energy_upper_k: "E_F upper endpoint",
    },
    wavevectorAxis: "k",
    diagramDescription: "Local parabolic band energies against wavevector",
    diagramShape: "The diagram shows the shape of the bands; k has no scale.",
    diagramReferenceMass:
      "The curvature scale is illustrative. Without Hall data the size of band 1's mass is not set by the data, so it is assumed to be mₑ.",
    wavevectorWithUnit: (unit: string) => `k (${unit})`,
    axes: {
      seebeck: "S, µV/K",
      resistivity: "ρ, µΩ·m",
      hall: "R_H, m³/C",
      chemicalPotential: (unit: string) => `μ, ${unit}`,
      energy: (unit: string) => `E, ${unit}`,
      conductivity: "σ, S/m",
      thermalConductivity: "κ_e, W/(m·K)",
      lorenz: "L / L₀",
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
    band1Edge: "band 1 edge",
    band2Edge: "band 2 edge (Δ)",
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
    lorenz: "L",
    lorenzEffective: "Effective L = κ_e/(σT)",
    lorenzDescription:
      "Chart of the Lorenz number against temperature, in units of L₀",
    lorenzNote:
      "L = κ_e/(σT), in units of L₀ = π²/3 (k_B/e)² = 2,44 × 10⁻⁸ W·Ω/K². It tends to L₀ for a degenerate band, and for a nondegenerate one to 2 (k_B/e)² with acoustic phonons or alloy disorder and to 4 (k_B/e)² with ionized impurities.",
    lorenzTwoBandsNote:
      "The solid line is the effective L = κ_e/(σT), with the bipolar part, which can rise far above either band's; the dashed lines are each band's own L. All in units of L₀ = π²/3 (k_B/e)² = 2,44 × 10⁻⁸ W·Ω/K².",
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
    measurementsFromSigma: "1/σ of the σ data",
    resistivityFromSigmaNote:
      "Points are 1/σ of the loaded σ data, which the server calculates. The fit and its RMSE use them as ρ.",
    interpolated: "Interpolated",
    updating: "Updating…",
    lastCurveStays: "The last curve stays on the chart.",
    noResult: "The calculation has no result for these parameters.",
    calculationDetails: {
      chemical_potential_zero_mass:
        "The calculation needs a nonzero band mass in SPB or a nonzero mass ratio m₂/m₁ in DPB.",
      chemical_potential_spb_fermi_energy:
        "At T = 0 this band has no carriers with these values. Set E_F above 0 for m > 0 or below 0 for m < 0.",
      chemical_potential_dpb_fermi_energy:
        "At T = 0 neither valence band has hole carriers with these values. Set E_F below the higher band edge, max(0, E_g).",
      no_chemical_potential:
        "The model has no finite chemical potential for these band parameters.",
    },
    rateLimited: "Too many updates in a short time. Trying again shortly.",
    rateLimitedWait:
      "Too many updates in a short time. Change a value to try again.",
    busy: "The server is busy with other calculations. Trying again shortly.",
    networkError: "The server could not be reached.",
    serverUnavailable: "The server is not responding.",
    calcFailed: "The curve could not be calculated.",
  },
  status: {
    running: "Fitting…",
    settled: "Numerically settled",
    stalled: "Numerical fit stalled",
    converged: "Stopped by its rule",
    // A single-pass legacy fit: its solver returned, with no rule of the fit's own to name.
    finished: "Solver finished",
    iterationLimit: "Iteration limit reached",
    stopped: "Stopped",
    failed: "Failed",
    suggested: "Initial guess",
  },
  fit: {
    algorithm: {
      label: "Fitting method",
      ionizedVerified: "Ionized impurity fitting uses the verified method.",
      verified: "Verified sequential",
      legacy: "Legacy sequential (reproduce earlier results)",
      unknown: "Unknown",
      provenance: (algorithm: string) => `Fitting method: ${algorithm}`,
    },
    diagnostics: {
      title: "Numerical diagnostics",
      terminationReasons: {
        conditional_stage_optima: "Conditional stage optima reached",
        cycle_or_stall: "Cycle or stall detected",
        derivative_search_stall:
          "A better trial could not pass derivative validation",
        callback: "Stopped by request",
        sweep_budget: "Iteration budget reached",
        evaluation_budget: "Evaluation budget reached",
        numerical_failure: "Numerical failure",
      },
      otherTermination: "Other numerical stop",
      consistent: "Stages consistent at the returned parameters",
      inconsistent: "Stages are not consistent at the returned parameters",
      termination: (reason: string) => `Termination: ${reason}`,
      effort: (evaluations: number, recoveries: number) =>
        `${String(evaluations)} evaluations; ${String(recoveries)} recoveries`,
      residual: (
        quantity: string,
        rmse: string,
        unit: string,
        relative: string,
      ) => `${quantity}: RMSE ${rmse} ${unit}; relative L2 ${relative}`,
      residualInputs:
        "Fit-input residuals (including interpolated points when used)",
      unavailable: "not defined for a zero signal",
      unidentified: (names: string) => `Not identified: ${names}`,
      notAssessed:
        "Physical adequacy and parameter uncertainty have not been assessed.",
      stalled:
        "The numerical fit stalled. These are usable endpoint values, not a converged result.",
      settled:
        "The numerical stop criteria were met; physical adequacy and uncertainty have not been assessed.",
    },
    pageTitle: "Model fit",
    data: "Data",
    charts: "Charts",
    result: "Result",
    panelTitle: "Fit",
    guess: "Initial guess",
    guessHint:
      "Estimate band parameters from S(T), replacing free manual starts; held and fixed values and SPB mass magnitudes are preserved",
    guessUnsupported: {
      scattering_not_supported:
        "The DPB neural estimate is unavailable for ionized impurities. Set start values manually.",
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
    guessUnitInDoubt:
      "Check the unit of S first, or confirm under Data that its values are right",
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
        "The rows were not in order of T, so they were sorted first.",
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
    stopRule: (percent: string) =>
      `(each parameter changed by at most ${percent} % in the last iteration)`,
    resultFailed: "The fit could not finish. Change the values, and try again.",
    // The API's fixed text for a fit that ends without a result.
    resultFailures: {
      "The start values do not fit the bounds.":
        "The start values do not fit the bounds.",
      "The model gave values that are not finite during the fit.":
        "The model gave values that are not finite during the fit.",
      "The fit encountered band parameters with no finite chemical potential.":
        "The fit encountered band parameters with no finite chemical potential. Check the band parameters and their bounds.",
      "The chemical-potential balance could not be verified during the fit.":
        "The fit could not verify the chemical-potential balance to numerical precision.",
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
      unitInDoubt: (symbols: string) =>
        `Check the unit of ${symbols} first, or confirm under Data that the values are right.`,
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
      "known_issue.dpb_loop_degeneracy":
        "In the legacy method with N₂/N₁ other than 1, the fit returns m₂/m₁ times N₂/N₁, so the value shown can leave its bounds. The bounds and the at-bound mark apply before that factor.",
      "known_issue.collapsed_m_eff":
        "With m₂/m₁ near 0, the fit can be poorly conditioned. The data may not determine the band parameters separately, and results can differ between machines.",
      "known_issue.fermi_energy_in_gap":
        "The 0 K Fermi energy is in the DPB gap or at one of its edges. The transport data cannot determine where E_F is within this gap: with the other parameters fixed, every value in the gap gives the same S, ρ and R_H.",
      "known_issue.no_chemical_potential":
        "When E_F is at the band edge or outside the band, SPB has zero carrier density at T = 0 and cannot calculate a curve.",
      "known_issue.hall_dis_no_reference":
        "This fit fails on the desktop, and runs here with other bounds of G, so there is no desktop result to compare with.",
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
      unknownVersion: "unknown",
      serverCore: (version: string) => `Export server core ${version}`,
      fitCore: (version: string) => `Fit core ${version}`,
      curveCore: (version: string) => `Curve core ${version}`,
      // The API's as it was when the file was made, which a server deployed since a fit changes.
      app: (app: string, api: string | null) =>
        api === null
          ? `SeeBand Web ${app}`
          : `SeeBand Web ${app}, API ${api} when exported`,
      algorithmChosen: (algorithm: string) =>
        `Fitting method chosen, no fit ran with it: ${algorithm}`,
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
      fromConductivity:
        "rho is 1/sigma of the loaded conductivity data, so its RMSE compares the fit with 1/sigma",
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
      experimentalFromSigma: (quantity: string) =>
        `Experimental ${quantity}, 1/sigma of the loaded conductivity`,
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
      lorenz_number_w_ohm_per_k2:
        "Lorenz number L = kappa_e/(sigma*T) [W*Ohm/K^2]",
      lorenz_number_band_1_w_ohm_per_k2: "Lorenz number of band 1 [W*Ohm/K^2]",
      lorenz_number_band_2_w_ohm_per_k2: "Lorenz number of band 2 [W*Ohm/K^2]",
      seebeck_v_per_k: "Total Seebeck coefficient [V/K]",
      seebeck_band_1_v_per_k: "Seebeck coefficient of band 1 [V/K]",
      seebeck_band_2_v_per_k: "Seebeck coefficient of band 2 [V/K]",
      carrier_concentration_band_1_per_cm3:
        "Carrier concentration of band 1 [1/cm^3]",
      carrier_concentration_band_2_per_cm3:
        "Carrier concentration of band 2 [1/cm^3]",
    },
    relativeToL0: (column: string) =>
      `${column.replace(/ \[W\*Ohm\/K\^2\]$/, "")} / L0, L0 = pi^2/3 (k_B/e)^2 = 2.44e-8 W*Ohm/K^2`,
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
      found: {
        estimated: "estimated",
        at_bound: "at bound",
        not_determined: "not determined by the data",
        did_not_move: "did not move from its start",
        not_assessed: "not assessed",
      },
      fixed: "fixed",
      held: "held at its value",
      free: "not fitted yet",
      freeAfterFailure: "not fitted: the fit failed",
    },
    uncertaintyNote:
      "The uncertainty of the values is not assessed. Estimated means only that the fit gave no sign of a problem with a value, not that the data determine it.",
    // What a run used, so that it can be made again.
    run: {
      demo: "demo data",
      file: (name: string) => `file "${name}"`,
      temperature: "T",
      conductivity: "σ",
      column: (role: string, column: number, unit: string, from: string) =>
        `${role} in column ${String(column)}, in ${unit} (${from})`,
      unitNotNamed: "a unit not named",
      sourceUnknown: "where the unit came from is not known",
      unitSource: {
        chosen: "chosen by the user",
        header: "named in the file's header",
        default: "SI, as nothing named a unit",
      },
      input: (quantity: string, source: string, columns: string) =>
        columns === ""
          ? `Input ${quantity}: ${source}`
          : `Input ${quantity}: ${source}; ${columns}`,
      doubt: (quantity: string, message: string, confirmed: boolean) =>
        confirmed
          ? `Unit in doubt for ${quantity}, and the user confirmed the values: ${message}`
          : `Unit in doubt for ${quantity}, not confirmed: ${message}`,
      interpolationOn: "Interpolation on",
      interpolationOff: "Interpolation off",
      interpolationFailed: (quantities: string) =>
        `Interpolation failed for ${quantities}, so a fit cannot use their data until it works or is turned off`,
      points: (quantity: string, points: number, inRange: number | null) =>
        inRange === null
          ? `${quantity}: ${String(points)} measured points`
          : `${quantity}: ${String(points)} measured points, ${String(inRange)} within the fit range`,
      values: (values: string) => `Values in use: ${values}`,
      fromNet: (minK: string, maxK: string) =>
        `the neural net's guess from its net for ${minK}-${maxK} K where it gave a value, else the fit screen`,
      fromNumerical:
        "the numerical estimate from S(T) where it gave a value, else the fit screen",
      fromScreen: "the values on the fit screen",
      start: (source: string, values: string) =>
        `Start values, from ${source}: ${values}`,
      bound: (symbol: string, lower: string, upper: string, custom: boolean) =>
        `${symbol} ${lower} to ${upper}${custom ? " (set by the user)" : ""}`,
      bounds: (bounds: string) => `Bounds: ${bounds}`,
      held: (symbols: string) => `Held at their values: ${symbols}`,
      massBranch:
        "The legacy loop also keeps m2/m1 on the sign of its start, and with N2/N1 other than 1 its bounds apply to m2/m1 divided by N2/N1",
      rmse: (quantity: string, value: string, unit: string, fitted: boolean) =>
        `RMSE ${quantity} of the ${fitted ? "fitted curve" : "curve of the values in use"}: ${value} ${unit}`,
      notFinite: "not finite",
      rmseFailed:
        "RMSE not given: the server could not calculate the curve for it when this file was made",
      stopRule: (percent: string, limit: number | null) =>
        limit === null
          ? `Stop rule: each parameter of the loop changed by at most ${percent} % in an iteration`
          : `Stop rule: each parameter of the loop changed by at most ${percent} % in an iteration, within ${String(limit)} iterations`,
      lastChanges: (changes: string) =>
        `Relative changes the stop rule compared in the last iteration: ${changes}`,
      limitBands:
        "At the iteration limit the loop fits S once more after these changes, so m2/m1, E_g and E_F are from that last Seebeck stage",
      summary: (
        symbol: string,
        unit: string,
        temperature: string | null,
        doubt: "open" | "confirmed" | null,
      ) =>
        `${symbol} in ${unit}` +
        (temperature === null ? "" : `, T in ${temperature}`) +
        (doubt === null
          ? ""
          : doubt === "open"
            ? ", unit in doubt"
            : ", unit in doubt, confirmed"),
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
        text: "Plain tables of the data, curves, parameters and additional graphs, and the session file, which holds the full text of each data file. The app loads the data and curves again.",
      },
    },
    csvFile: "seeband-data.csv",
    zipFile: "seeband-export.zip",
    sessionFile: "seeband-session.json",
    session: "Session to file",
    sessionHint:
      "The data, with the full text of each file, the settings and the last fit, to load back later with Open session. Share it only as you would the files. Nothing is kept on the server.",
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
    run: "How the run was made",
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
      // How the fit found it. None of these says that a value is right.
      found: {
        estimated: "estimated",
        at_bound: "at bound",
        not_determined: "not determined by the data",
        did_not_move: "did not move from its start",
        not_assessed: "not assessed",
      },
      free: "not fitted yet",
      freeAfterFailure: "not fitted: the fit failed",
      fixed: "fixed",
      held: "held",
      needs: (symbols: string) => `needs ${symbols}`,
    },
    uncertaintyNote:
      "The uncertainty of the values is not assessed. “Estimated” means only that the fit gave no sign of a problem with a value, not that the data determine it.",
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
      converged: "Stopped by its rule",
      convergedText: "The fit met its stop rule.",
      convergedBelow: (percent: string, iterations: number | null) =>
        iterations === null
          ? `The legacy fit met its stop rule: each parameter of its loop changed by at most ${percent} %.`
          : `The legacy fit met its stop rule: each parameter of its loop changed by at most ${percent} % in iteration ${String(iterations)}.`,
      changes: (listed: string) =>
        `The changes in its last iteration: ${listed}.`,
      limitBands:
        "At the limit it fitted S once more after these, so m₂/m₁, E_g and E_F are from that last stage.",
      above: (percent: string, symbols: string) =>
        `Above ${percent} %: ${symbols}.`,
      notFinite: "not finite",
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
