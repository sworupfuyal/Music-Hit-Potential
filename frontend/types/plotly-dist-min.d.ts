/**
 * `plotly.js-dist-min` ships no types of its own. It exposes the same runtime API
 * as `plotly.js` (typed by @types/plotly.js), and is only ever handed to
 * react-plotly.js's factory, so a default-exported module object is enough.
 */
declare module "plotly.js-dist-min" {
  const Plotly: typeof import("plotly.js");
  export default Plotly;
}
