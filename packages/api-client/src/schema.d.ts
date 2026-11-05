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
         *     why. `iterative` tells whether an iteration count means anything. `threshold`, a relative
         *     change, and `max_iterations` are what an iterative fit uses, and a request cannot change them.
         *     `scattering` is empty when a mode has no choice of scattering.
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
         *     `unit` is the unit of the displayed value, and can be `dimensionless` or `unknown`. `fit_bounds`
         *     is in core units, and is left out for a parameter that a fit does not change. `meaning` is
         *     English text, for a client with no translation.
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
                    /** @example "c306ebcca5c90ab57d6960126e9e1012" */
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
}
