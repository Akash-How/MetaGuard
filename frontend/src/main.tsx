import React from "react";
import ReactDOM from "react-dom/client";

import { ProtoApp } from "./app/ProtoApp";
import "./app/styles.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ProtoApp />
  </React.StrictMode>,
);
