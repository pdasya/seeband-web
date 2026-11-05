import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      "**/dist/**",
      "**/.astro/**",
      "**/node_modules/**",
      ".venv/**",
      ".claude/worktrees/**",
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
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
    },
  },
);
