import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { createRepository, renderPage } from "@/test/render"

import { ExpertFinderPage } from "./expert-finder-page"

it("searches and renders only evidence-ranked experts", async () => {
  const repository = createRepository()
  vi.mocked(repository.findExperts).mockResolvedValue({
    experts: [
      {
        expertId: "expert-1",
        name: "Jane Expert",
        score: 0.91,
        projectIds: ["project-1"],
        matchedSignals: [{ kind: "technology", value: "Snowflake" }],
        evidence: [
          { documentId: "document-1", sectionSequence: 2, quote: "Jane Expert led delivery" },
        ],
      },
    ],
  })
  renderPage(<ExpertFinderPage />, repository, "/experts")

  await userEvent.type(screen.getByLabelText("Expert capability query"), "Snowflake")
  await userEvent.click(screen.getByRole("button", { name: /Find experts/i }))

  expect(await screen.findByText("Jane Expert")).toBeInTheDocument()
  expect(screen.getByText("Snowflake")).toBeInTheDocument()
  expect(repository.findExperts).toHaveBeenCalledWith("Snowflake", expect.any(Object))
})
