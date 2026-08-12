import React from "react";
import ReactDOM from "react-dom/client";
import { TonConnectUIProvider } from "@tonconnect/ui-react";
import App from "./App";
import { initTelegramWebApp } from "./telegram";
import "./styles.css";

initTelegramWebApp();

// TON Connect validates the app against this manifest (public/tonconnect-manifest.json).
const manifestUrl =
  (import.meta.env.VITE_TON_MANIFEST_URL as string | undefined) ??
  `${window.location.origin}/tonconnect-manifest.json`;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <TonConnectUIProvider manifestUrl={manifestUrl}>
      <App />
    </TonConnectUIProvider>
  </React.StrictMode>
);
