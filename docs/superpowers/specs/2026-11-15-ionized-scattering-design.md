# Ionized impurity scattering

The scientific owner selected the power-law approximation tau(E) proportional to E^(3/2), lambda=2, and requested replacing acPhDis with ionized impurities in SPB and DPB. Lambda belongs to each scattering mechanism; it is neither mutable global state nor a fitted parameter.

## Approach

Use explicit immutable mechanism metadata and shared transport expressions. Preserve acPh/dis numerical behavior. Add `ionized` to all fit modes including S-only; remove acPhDis from public choices. Retain historical low-level mixed-scattering calls and captures for reproducibility, without offering them as a current model. Do not reinterpret old sessions as ionized.

The alternatives were an explicit screened Brooks-Herring model and a fixed power-law approximation. The owner selected the latter; dielectric screening, impurity ionization and crossover models are excluded.

## Physics contract

For unnormalized Fermi integrals and lambda=2, sigma is proportional to T^3 F2, S uses (4 F3)/(3 F2)-eta, Lorenz uses (5 F4)/(3 F2)-(4 F3/(3 F2))^2, and Hall uses F_(7/2)/F2^2 with coefficient (2lambda+1/2)/(lambda+1)^2. Carrier statistics and density solving are independent of scattering. DPB combines conductivities, signed Hall numerators and open-circuit heat transport including the bipolar term. Free amplitudes absorb material prefactors, not temperature dependence. Electron/hole signs and public mass/degeneracy conventions remain explicit.

## Integration

Verified fitting supports ionized. Legacy selection must reject it explicitly, never silently substitute another algorithm. SPB numerical starting estimates use the chosen mechanism; DPB neural estimates are unavailable for ionized. The UI explains these restrictions. API/client descriptions remain registry driven; regenerate OpenAPI and TypeScript. Metadata, sessions and exports retain mechanism identity. Version and documentation describe the new approximation and removal.

## Validation

Independent transport-integral references, electron/hole and degenerate/nondegenerate limits, sigma*rho=1, band sums, Hall density scaling, bipolar thermal term and interleaved mechanism calls. Exercise calculation, fitting, input-grid residuals, API, sessions and browser choice. Preserve historical fixtures; new synthetic evidence is separate. Parent owns final validation; worker runs focused core checks. Independent physics, numerics and integration reviews have distinct scopes. Agent review does not replace scientific-owner acceptance of implementation.
