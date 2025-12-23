import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Custom ignores:
    "public/**",
  ]),
  // Rule overrides - these apply AFTER the base next configs
  {
    rules: {
      // Allow unused vars that start with underscore
      "@typescript-eslint/no-unused-vars": ["warn", { "argsIgnorePattern": "^_", "varsIgnorePattern": "^_" }],
      // Allow unescaped entities in JSX (common in text content)
      "react/no-unescaped-entities": "warn",
      // Allow any type in some cases
      "@typescript-eslint/no-explicit-any": "warn",
      // Allow <a> tags for external links or placeholders during migration
      "@next/next/no-html-link-for-pages": "warn",
      // Allow missing exhaustive-deps (will fix incrementally)
      "react-hooks/exhaustive-deps": "warn",
      // Allow missing display-name for components
      "react/display-name": "warn",
      // Allow <img> instead of Next.js Image during migration
      "@next/next/no-img-element": "warn",
      // Allow setState in useEffect (common pattern for hydration)
      "react-hooks/set-state-in-effect": "warn",
      // Allow rules-of-hooks violations during migration
      "react-hooks/rules-of-hooks": "warn",
      // Allow static components (components defined in render)
      "react-hooks/static-components": "warn",
    },
  },
]);

export default eslintConfig;
