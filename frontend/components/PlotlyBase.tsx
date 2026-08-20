"use client";

/** Plotly bound to the browser bundle — loaded only via dynamic import (no SSR). */

import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";

export default createPlotlyComponent(Plotly);
