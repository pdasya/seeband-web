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
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** BoundsResponse */
        BoundsResponse: {
            /** Lower */
            lower: number;
            /** Upper */
            upper: number;
        };
        /** DegeneracyResponse */
        DegeneracyResponse: {
            /** Band 1 Default */
            band_1_default: number;
            /** Band 2 Default */
            band_2_default: number;
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
         * FitModeResponse
         * @description One way of fitting a model.
         *
         *     A client must not offer a mode with `disabled`. `disabled_by` names the `known_issues` that say
         *     why. `iterative` tells whether an iteration count means anything, and `threshold` and
         *     `max_iterations` apply only to an iterative mode. `scattering` is empty when a mode has no
         *     choice of scattering.
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
            /** Disabled */
            disabled: boolean;
            /** Disabled By */
            disabled_by: string[];
            /** Known Issues */
            known_issues: components["schemas"]["KnownIssueResponse"][];
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
         * KnownIssueResponse
         * @description A known error of the calculations in this mode.
         *
         *     Clients show `message_key` through i18n. `explanation` is English text for developers. Empty
         *     `scattering` means every type, and empty `columns` every curve of a kind. `condition`, if
         *     present, limits the issue to some inputs. `fixed_by` is the issue in this repository that
         *     removes it.
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
            /** Explanation */
            explanation: string;
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
         * ModelResponse
         * @description A model. `name` is English text, for a client to fall back on.
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
            /** Fit Modes */
            fit_modes: components["schemas"]["FitModeResponse"][];
        };
        /** ModelsResponse */
        ModelsResponse: {
            /** Models */
            models: components["schemas"]["ModelResponse"][];
        };
        /**
         * ParameterResponse
         * @description One parameter of a fit mode.
         *
         *     `value_range` is in control units, and `display_range` is the same range as a user sees it.
         *     `display_scale` converts control units to displayed values, and `fit_scale` to core units.
         *     `unit` is the unit of the displayed value. `fit_bounds` is in core units, and is left out for a
         *     parameter that a fit does not change. `meaning` is English text, for a client to fall back on.
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
            /** Display Scale */
            display_scale: number;
            /** Fit Scale */
            fit_scale: number;
            /** Default Core Value */
            default_core_value: number;
            fit_bounds?: components["schemas"]["BoundsResponse"] | null;
            /** Bounds Editable */
            bounds_editable: boolean;
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
                    "application/json": components["schemas"]["ModelsResponse"];
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
