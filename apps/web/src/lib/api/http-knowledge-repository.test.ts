import { HttpKnowledgeRepository } from "./http-knowledge-repository"
import { ApiError } from "./api-error"
import { dashboard } from "@/test/fixtures"
import type { BusinessArtifact } from "./contracts"

describe("HttpKnowledgeRepository", () => {
  it("uses secure request defaults and validates successful responses", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(dashboard), {
        status: 200,
        headers: { "Content-Type": "application/json", "X-Request-ID": "request-1" },
      }),
    )
    const repository = new HttpKnowledgeRepository("/api/v1/", fetchMock)

    await expect(repository.getDashboard()).resolves.toEqual(dashboard)

    const [url, init] = fetchMock.mock.calls[0] ?? []
    expect(url).toBe("/api/v1/dashboard")
    expect(init?.credentials).toBe("include")
    expect(new Headers(init?.headers).get("X-Request-ID")).toBeTruthy()
  })

  it("maps problem details to a stable API error", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Not allowed", code: "forbidden" }), {
        status: 403,
        headers: { "X-Request-ID": "request-2" },
      }),
    )
    const repository = new HttpKnowledgeRepository("/api/v1", fetchMock)

    await expect(repository.getProject("project/secret")).rejects.toEqual(
      new ApiError("Not allowed", 403, "forbidden", "request-2"),
    )
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/projects/project%2Fsecret")
  })

  it("loads the complete project catalog with an optional query", async () => {
    const payload = { projects: dashboard.recentProjects, total: dashboard.totalProjects }
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify(payload), { status: 200 })),
      )
    const repository = new HttpKnowledgeRepository("/api/v1", fetchMock)

    await expect(repository.getProjects(" Retail ")).resolves.toEqual(payload)
    await expect(repository.getProjects()).resolves.toEqual(payload)

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/projects?limit=1000&query=Retail")
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/projects?limit=1000")
  })

  it("posts questions and rejects invalid response contracts", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ answer: "untyped" }), { status: 200 }),
    )
    const repository = new HttpKnowledgeRepository("/api/v1", fetchMock)

    await expect(repository.search("What improved?")).rejects.toThrow()
    const init = fetchMock.mock.calls[0]?.[1]
    expect(init?.method).toBe("POST")
    expect(init?.body).toBe(JSON.stringify({ question: "What improved?" }))
  })

  it("uses safe defaults when an error response is not JSON", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response("upstream failure", { status: 502 }))
    const repository = new HttpKnowledgeRepository("/api/v1", fetchMock)

    await expect(repository.getProjectDna("project-1")).rejects.toMatchObject({
      message: "The request could not be completed.",
      code: "request_failed",
      status: 502,
    })
  })

  it("authenticates and validates intelligence endpoints", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            projects: [
              {
                projectId: "project-2",
                displayName: "Similar project",
                score: 0.8,
                sharedSignals: [{ kind: "industry", value: "Retail" }],
              },
            ],
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            experts: [
              {
                expertId: "expert-1",
                name: "Blend Expert",
                score: 0.9,
                projectIds: ["project-1"],
                matchedSignals: [],
                evidence: [
                  { documentId: "document-1", sectionSequence: 1, quote: "Blend Expert" },
                ],
              },
            ],
          }),
          { status: 200 },
        ),
      )
    const repository = new HttpKnowledgeRepository("/api/v1", fetchMock, "local-token")

    await expect(repository.getSimilarProjects("project-1")).resolves.toMatchObject({
      projects: [{ projectId: "project-2" }],
    })
    await expect(repository.findExperts("retail")).resolves.toMatchObject({
      experts: [{ expertId: "expert-1" }],
    })
    expect(new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get("Authorization")).toBe(
      "Bearer local-token",
    )
    expect(fetchMock.mock.calls[1]?.[1]?.body).toBe(JSON.stringify({ query: "retail" }))
  })

  it("generates grounded artifacts and exports their PDF", async () => {
    const artifact: BusinessArtifact = {
      artifactId: "artifact-1",
      kind: "project_one_pager",
      sourceProjectIds: ["project-1"],
      title: "Retail Forecasting",
      subtitle: "A Blend360 Case Study",
      sections: [],
      status: "draft",
      model: "gpt-4.1",
      promptVersion: "pih-sales-brief-v2",
      createdAt: "2026-07-24T18:00:00Z",
    }
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify(artifact), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ...artifact, kind: "proposal" }), { status: 200 }),
      )
      .mockResolvedValueOnce(new Response(new Blob(["%PDF-test"]), { status: 200 }))
    const repository = new HttpKnowledgeRepository("/api/v1", fetchMock, "local-token")

    await expect(
      repository.generateOnePager({
        requestId: "request-1",
        projectId: "project-1",
        audience: "Sales",
      }),
    ).resolves.toMatchObject({ artifactId: "artifact-1" })
    await expect(
      repository.generateProposal({
        requestId: "request-2",
        projectIds: ["project-1"],
        clientName: "Client",
        audience: "Executives",
        opportunity: "Forecasting",
        objectives: ["Improve plans"],
        constraints: [],
      }),
    ).resolves.toMatchObject({ kind: "proposal" })
    await expect(repository.exportArtifactPdf(artifact)).resolves.toBeInstanceOf(Blob)

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/artifacts/one-pagers")
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/artifacts/proposals")
    expect(fetchMock.mock.calls[2]?.[0]).toBe(
      "/api/v1/artifacts/project_one_pager/artifact-1/pdf",
    )
  })
})
