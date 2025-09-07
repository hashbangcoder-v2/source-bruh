import React from "react";
import ReactDOM from "react-dom/client"; 
import ExtensionPopup from "./ExtensionPopup";
import "./style.css";

// Select the root element
const rootElement = document.getElementById("root");

// Create a root using ReactDOM's createRoot
const root = ReactDOM.createRoot(rootElement);
console.log("Popup loaded");
// Render the React component into the DOM
root.render(<ExtensionPopup/>);

