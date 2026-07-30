import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";
import "../../../editors/web/src/styles/app.css";
import "../../../editors/web/src/styles/chat.css";
import "@vscode/codicons/dist/codicon.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <App />,
);
