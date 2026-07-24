import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { vi } from "vitest"

import { searchResponse, summary } from "@/test/fixtures"
import { createRepository, renderPage } from "@/test/render"

import { SearchPage } from "./search-page"

it("submits a suggested question and renders grounded claims with citations", async () => {
  const repository = createRepository()
  vi.mocked(repository.search).mockResolvedValue(searchResponse)
  renderPage(<SearchPage />, repository, "/search")

  await userEvent.click(
    screen.getByRole("button", { name: "Which projects solved a forecasting challenge?" }),
  )

  expect(await screen.findByText("Planning time was reduced by 30%.")).toBeInTheDocument()
  expect(screen.getByText("“reduced planning time by 30%”")).toBeInTheDocument()
  expect(screen.getByText(/high evidence/i)).toBeInTheDocument()
})

it("renders an explicit abstention without fabricated results", async () => {
  const repository = createRepository()
  vi.mocked(repository.search).mockResolvedValue({
    ...searchResponse,
    answer: {
      ...searchResponse.answer,
      answerable: false,
      answer: null,
      claims: [],
      citations: [],
      confidence: {
        score: 0,
        band: "low",
        breakdown: { retrievalStrength: 0, citationCoverage: 0, sourceDiversity: 0 },
      },
      reason: "The sources do not state this.",
    },
  })
  renderPage(<SearchPage />, repository, "/search?q=Unknown")

  expect(await screen.findByText("The sources do not support an answer")).toBeInTheDocument()
  expect(screen.getByText("The sources do not state this.")).toBeInTheDocument()
})

it("carries cited projects into proposal and one-pager generation", async () => {
  const repository = createRepository()
  const secondProject = { ...summary, id: "project-2", name: "Second Project" }
  const firstCitation = searchResponse.answer.citations[0]
  if (!firstCitation) throw new Error("Search fixture requires one citation")
  vi.mocked(repository.search).mockResolvedValue({
    ...searchResponse,
    answer: {
      ...searchResponse.answer,
      citations: [
        ...searchResponse.answer.citations,
        { ...firstCitation, citationId: "C2", projectId: "project-2" },
      ],
    },
    relatedProjects: [summary, secondProject],
  })
  renderPage(<SearchPage />, repository, "/search?q=Forecasting")

  const projectSelector = await screen.findByLabelText("Project for one-pager")
  await userEvent.selectOptions(projectSelector, "project-2")

  expect(screen.getByRole("link", { name: /Generate proposal/i })).toHaveAttribute(
    "href",
    expect.stringContaining("project=project-1"),
  )
  expect(screen.getByRole("link", { name: /One-pager/i })).toHaveAttribute(
    "href",
    expect.stringContaining("project=project-2"),
  )
  expect(screen.getByText(/2 cited projects selected/i)).toBeInTheDocument()
})

it("submits a typed question and renders a recoverable API failure", async () => {
  const repository = createRepository()
  vi.mocked(repository.search).mockRejectedValue(new Error("unavailable"))
  renderPage(<SearchPage />, repository, "/search")

  await userEvent.type(screen.getByLabelText("Knowledge question"), "Which projects used AWS?")
  await userEvent.click(screen.getByRole("button", { name: /Search knowledge/i }))

  expect(await screen.findByText("Search is temporarily unavailable")).toBeInTheDocument()
  await userEvent.click(screen.getByRole("button", { name: "Try again" }))
  expect(repository.search).toHaveBeenCalled()
})
