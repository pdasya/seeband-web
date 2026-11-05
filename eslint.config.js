import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["**/dist/**", "**/.astro/**", "**/node_modules/**", ".venv/**"] },
  { ignores: ["packages/api-client/src/schema.d.ts"] },
  {
    files: ["**/*.mjs"],
    languageOptions: {
      globals: { URL: "readonly", console: "readonly", process: "writable" },
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
