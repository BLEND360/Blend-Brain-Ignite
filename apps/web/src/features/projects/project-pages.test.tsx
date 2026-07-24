import { screen } from "@testing-library/react"
import { Route, Routes } from "react-router-dom"
import { vi } from "vitest"

import { dna, project } from "@/test/fixtures"
import { createRepository, renderPage } from "@/test/render"

import { ProjectDetailsPage } from "./project-details-page"
import { ProjectDnaPage } from "./project-dna-page"

it("renders project overview, outcomes, documents, and experts", async () => {
  const repository = createRepository()
  vi.mocked(repository.getProject).mockResolvedValue(project)
  renderPage(
    <Routes>
      <Route path="/projects/:projectId" element={<ProjectDetailsPage />} />
    </Routes>,
    repository,
    "/projects/project-1",
  )

  expect(await screen.findByRole("heading", { name: project.name })).toBeInTheDocument()
  expect(screen.getByText("Reduced planning time by 30%")).toBeInTheDocument()
  expect(screen.getByText("retail-forecasting.pdf")).toBeInTheDocument()
  expect(screen.getByText("Blend Expert")).toBeInTheDocument()
})

it("renders structured Project DNA and expandable evidence", async () => {
  const repository = createRepository()
  vi.mocked(repository.getProjectDna).mockResolvedValue(dna)
  renderPage(
    <Routes>
      <Route path="/projects/:projectId/dna" element={<ProjectDnaPage />} />
    </Routes>,
    repository,
    "/projects/project-1/dna",
  )

  expect(await screen.findByRole("heading", { name: project.name })).toBeInTheDocument()
  expect(screen.getByText("Manual forecasting constrained planners")).toBeInTheDocument()
  expect(screen.getAllByText(/View 1 evidence source/).length).toBeGreaterThan(0)
  expect(screen.getAllByText("No supported claims were extracted.")).toHaveLength(2)
})

it("renders project fields as unavailable instead of inventing content", async () => {
  const repository = createRepository()
  vi.mocked(repository.getProject).mockResolvedValue({
    ...project,
    summary: null,
    challenge: null,
    solution: null,
    outcomes: [],
    technologies: [],
    capabilities: [],
    experts: [],
    documents: [],
    dna: null,
  })
  renderPage(
    <Routes>
      <Route path="/projects/:projectId" element={<ProjectDetailsPage />} />
    </Routes>,
    repository,
    "/projects/project-1",
  )

  expect(await screen.findByText("No source-grounded project summary is available.")).toBeInTheDocument()
  expect(screen.getAllByText("No grounded information is available.")).toHaveLength(2)
  expect(screen.getByText("No verified outcomes were extracted.")).toBeInTheDocument()
  expect(screen.getByText("No accessible documents are attached.")).toBeInTheDocument()
  expect(screen.getByText("No technologies extracted.")).toBeInTheDocument()
  expect(screen.getByText("No capabilities extracted.")).toBeInTheDocument()
  expect(screen.getByText("No experts are identified in the sources.")).toBeInTheDocument()
})

it("renders a recoverable project load failure", async () => {
  const repository = createRepository()
  vi.mocked(repository.getProject).mockRejectedValue(new Error("unavailable"))
  renderPage(
    <Routes>
      <Route path="/projects/:projectId" element={<ProjectDetailsPage />} />
    </Routes>,
    repository,
    "/projects/project-1",
  )

  expect(await screen.findByText("Project intelligence is unavailable")).toBeInTheDocument()
})

it("renders sparse DNA and a recoverable DNA load failure", async () => {
  const repository = createRepository()
  vi.mocked(repository.getProjectDna).mockResolvedValue({
    ...dna,
    projectName: null,
    clientName: null,
    summary: null,
    businessChallenges: [],
  })
  const view = renderPage(
    <Routes>
      <Route path="/projects/:projectId/dna" element={<ProjectDnaPage />} />
    </Routes>,
    repository,
    "/projects/project-1/dna",
  )
  expect(await screen.findByRole("heading", { name: "Project DNA" })).toBeInTheDocument()
  expect(screen.getByText("Not established")).toBeInTheDocument()
  view.unmount()

  vi.mocked(repository.getProjectDna).mockRejectedValue(new Error("unavailable"))
  renderPage(
    <Routes>
      <Route path="/projects/:projectId/dna" element={<ProjectDnaPage />} />
    </Routes>,
    repository,
    "/projects/another-project/dna",
  )
  expect(await screen.findByText("Project DNA is unavailable")).toBeInTheDocument()
})
