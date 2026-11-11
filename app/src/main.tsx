import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "./design/tokens.css";
import "./design/base.css";
import "./design/components.css";
import "./design/prose.css";
import "./design/code.css";
import "./design/theme.css";
import { App } from "./app/App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
