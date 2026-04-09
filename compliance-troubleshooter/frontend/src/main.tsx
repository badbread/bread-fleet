// React entry. Mounts the App component into #root.
// Strict mode is on because the rest of the codebase is small enough
// to handle the double-render in development without surprises.

import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
