/**
 * Rollup config for the Price Watch panel.
 *
 * Bundles src/panel.ts (and everything it imports — Lit, our cards,
 * utils) into a single self-executing JS file that Home Assistant
 * loads via panel_custom. The output lives in the integration's
 * frontend/ directory so the same install ships the panel alongside
 * the Python code.
 */

import resolve from "@rollup/plugin-node-resolve";
import commonjs from "@rollup/plugin-commonjs";
import typescript from "@rollup/plugin-typescript";
import replace from "@rollup/plugin-replace";
import terser from "@rollup/plugin-terser";

const dev = process.env.ROLLUP_WATCH === "true";

export default {
  input: "src/panel.ts",
  output: {
    // Single-file bundle that registers the custom element side-effectfully.
    // No exports needed — Home Assistant just needs the <price-watch-panel>
    // element to exist on the page.
    file: "../custom_components/price_watch/frontend/price-watch-panel.js",
    format: "es",
    sourcemap: dev,
  },
  plugins: [
    // process.env.NODE_ENV is referenced by Lit's reactive controllers and
    // a few others. Without this replace, the bundle errors at runtime
    // when those modules try to read `process`.
    replace({
      preventAssignment: true,
      values: {
        "process.env.NODE_ENV": JSON.stringify(dev ? "development" : "production"),
      },
    }),
    // Resolve bare imports (lit, lit/decorators.js, etc.) from node_modules.
    resolve({
      browser: true,
      preferBuiltins: false,
      dedupe: ["lit"],
    }),
    // Some transitive deps are still CommonJS — Rollup needs this to handle them.
    commonjs(),
    // Transpile + bundle TS. Type-checking happens here too; tsconfig.json
    // controls the strictness.
    typescript({
      tsconfig: "./tsconfig.json",
      // We don't want the typescript plugin to also write declaration files.
      declaration: false,
      sourceMap: dev,
    }),
    // Minify production builds. Skip in watch mode so error messages stay
    // readable. Even minified, gzipped size should be well under 50KB.
    !dev && terser({
      // Preserve our custom-element class name in the output so debugging
      // in DevTools is easier. Other class names get mangled.
      mangle: {
        reserved: ["PriceWatchPanel"],
      },
      format: {
        comments: false,
      },
    }),
  ],
  watch: {
    clearScreen: false,
  },
};
