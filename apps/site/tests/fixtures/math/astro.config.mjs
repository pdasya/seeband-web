import mdx from "@astrojs/mdx";
import { defineConfig } from "astro/config";

import { markdown } from "../../../markdown.mjs";

// A page with formulas, built as the site builds its MDX, as the site has none yet.
export default defineConfig({ integrations: [mdx()], markdown });
