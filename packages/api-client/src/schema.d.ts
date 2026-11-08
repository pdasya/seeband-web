export interface paths {
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Health */
        get: operations["get_health"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/models": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Models */
        get: operations["get_models"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/calc": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Post Calc */
        post: operations["post_calc"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/band-diagram": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Post Band Diagram */
        post: operations["post_band_diagram"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/parse": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Post Parse */
        post: operations["post_parse"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/guess": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Post Guess */
        post: operations["post_guess"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/fit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Post Fit */
        post: operations["post_fit"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/demo": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Demo */
        get: operations["get_demo"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * BandDiagramRequest
         * @description What to draw. `parameters` holds every parameter of the mode in core units, as in a curve.
         * @example {
         *       "fit_mode": "spb_s",
         *       "model": "spb",
         *       "parameters": {
         *         "band_mass": 1.01,
         *         "fermi_energy": 100
         *       }
         *     }
         */
        BandDiagramRequest: {
            /** Model */
            model: string;
            /** Fit Mode */
            fit_mode: string;
            /** Parameters */
            parameters: {
                [key: string]: number;
            };
            /**
             * Band 1 Degeneracy
             * @default 1
             */
            band_1_degeneracy?: number;
            /**
             * Band 2 Degeneracy
             * @default 1
             */
            band_2_degeneracy?: number;
        };
        /**
         * BandDiagramResponse
         * @description Curves over `wavevector`, by name, where null marks a value that is not finite.
         *
         *     Each name ends in its unit. `wavevector` has none, as the formula states none, and the desktop
         *     draws this axis with no ticks. `known_issues` names known errors, as in `GET /api/models`.
         * @example {
         *       "curves": {
         *         "band_1_energy_k": [
         *           1954.5,
         *           0,
         *           1954.5
         *         ],
         *         "fermi_energy_k": [
         *           100,
         *           100,
         *           100
         *         ]
         *       },
         *       "known_issues": [
         *         "band_diagram_formula"
         *       ],
         *       "wavevector": [
         *         -40,
         *         0,
         *         40
         *       ]
         *     }
         */
        BandDiagramResponse: {
            /** Wavevector */
            wavevector: number[];
            /** Curves */
            curves: {
                [key: string]: (number | null)[];
            };
            /** Known Issues */
            known_issues: string[];
        };
        /** BoundsInput */
        BoundsInput: {
            /** Lower */
            lower: number;
            /** Upper */
            upper: number;
        };
        /** BoundsResponse */
        BoundsResponse: {
            /** Lower */
            lower: number;
            /** Upper */
            upper: number;
        };
        /**
         * CalcRequest
         * @description What to calculate.
         *
         *     `parameters` holds every parameter of the mode in core units, including those of other
         *     scattering types. Values outside a control's range are allowed, as a fit can end there. `points`
         *     defaults to the model's. `measurements` gives an RMSE for each quantity, and should hold only
         *     points in the fit range. `extrapolated` says that interpolation made up some of these points.
         *
         *     `kind` chooses the curves, and `GET /api/models` lists which a mode offers. `measurements` need
         *     the `measured` kind, because the known issues of a response are those of its curves, and an RMSE
         *     of other curves would not carry its own.
         * @example {
         *       "fit_mode": "dpb_s_rho",
         *       "max_temperature_k": 500,
         *       "measurements": {
         *         "seebeck": {
         *           "temperature_k": [
         *             100,
         *             300,
         *             500
         *           ],
         *           "values": [
         *             0.0002,
         *             0.00009,
         *             0.00002
         *           ]
         *         }
         *       },
         *       "min_temperature_k": 100,
         *       "model": "dpb",
         *       "parameters": {
         *         "A": 40000,
         *         "B": 1,
         *         "C": 1,
         *         "D": 1,
         *         "F": 1000,
         *         "G": 1,
         *         "band_gap": 1000,
         *         "fermi_energy": -100,
         *         "m_eff": 1.01
         *       },
         *       "points": 5,
         *       "scattering": "acPh"
         *     }
         */
        CalcRequest: {
            /** Model */
            model: string;
            /** Fit Mode */
            fit_mode: string;
            /** Scattering */
            scattering?: string | null;
            /** Parameters */
            parameters: {
                [key: string]: number;
            };
            /** Min Temperature K */
            min_temperature_k: number;
            /** Max Temperature K */
            max_temperature_k: number;
            /**
             * Kind
             * @default measured
             * @enum {string}
             */
            kind?: "measured" | "seebeck" | "seebeck_by_band" | "chemical_potential" | "electrical_conductivity" | "electrical_conductivity_by_band" | "thermal_conductivity" | "carrier_concentration_by_band";
            /** Points */
            points?: number | null;
            /**
             * Band 1 Degeneracy
             * @default 1
             */
            band_1_degeneracy?: number;
            /**
             * Band 2 Degeneracy
             * @default 1
             */
            band_2_degeneracy?: number;
            /**
             * Extrapolated
             * @default false
             */
            extrapolated?: boolean;
            /** Measurements */
            measurements?: {
                [key: string]: components["schemas"]["MeasurementInput"];
            };
            /**
             * Rmse Points
             * @default 50
             */
            rmse_points?: number;
        };
        /**
         * CalcResponse
         * @description Curves by name, where each name ends in its unit, and null marks a value that is not finite.
         *
         *     `known_issues` names known errors that apply to this result, as in `GET /api/models`. `rmse` is
         *     empty without measurements. `measured_points` holds points made from the measurements sent,
         *     by name with its unit: `electrical_conductivity_s_per_m` is 1/rho, with null for a rho of 0 or
         *     below. They use no model, so they go with the data the request sent, interpolated or not.
         * @example {
         *       "curves": {
         *         "resistivity_ohm_m": [
         *           0.000036627,
         *           0.000084229,
         *           0.000067638,
         *           0.000049129,
         *           0.000039895
         *         ],
         *         "seebeck_v_per_k": [
         *           0.00020573,
         *           0.00022818,
         *           0.000088928,
         *           0.000037589,
         *           0.000020745
         *         ]
         *       },
         *       "known_issues": [],
         *       "measured_points": {
         *         "electrical_conductivity_s_per_m": {
         *           "temperature_k": [
         *             150,
         *             300
         *           ],
         *           "values": [
         *             100000,
         *             25000
         *           ]
         *         }
         *       },
         *       "rmse": {
         *         "seebeck": {
         *           "unit": "uV/K",
         *           "value": 3.385
         *         }
         *       },
         *       "temperature_k": [
         *         100,
         *         200,
         *         300,
         *         400,
         *         500
         *       ]
         *     }
         */
        CalcResponse: {
            /** Temperature K */
            temperature_k: number[];
            /** Curves */
            curves: {
                [key: string]: (number | null)[];
            };
            /** Known Issues */
            known_issues: string[];
            /** Rmse */
            rmse: {
                [key: string]: components["schemas"]["RmseResponse"];
            };
            /** Measured Points */
            measured_points?: {
                [key: string]: components["schemas"]["MeasuredPointsResponse"];
            };
        };
        /**
         * ColumnRole
         * @description What a column holds. Columns count from 0.
         */
        ColumnRole: {
            /** Column */
            column: number;
            /**
             * Role
             * @enum {string}
             */
            role: "temperature" | "seebeck" | "resistivity" | "hall";
        };
        /**
         * CurveAvailabilityResponse
         * @description Whether a mode offers a kind of curve for `POST /api/calc`.
         *
         *     `reason` is a code for one it does not offer, and a client shows `curve_unavailable.<reason>`
         *     through i18n. `relative` means that the size of the curve rests on an assumed value, not on
         *     data: carrier concentrations with no Hall data use m1 = 1.
         */
        CurveAvailabilityResponse: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "measured" | "seebeck" | "seebeck_by_band" | "chemical_potential" | "electrical_conductivity" | "electrical_conductivity_by_band" | "thermal_conductivity" | "carrier_concentration_by_band";
            /** Available */
            available: boolean;
            /** Reason */
            reason?: string | null;
            /** Relative */
            relative: boolean;
        };
        /** DegeneracyResponse */
        DegeneracyResponse: {
            /** Band 1 Default */
            band_1_default: number;
            /** Band 2 Default */
            band_2_default: number;
        };
        /**
         * DemoNoise
         * @description The noise added to the model's curves: V/K for S, and a relative size for rho and R_H.
         */
        DemoNoise: {
            /** Seed */
            seed: number;
            /** Seebeck V Per K */
            seebeck_v_per_k: number;
            /** Resistivity Relative */
            resistivity_relative: number;
            /** Hall Relative */
            hall_relative: number;
        };
        /**
         * DemoResponse
         * @description A parsed file, as from `POST /api/parse`, that is not a measurement of any material.
         *
         *     A client must say so, by showing `message_key` through i18n wherever the data appear.
         *     `known_issues` names the errors of the model that the data carry. `model`, `fit_mode` and
         *     `scattering` say what generated them. `true_parameters` holds values of that model, in core
         *     units, and its other parameters were at the defaults of `GET /api/models`.
         */
        DemoResponse: {
            /** Headers */
            headers?: string[] | null;
            /** Column Count */
            column_count: number;
            /** Row Count */
            row_count: number;
            /** Preview */
            preview: number[][];
            /** Mapping */
            mapping: components["schemas"]["ColumnRole"][];
            /** Measurements */
            measurements: {
                [key: string]: components["schemas"]["MeasurementResponse"];
            };
            /** Errors */
            errors: components["schemas"]["IssueResponse"][];
            /** Warnings */
            warnings: components["schemas"]["IssueResponse"][];
            /** Warnings Omitted */
            warnings_omitted: number;
            /** Interpolated */
            interpolated: {
                [key: string]: components["schemas"]["InterpolatedResponse"];
            };
            /** Interpolation Failed */
            interpolation_failed: ("seebeck" | "resistivity" | "hall")[];
            /**
             * Synthetic
             * @constant
             */
            synthetic: true;
            /** Message Key */
            message_key: string;
            /** Known Issues */
            known_issues: string[];
            /** Model */
            model: string;
            /** Fit Mode */
            fit_mode: string;
            /** Scattering */
            scattering: string;
            /** True Parameters */
            true_parameters: {
                [key: string]: number;
            };
            noise: components["schemas"]["DemoNoise"];
        };
        /**
         * EnergyDisplayResponse
         * @description How a client shows an energy that comes in K, such as a curve of μ or E(k): in `unit`, at
         *     `per_kelvin` of it for each kelvin. Temperatures stay in K.
         */
        EnergyDisplayResponse: {
            /** Unit */
            unit: string;
            /** Per Kelvin */
            per_kelvin: number;
        };
        /**
         * ErrorDetail
         * @description One problem in a request. `location` is the path to it, such as `["body", "points", 3]`.
         */
        ErrorDetail: {
            /** Location */
            location: (string | number)[];
            /** Code */
            code: string;
            /** Message */
            message: string;
        };
        /**
         * ErrorResponse
         * @description The body of every error response.
         */
        ErrorResponse: {
            /** Code */
            code: string;
            /** Message */
            message: string;
            /** Details */
            details: components["schemas"]["ErrorDetail"][];
        };
        /**
         * FitApiRequest
         * @description What to fit.
         *
         *     `start` holds every parameter of the mode in core units, including those of other scattering
         *     types. `bounds` overrides the description's bounds for fitted parameters, in core units.
         *     `measurements` holds each quantity of the mode, and only points from `min_temperature_k` to
         *     `max_temperature_k`, inclusive, enter the fit. `extrapolated` says that interpolation made up
         *     some of these points, so that the result says so too.
         * @example {
         *       "bounds": {
         *         "band_gap": {
         *           "lower": 0,
         *           "upper": 4000
         *         }
         *       },
         *       "fit_mode": "dpb_s",
         *       "max_temperature_k": 500,
         *       "measurements": {
         *         "seebeck": {
         *           "temperature_k": [
         *             100,
         *             200,
         *             300,
         *             400,
         *             500
         *           ],
         *           "values": [
         *             0.0002,
         *             0.00023,
         *             0.000089,
         *             0.000038,
         *             0.000021
         *           ]
         *         }
         *       },
         *       "min_temperature_k": 100,
         *       "model": "dpb",
         *       "start": {
         *         "band_gap": 1000,
         *         "fermi_energy": -100,
         *         "m_eff": 1.01
         *       }
         *     }
         */
        FitApiRequest: {
            /** Model */
            model: string;
            /** Fit Mode */
            fit_mode: string;
            /** Scattering */
            scattering?: string | null;
            /** Start */
            start: {
                [key: string]: number;
            };
            /** Bounds */
            bounds?: {
                [key: string]: components["schemas"]["BoundsInput"];
            };
            /** Min Temperature K */
            min_temperature_k: number;
            /** Max Temperature K */
            max_temperature_k: number;
            /**
             * Band 1 Degeneracy
             * @default 1
             */
            band_1_degeneracy?: number;
            /**
             * Band 2 Degeneracy
             * @default 1
             */
            band_2_degeneracy?: number;
            /**
             * Extrapolated
             * @default false
             */
            extrapolated?: boolean;
            /** Measurements */
            measurements: {
                [key: string]: components["schemas"]["MeasurementInput"];
            };
        };
        /**
         * FitDone
         * @description The last event of a fit that ended, whatever its `status`.
         */
        FitDone: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "done";
            result: components["schemas"]["FitResponse"];
        };
        /**
         * FitError
         * @description The last event of a fit with no result: `fit_timeout`, `fit_process_died` or `fit_failed`.
         */
        FitError: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "error";
            error: components["schemas"]["ErrorResponse"];
        };
        /**
         * FitIteration
         * @description Progress of an iterative fit, in core units. A single-pass mode sends none.
         *
         *     `parameters` holds every parameter of the mode, in the form of a final result. One fitted after
         *     the loop, such as m1, keeps its start value here. A value that is not finite is null.
         */
        FitIteration: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "iteration";
            /** Iteration */
            iteration: number;
            /** Parameters */
            parameters: {
                [key: string]: number | null;
            };
        };
        /**
         * FitModeResponse
         * @description One way of fitting a model.
         *
         *     A client must not offer a mode with `disabled`. `disabled_by` names the `known_issues` that say
         *     why. `iterative` tells whether an iteration count means anything. `threshold`, a relative
         *     change, and `max_iterations` are what an iterative fit uses, and a request cannot change them.
         *     `scattering` is empty when a mode has no choice of scattering. `stages` are the solver runs of
         *     a fit, in their order.
         */
        FitModeResponse: {
            /** Id */
            id: string;
            /** Quantities */
            quantities: ("seebeck" | "resistivity" | "hall")[];
            /** Parameters */
            parameters: components["schemas"]["ParameterResponse"][];
            /** Scattering */
            scattering: string[];
            /** Default Scattering */
            default_scattering?: string | null;
            /** Iterative */
            iterative: boolean;
            /** Threshold */
            threshold?: number | null;
            /** Max Iterations */
            max_iterations?: number | null;
            degeneracy?: components["schemas"]["DegeneracyResponse"] | null;
            /** Curve Kinds */
            curve_kinds: ("measured" | "seebeck" | "seebeck_by_band" | "chemical_potential" | "electrical_conductivity" | "electrical_conductivity_by_band" | "thermal_conductivity" | "carrier_concentration_by_band")[];
            /** Curves */
            curves: components["schemas"]["CurveAvailabilityResponse"][];
            /** Disabled */
            disabled: boolean;
            /** Disabled By */
            disabled_by: string[];
            /** Known Issues */
            known_issues: components["schemas"]["KnownIssueResponse"][];
            /** Stages */
            stages: components["schemas"]["FitStageResponse"][];
        };
        /**
         * FitResponse
         * @description The outcome of a fit, in core units.
         *
         *     `converged` means that the fit ended normally, not that the result is sound. `iteration_limit`
         *     is not a converged result. `failed` returns the start values, with fixed text in `message`.
         *     `iterations` is left out for a single-pass mode. A value that is not finite is null.
         *
         *     `parameter_errors` holds standard errors from the last solver run of each stage, holding other
         *     stages fixed, so in a staged fit they can be far too small, and are not plain uncertainties.
         *     `at_bounds` names fitted parameters that ended at a bound, which may be what set them.
         *     `known_issues` names known errors that apply, as in `GET /api/models`.
         * @example {
         *       "at_bounds": [],
         *       "known_issues": [],
         *       "parameter_errors": {
         *         "band_gap": 12,
         *         "fermi_energy": 4,
         *         "m_eff": 0.02
         *       },
         *       "parameters": {
         *         "band_gap": 910,
         *         "fermi_energy": -35,
         *         "m_eff": 0.57
         *       },
         *       "status": "converged"
         *     }
         */
        FitResponse: {
            /** Parameters */
            parameters: {
                [key: string]: number | null;
            };
            /**
             * Status
             * @enum {string}
             */
            status: "converged" | "iteration_limit" | "stopped" | "failed";
            /** Iterations */
            iterations?: number | null;
            /** Message */
            message?: string | null;
            /** Parameter Errors */
            parameter_errors: {
                [key: string]: number;
            };
            /** At Bounds */
            at_bounds: string[];
            /** Known Issues */
            known_issues: string[];
        };
        /**
         * FitStageResponse
         * @description One solver run of a fit: the quantity it fits, and the parameters it finds.
         *
         *     `repeats` marks a stage of the loop of an iterative mode, which runs once in each iteration.
         *     `parameters` names every parameter the stage can find; the scattering decides which of them
         *     a fit has.
         */
        FitStageResponse: {
            /**
             * Quantity
             * @enum {string}
             */
            quantity: "seebeck" | "resistivity" | "hall";
            /** Parameters */
            parameters: string[];
            /** Repeats */
            repeats: boolean;
        };
        /**
         * FitStarted
         * @description The fit has left the queue, and its process is starting.
         */
        FitStarted: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "started";
        };
        /**
         * GuessFound
         * @description A guess.
         *
         *     `start_values` holds what to use, by the parameter names of `GET /api/models`, in core units as
         *     in `core_range`: `m_eff` is dimensionless, `band_gap` and `fermi_energy` are in K. They are
         *     rounded and limited as the desktop's sliders do, so they lie in `core_range` of every mode of
         *     the model. Other parameters keep their values. With the warning `m_eff_rounds_to_zero`, `m_eff`
         *     is 0, which has no curve, and a fit from it fails, so a client should not use it as it is.
         */
        GuessFound: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            status: "guess";
            net_range: components["schemas"]["NetRange"];
            prediction: components["schemas"]["Prediction"];
            /** Start Values */
            start_values: {
                [key: string]: number;
            };
            /** Warnings */
            warnings: ("unsorted_temperature" | "underdetermined_fit" | "m_eff_rounds_to_zero")[];
        };
        /**
         * GuessNoNet
         * @description No net fits: the first and last rows do not span any of `available_ranges`.
         *
         *     A client should keep its current values, as the desktop does.
         */
        GuessNoNet: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            status: "no_net";
            /**
             * Reason
             * @constant
             */
            reason: "temperature_span";
            /** First Temperature K */
            first_temperature_k: number;
            /** Last Temperature K */
            last_temperature_k: number;
            /** Available Ranges */
            available_ranges: components["schemas"]["NetRange"][];
            /** Warnings */
            warnings: ("unsorted_temperature" | "underdetermined_fit" | "m_eff_rounds_to_zero")[];
        };
        /**
         * GuessNotFinite
         * @description The net ran, but a value of its prediction is not finite, so there is nothing to use.
         *
         *     The prediction is left out, as JSON has no such numbers. A client should keep its values.
         */
        GuessNotFinite: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            status: "not_finite";
            net_range: components["schemas"]["NetRange"];
            /** Warnings */
            warnings: ("unsorted_temperature" | "underdetermined_fit" | "m_eff_rounds_to_zero")[];
        };
        /**
         * GuessRequest
         * @description Measured Seebeck data, in V/K, with all rows of the data.
         *
         *     Unlike `POST /api/calc`, this takes every row and not only the fit range, as the desktop does.
         *     Rows are read in the order sent, and the choice of net reads the first and last.
         * @example {
         *       "model": "dpb",
         *       "seebeck_v_per_k": [
         *         -0.000008983,
         *         -0.00005032,
         *         -0.00007751,
         *         -0.00009938,
         *         -0.0001174,
         *         -0.0001202,
         *         -0.0001046,
         *         -0.00008192,
         *         -0.0000619,
         *         -0.000047
         *       ],
         *       "temperature_k": [
         *         25,
         *         100,
         *         175,
         *         250,
         *         325,
         *         400,
         *         475,
         *         550,
         *         625,
         *         700
         *       ]
         *     }
         */
        GuessRequest: {
            /** Model */
            model: string;
            /** Temperature K */
            temperature_k: number[];
            /** Seebeck V Per K */
            seebeck_v_per_k: number[];
        };
        /**
         * HealthResponse
         * @example {
         *       "status": "ok",
         *       "version": "1.0.0"
         *     }
         */
        HealthResponse: {
            /**
             * Status
             * @constant
             */
            status: "ok";
            /** Version */
            version: string;
        };
        /**
         * InterpolatedResponse
         * @description A quantity on the interpolation grid. `null` marks a value that is not finite.
         *
         *     `extrapolated` means that some of the grid lies outside the data, so those values are made up,
         *     and a fit from them should say so through `extrapolated` in its request.
         *     `measured_points_in_range` of 0 means that all the values are made up. `underdetermined` means
         *     that the data do not set the polynomial.
         */
        InterpolatedResponse: {
            /** Temperature K */
            temperature_k: number[];
            /** Values */
            values: (number | null)[];
            /** Extrapolated */
            extrapolated: boolean;
            /** Measured Points In Range */
            measured_points_in_range: number;
            /** Underdetermined */
            underdetermined: boolean;
        };
        /** InterpolationRange */
        InterpolationRange: {
            /** Min Temperature K */
            min_temperature_k: number;
            /** Max Temperature K */
            max_temperature_k: number;
        };
        /**
         * IssueResponse
         * @description A problem in the data, as a code a client translates, in `input-data.md` of the core.
         *
         *     `line` counts every line of the text from 1, and `column` from 0.
         */
        IssueResponse: {
            /**
             * Code
             * @enum {string}
             */
            code: "no_data" | "wrong_encoding" | "line_too_long" | "too_many_problems" | "too_few_columns" | "wrong_column_count" | "missing_value" | "not_numeric" | "not_finite" | "decimal_comma" | "too_few_rows" | "missing_temperature" | "non_positive_temperature" | "negative_resistivity" | "repeated_role" | "preamble_skipped" | "header_mismatch" | "unit_differs" | "repeated_header" | "columns_need_assigning" | "expected_not_found" | "no_quantity" | "few_rows" | "unsorted_temperature" | "duplicate_temperature";
            /** Line */
            line?: number | null;
            /** Column */
            column?: number | null;
        };
        /**
         * KnownIssueResponse
         * @description A known error of the calculations in this mode. Clients show `message_key` through i18n.
         *
         *     Empty `scattering` means every type. `curve_kinds` lists the curves it applies to, and empty
         *     means none. Empty `columns` means every curve of those kinds. `condition`, if present, limits it
         *     to some inputs. `fixed_by` is the issue in this repository that removes it.
         */
        KnownIssueResponse: {
            /** Id */
            id: string;
            /**
             * Severity
             * @enum {string}
             */
            severity: "disabled" | "unreliable" | "caution";
            /** Message Key */
            message_key: string;
            /** Fixed By */
            fixed_by: string;
            /** Scattering */
            scattering: string[];
            /** Curve Kinds */
            curve_kinds: ("measured" | "seebeck" | "seebeck_by_band" | "chemical_potential" | "electrical_conductivity" | "electrical_conductivity_by_band" | "thermal_conductivity" | "carrier_concentration_by_band")[];
            /** Columns */
            columns: string[];
            /** Affects Fit */
            affects_fit: boolean;
            /** Condition */
            condition?: ("degeneracy_not_one" | "negative_m_eff" | "collapsed_m_eff" | "fermi_energy_outside_band" | "interpolation_extrapolated") | null;
        };
        /**
         * MeasuredPointsResponse
         * @description Points made from measurements alone, at their temperatures. Null marks one with no value.
         */
        MeasuredPointsResponse: {
            /** Temperature K */
            temperature_k: number[];
            /** Values */
            values: (number | null)[];
        };
        /**
         * MeasurementInput
         * @description Measured points, with values in V/K for S, ohm m for rho and m^3/C for R_H.
         */
        MeasurementInput: {
            /** Temperature K */
            temperature_k: number[];
            /** Values */
            values: number[];
        };
        /**
         * MeasurementResponse
         * @description Measured data sorted by temperature, in V/K, ohm m or m^3/C, and its size and range.
         */
        MeasurementResponse: {
            /** Temperature K */
            temperature_k: number[];
            /** Values */
            values: number[];
            /** Points */
            points: number;
            /** Min Temperature K */
            min_temperature_k: number;
            /** Max Temperature K */
            max_temperature_k: number;
        };
        /**
         * ModelResponse
         * @description A model. `name` is English text, for a client to fall back on.
         *
         *     `has_initial_guess` says that `POST /api/guess` gives start values for this model.
         */
        ModelResponse: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Default Min Temperature K */
            default_min_temperature_k: number;
            /** Default Max Temperature K */
            default_max_temperature_k: number;
            /** Default Curve Points */
            default_curve_points: number;
            /** Has Initial Guess */
            has_initial_guess: boolean;
            /** Fit Modes */
            fit_modes: components["schemas"]["FitModeResponse"][];
        };
        /** ModelsResponse */
        ModelsResponse: {
            /** Models */
            models: components["schemas"]["ModelResponse"][];
            energy_display: components["schemas"]["EnergyDisplayResponse"];
        };
        /**
         * NetRange
         * @description The temperature span a net needs, and the range of its input.
         */
        NetRange: {
            /** Min Temperature K */
            min_temperature_k: number;
            /** Max Temperature K */
            max_temperature_k: number;
        };
        /**
         * ParameterResponse
         * @description One parameter of a fit mode.
         *
         *     `display_range` is the control's range as a user sees it, and `core_range` is the same range in
         *     the core units of requests and results. Use these two, and do not calculate core values from the
         *     scales: `display_scale` and `fit_scale`, from control units in `value_range`, are there for
         *     information, as the desktop divides where a multiplication would change the last bit.
         *
         *     In each range, `step` is the desktop's keyboard increment, not a grid: values between steps are
         *     valid, and the default or maximum need not lie on a step.
         *
         *     `scattering` lists the types the parameter applies to, and empty means all of them. A mode with
         *     no choice of scattering uses all its parameters, whatever they list. A `fixed` parameter is set
         *     by the user, and a fit does not change it. Requests hold every parameter of a mode, including
         *     those of other scattering types.
         *
         *     `unit` is the unit of the scaled value, and can be `dimensionless` or `unknown`. `display_unit`
         *     is the one a user sees, and `display_factor` goes from the one to the other: an energy in K is
         *     shown in eV. `display_range` is already in `display_unit`. `fit_bounds` is in core units, and is
         *     left out for a parameter that a fit does not change. `meaning` is English text, for a client
         *     with no translation.
         */
        ParameterResponse: {
            /** Name */
            name: string;
            /** Meaning */
            meaning: string;
            /** Unit */
            unit: string;
            /**
             * Role
             * @enum {string}
             */
            role: "fitted" | "fixed";
            /** Scattering */
            scattering: string[];
            value_range: components["schemas"]["ValueRangeResponse"];
            display_range: components["schemas"]["ValueRangeResponse"];
            core_range: components["schemas"]["ValueRangeResponse"];
            /** Display Scale */
            display_scale: number;
            /** Fit Scale */
            fit_scale: number;
            /** Display Unit */
            display_unit: string;
            /** Display Factor */
            display_factor: number;
            fit_bounds?: components["schemas"]["BoundsResponse"] | null;
            /** Bounds Editable */
            bounds_editable: boolean;
        };
        /**
         * ParseRequest
         * @description A text to read, as the client read it from a file or table.
         *
         *     `expected` names the quantity of a file meant to hold one. `mapping` replaces the suggested
         *     columns with a user's choice, and the text is sent again each time, as the API keeps nothing.
         *     `interpolate` asks for each quantity on a grid over this fit range.
         */
        ParseRequest: {
            /** Text */
            text: string;
            /** Expected */
            expected?: ("seebeck" | "resistivity" | "hall") | null;
            /** Mapping */
            mapping?: components["schemas"]["ColumnRole"][] | null;
            interpolate?: components["schemas"]["InterpolationRange"] | null;
        };
        /**
         * ParseResponse
         * @description What the text holds. A file with problems is still a 200, with a preview and its `errors`.
         *
         *     `measurements` is empty with any `errors`. `headers` is left out when no header matches the
         *     columns. `column_count` is 0 when neither a row nor a header sets it. `preview` holds the first
         *     rows that could be read, in the order of the text, and `row_count` all of them. `mapping` is the
         *     suggestion or the user's choice, and with no readable rows, always the suggestion. `warnings`
         *     holds every kind, with at most 100 `preamble_skipped`, and `warnings_omitted` counts the rest.
         *     `interpolation_failed` names quantities that could not be interpolated.
         */
        ParseResponse: {
            /** Headers */
            headers?: string[] | null;
            /** Column Count */
            column_count: number;
            /** Row Count */
            row_count: number;
            /** Preview */
            preview: number[][];
            /** Mapping */
            mapping: components["schemas"]["ColumnRole"][];
            /** Measurements */
            measurements: {
                [key: string]: components["schemas"]["MeasurementResponse"];
            };
            /** Errors */
            errors: components["schemas"]["IssueResponse"][];
            /** Warnings */
            warnings: components["schemas"]["IssueResponse"][];
            /** Warnings Omitted */
            warnings_omitted: number;
            /** Interpolated */
            interpolated: {
                [key: string]: components["schemas"]["InterpolatedResponse"];
            };
            /** Interpolation Failed */
            interpolation_failed: ("seebeck" | "resistivity" | "hall")[];
        };
        /**
         * Prediction
         * @description The net's prediction as it is, in core units, before any rounding or limits.
         */
        Prediction: {
            /** M Eff */
            m_eff: number;
            /** Band Gap K */
            band_gap_k: number;
            /** Fermi Energy K */
            fermi_energy_k: number;
        };
        /**
         * RmseResponse
         * @description `value` is null where the result is not finite, as when the model has no finite value.
         */
        RmseResponse: {
            /** Value */
            value: number | null;
            /** Unit */
            unit: string;
        };
        /** ValueRangeResponse */
        ValueRangeResponse: {
            /** Minimum */
            minimum: number;
            /** Maximum */
            maximum: number;
            /** Step */
            step: number;
            /** Default */
            default: number;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    get_health: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
            /** @description Default Response */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_models: {
        parameters: {
            query?: never;
            header?: {
                "if-none-match"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    /** @example no-cache */
                    "Cache-Control"?: string;
                    /** @example "c38f3175cdbaf11f1e62cbf8bcb3712c" */
                    ETag?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelsResponse"];
                };
            };
            /** @description The descriptions have not changed since the given `If-None-Match` */
            304: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Default Response */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    post_calc: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CalcRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CalcResponse"];
                };
            };
            /** @description Too many requests from this client, or for the server */
            429: {
                headers: {
                    /** @example 5 */
                    "Retry-After"?: number;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Default Response */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    post_band_diagram: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BandDiagramRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BandDiagramResponse"];
                };
            };
            /** @description Too many requests from this client, or for the server */
            429: {
                headers: {
                    /** @example 5 */
                    "Retry-After"?: number;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Default Response */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    post_parse: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ParseRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ParseResponse"];
                };
            };
            /** @description Too many requests from this client, or for the server */
            429: {
                headers: {
                    /** @example 5 */
                    "Retry-After"?: number;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Default Response */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    post_guess: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GuessRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GuessFound"] | components["schemas"]["GuessNoNet"] | components["schemas"]["GuessNotFinite"];
                };
            };
            /** @description Too many requests from this client, or for the server */
            429: {
                headers: {
                    /** @example 5 */
                    "Retry-After"?: number;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Default Response */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    post_fit: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FitApiRequest"];
            };
        };
        responses: {
            /** @description Events of the fit. The last is `done` or `error` */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": unknown;
                };
            };
            /** @description Too many requests from this client, or for the server */
            429: {
                headers: {
                    /** @example 5 */
                    "Retry-After"?: number;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Default Response */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_demo: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DemoResponse"];
                };
            };
            /** @description Default Response */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
}
