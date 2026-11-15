# P13 positive DPB transport weights

The owner approved this contract on 2026-11-15. Correct P13 independently of
P18: retain band 1 as valence and the signed public mass ratio R, with r=R/N.
Keep the sign in occupations, conserved density and carrier signs. Longitudinal
weights are 1/|r| for S-only, B/|r| for single scattering, and
B(C_K+T)/[(D_K+T)|r|] for mixed scattering. Propagate these weights through
Seebeck, conductivity, resistivity, electronic thermal conductivity and band
contributions. Hall retains carrier signs and uses corrected resistivity.

Each DPB fit keeps the carrier branch selected by its initial mass. Zero is
excluded; bounds are intersected with that branch without an artificial mass
floor. Existing valid-domain numerical failures remain explicit. The density
solver, objectives and tolerances are unchanged.

The chosen approach fixes existing VB+VB and VB+CB configurations. Combining
it with P18 would also add explicit band types, CB+CB and API migration; that
larger alternative is deferred. This does not resolve P6 iterative degeneracy,
P16 identifiability or P19 general fit reliability. Neural guesses are not
evidence of validity for a newly corrected branch.

Acceptance: identical equally scattered valence bands add to twice the
single-channel conductivity and thermal conductivity, preserve single-channel
Seebeck and halve its Hall coefficient. Check both signs, all scattering
mechanisms, nonunit degeneracy, contribution reconstruction, positive physical
conductivities, sigma*rho=1, band-removal and equal-scattering limits. Record
intentional reference changes and version metadata. Independent agent review
does not replace the separate human physicist/parity release gate.
