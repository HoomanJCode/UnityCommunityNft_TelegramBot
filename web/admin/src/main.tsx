import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

// The admin dashboard is a plain web app (no Telegram/TON Connect), so it
// mounts directly into #root.
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
