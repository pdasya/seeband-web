import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      "**/dist/**",
      "**/.astro/**",
      "**/node_modules/**",
      ".venv/**",
      ".claude/worktrees/**",
      "apps/web/.claude/**",
    ],
  },
  { ignores: ["packages/api-client/src/schema.d.ts"] },
  {
    files: ["**/*.mjs"],
    languageOptions: {
      globals: {
        AbortController: "readonly",
        AbortSignal: "readonly",
        Buffer: "readonly",
        URL: "readonly",
        console: "readonly",
        fetch: "readonly",
        performance: "readonly",
        process: "writable",
      },
    },
  },
  js.configs.recommended,
  ...tseslint.configs.strict,
  {
    files: ["apps/web/**/*.{ts,tsx}"],
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // A warning does not fail the checks, and a missing dependency is a real bug.
      "react-hooks/exhaustive-deps": "error",
    },
  },
  {
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
    },
  },
);
