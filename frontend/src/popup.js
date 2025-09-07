import React from "react";
import ReactDOM from "react-dom/client"; 
import ExtensionPopup from "./ExtensionPopup";
import "./style.css";

const rootElement = document.getElementById("root");
const root = ReactDOM.createRoot(rootElement);
root.render(<ExtensionPopup/>);
