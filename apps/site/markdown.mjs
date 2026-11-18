// Formulas in Markdown and MDX, as KaTeX renders them when the site is built: a page gets HTML and
// CSS for them, and no script. The math fixture in `tests` builds with these too.
import { unified } from "@astrojs/markdown-remark";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";

const hasClass = (node, name) => {
  const classes = node.properties?.className;
  return Array.isArray(classes) && classes.includes(name);
};

/**
 * A wide table or formula scrolls in its own box, which takes keyboard focus so that it can be
 * scrolled without a mouse. A table stays a table, as a screen reader loses its role if the table
 * itself scrolls.
 */
export function rehypeScrollBoxes() {
  const walk = (node) => {
    if (!Array.isArray(node.children)) {
      return;
    }
    node.children = node.children.map((child) => {
      if (child.type !== "element") {
        return child;
      }
      if (child.tagName === "table") {
        return {
          type: "element",
          tagName: "div",
          properties: { className: ["scroll-box"], tabIndex: 0 },
          children: [child],
        };
      }
      if (hasClass(child, "katex-display")) {
        child.properties = { ...child.properties, tabIndex: 0 };
        return child;
      }
      walk(child);
      return child;
    });
  };
  return walk;
}

export const markdown = {
  processor: unified({
    remarkPlugins: [remarkMath],
    rehypePlugins: [rehypeKatex, rehypeScrollBoxes],
  }),
};
