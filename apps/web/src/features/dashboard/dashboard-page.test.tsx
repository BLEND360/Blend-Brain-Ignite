import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { vi } from "vitest"

import { dashboard } from "@/test/fixtures"
import { createRepository, renderPage } from "@/test/render"

import { DashboardPage } from "./dashboard-page"

it("renders server-backed dashboard metrics and recent projects", async () => {
  const repository = createRepository()
  vi.mocked(repository.getDashboard).mockResolvedValue(dashboard)
  renderPage(<DashboardPage />, repository)

  expect(await screen.findByText("1.2K")).toBeInTheDocument()
  expect(screen.getByText("Retail Demand Forecasting")).toBeInTheDocument()
  expect(screen.getByText("78%")).toBeInTheDocument()

  await userEvent.click(screen.getByRole("link", { name: /Retail Demand Forecasting/i }))
  expect(window.location.pathname).toBeDefined()
})

it("renders honest empty states and submits a knowledge question", async () => {
  const repository = createRepository()
  vi.mocked(repository.getDashboard).mockResolvedValue({
    ...dashboard,
    totalProjects: 0,
    indexedDocuments: 0,
    identifiedExperts: 0,
    knowledgeCoverage: 0,
    recentProjects: [],
    topIndustries: [],
  })
  renderPage(<DashboardPage />, repository)

  expect(await screen.findByText("No enriched projects yet")).toBeInTheDocument()
  expect(screen.getByText("No industry classification is available.")).toBeInTheDocument()
  await userEvent.type(screen.getByLabelText("Ask a question about Blend projects"), "Snowflake outcomes")
  await userEvent.click(screen.getByRole("button", { name: /Ask the Brain/i }))
})

it("renders a recoverable dashboard API failure", async () => {
  const repository = createRepository()
  vi.mocked(repository.getDashboard).mockRejectedValue(new Error("unavailable"))
  renderPage(<DashboardPage />, repository)

  expect(await screen.findByText("Knowledge overview is unavailable")).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Try again" }))
  expect(repository.getDashboard).toHaveBeenCalled()
})
