import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import { App } from "@/app/app"
import { HttpKnowledgeRepository } from "@/lib/api/http-knowledge-repository"

import "./styles.css"

const root = document.getElementById("root")
if (root === null) {
  throw new Error("Application root element is missing")
}

const repository = new HttpKnowledgeRepository(
  import.meta.env.VITE_API_BASE_URL ?? "/api/v1",
  fetch,
  import.meta.env.VITE_API_BEARER_TOKEN,
)

createRoot(root).render(
  <StrictMode>
    <App repository={repository} />
  </StrictMode>,
)
