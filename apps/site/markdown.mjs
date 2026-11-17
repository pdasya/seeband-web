// Formulas in Markdown and MDX, as KaTeX renders them when the site is built: a page gets HTML and
// CSS for them, and no script. The math fixture in `tests` builds with these too.
import { unified } from "@astrojs/markdown-remark";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";

export const markdown = {
  processor: unified({
    remarkPlugins: [remarkMath],
    rehypePlugins: [rehypeKatex],
  }),
};
