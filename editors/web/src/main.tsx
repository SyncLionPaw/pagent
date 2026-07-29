import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles/app.css";
import "./styles/chat.css";
import "@vscode/codicons/dist/codicon.css";

const root = document.getElementById("root");

if (root) {
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
