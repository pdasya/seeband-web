import { render } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { plotlySubscripts, Subscripted } from "@/lib/subscripts";

const html = (text: string | null) =>
  render(<p>{<Subscripted text={text} />}</p>).container.innerHTML;

describe("Subscripted", () => {
  test("lowers the index of each one-letter symbol", () => {
    expect(html("E_g = 0,09 eV")).toBe(
      "<p><span>E<sub>g</sub> = 0,09 eV</span></p>",
    );
    expect(html("RMSE, R_H")).toBe("<p><span>RMSE, R<sub>H</sub></span></p>");
    expect(html("L = κ_e/(σT), with (k_B/e)²")).toBe(
      "<p><span>L = κ<sub>e</sub>/(σT), with (k<sub>B</sub>/e)²</span></p>",
    );
    expect(html("max(0, E_g) and E_F")).toBe(
      "<p><span>max(0, E<sub>g</sub>) and E<sub>F</sub></span></p>",
    );
  });

  test("leaves names, text without symbols and no text as they are", () => {
    expect(html("fermi_energy_k and known_issue.x")).toBe(
      "<p>fermi_energy_k and known_issue.x</p>",
    );
    expect(html("m₂/m₁ and T, K")).toBe("<p>m₂/m₁ and T, K</p>");
    expect(html(null)).toBe("<p></p>");
  });
});

describe("plotlySubscripts", () => {
  test("writes the index as Plotly's sub, and escapes the rest", () => {
    expect(plotlySubscripts("R_H, m³/C")).toBe("R<sub>H</sub>, m³/C");
    expect(plotlySubscripts("band 2 bottom (E_g)")).toBe(
      "band 2 bottom (E<sub>g</sub>)",
    );
    expect(plotlySubscripts("m₂/m₁ < 0 & E_F")).toBe(
      "m₂/m₁ &lt; 0 &amp; E<sub>F</sub>",
    );
  });
});
