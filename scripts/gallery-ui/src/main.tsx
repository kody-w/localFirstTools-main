import { createRoot } from "react-dom/client"
import App from "./App"
import "./index.css"

const container = document.getElementById("glass-gallery-root") ?? document.getElementById("root")
if (!container) {
  throw new Error("The liquid-glass gallery mount is missing.")
}
createRoot(container, { identifierPrefix: "gallery-" }).render(<App />)
