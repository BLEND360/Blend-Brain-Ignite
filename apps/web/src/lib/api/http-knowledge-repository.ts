import type { ZodType } from "zod"

import { ApiError } from "./api-error"
import {
  dashboardSchema,
  businessArtifactSchema,
  projectCatalogSchema,
  expertSearchSchema,
  projectDetailsSchema,
  projectDnaSchema,
  searchResponseSchema,
  similarProjectsSchema,
  type Dashboard,
  type ExpertSearch,
  type ProjectDetails,
  type ProjectDna,
  type SearchResponse,
  type SimilarProjects,
  type BusinessArtifact,
  type OnePagerRequest,
  type ProposalRequest,
  type ProjectCatalog,
} from "./contracts"
import type { KnowledgeRepository, RequestOptions } from "./knowledge-repository"

type ProblemDetails = {
  detail?: unknown
  code?: unknown
}

function createRequestId(): string {
  const runtimeCrypto = globalThis.crypto as Crypto | undefined
  if (runtimeCrypto && typeof runtimeCrypto.randomUUID === "function") {
    return runtimeCrypto.randomUUID()
  }

  return `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

export class HttpKnowledgeRepository implements KnowledgeRepository {
  readonly #baseUrl: string
  readonly #fetch: typeof fetch
  readonly #bearerToken: string | undefined

  constructor(
    baseUrl: string,
    fetchImplementation: typeof fetch = fetch,
    bearerToken?: string,
  ) {
    this.#baseUrl = baseUrl.replace(/\/$/, "")
    this.#fetch = fetchImplementation.bind(globalThis)
    const normalizedToken = bearerToken?.trim()
    this.#bearerToken = normalizedToken && normalizedToken.length > 0 ? normalizedToken : undefined
  }

  getDashboard(options?: RequestOptions): Promise<Dashboard> {
    return this.#request("/dashboard", dashboardSchema, { signal: options?.signal })
  }

  getProjects(query = "", options?: RequestOptions): Promise<ProjectCatalog> {
    const params = new URLSearchParams({ limit: "1000" })
    if (query.trim()) params.set("query", query.trim())
    return this.#request(`/projects?${params.toString()}`, projectCatalogSchema, {
      signal: options?.signal,
    })
  }

  search(question: string, options?: RequestOptions): Promise<SearchResponse> {
    return this.#request("/questions", searchResponseSchema, {
      method: "POST",
      body: JSON.stringify({ question }),
      signal: options?.signal,
    })
  }

  getProject(projectId: string, options?: RequestOptions): Promise<ProjectDetails> {
    return this.#request(
      `/projects/${encodeURIComponent(projectId)}`,
      projectDetailsSchema,
      { signal: options?.signal },
    )
  }

  getProjectDna(projectId: string, options?: RequestOptions): Promise<ProjectDna> {
    return this.#request(
      `/projects/${encodeURIComponent(projectId)}/dna`,
      projectDnaSchema,
      { signal: options?.signal },
    )
  }

  getSimilarProjects(projectId: string, options?: RequestOptions): Promise<SimilarProjects> {
    return this.#request(
      `/projects/${encodeURIComponent(projectId)}/similar`,
      similarProjectsSchema,
      { signal: options?.signal },
    )
  }

  findExperts(query: string, options?: RequestOptions): Promise<ExpertSearch> {
    return this.#request("/experts/search", expertSearchSchema, {
      method: "POST",
      body: JSON.stringify({ query }),
      signal: options?.signal,
    })
  }

  generateProposal(
    request: ProposalRequest,
    options?: RequestOptions,
  ): Promise<BusinessArtifact> {
    return this.#request("/artifacts/proposals", businessArtifactSchema, {
      method: "POST",
      body: JSON.stringify(request),
      signal: options?.signal,
    })
  }

  generateOnePager(
    request: OnePagerRequest,
    options?: RequestOptions,
  ): Promise<BusinessArtifact> {
    return this.#request("/artifacts/one-pagers", businessArtifactSchema, {
      method: "POST",
      body: JSON.stringify(request),
      signal: options?.signal,
    })
  }

  async exportArtifactPdf(
    artifact: BusinessArtifact,
    options?: RequestOptions,
  ): Promise<Blob> {
    const headers = new Headers({ Accept: "application/pdf", "X-Request-ID": createRequestId() })
    if (this.#bearerToken) headers.set("Authorization", `Bearer ${this.#bearerToken}`)
    const response = await this.#fetch(
      `${this.#baseUrl}/artifacts/${artifact.kind}/${encodeURIComponent(artifact.artifactId)}/pdf`,
      { method: "POST", credentials: "include", headers, signal: options?.signal },
    )
    if (!response.ok) {
      const problem = await this.#readProblem(response)
      throw new ApiError(
        typeof problem.detail === "string" ? problem.detail : "PDF export failed.",
        response.status,
        typeof problem.code === "string" ? problem.code : "pdf_export_failed",
        response.headers.get("X-Request-ID"),
      )
    }
    return response.blob()
  }

  async #request<T>(path: string, schema: ZodType<T>, init: RequestInit): Promise<T> {
    const headers = new Headers(init.headers)
    headers.set("Accept", "application/json")
    headers.set("Content-Type", "application/json")
    headers.set("X-Request-ID", createRequestId())
    if (this.#bearerToken) {
      headers.set("Authorization", `Bearer ${this.#bearerToken}`)
    }
    const response = await this.#fetch(`${this.#baseUrl}${path}`, {
      ...init,
      credentials: "include",
      headers,
    })
    const requestId = response.headers.get("X-Request-ID")
    if (!response.ok) {
      const problem = await this.#readProblem(response)
      throw new ApiError(
        typeof problem.detail === "string" ? problem.detail : "The request could not be completed.",
        response.status,
        typeof problem.code === "string" ? problem.code : "request_failed",
        requestId,
      )
    }
    return schema.parse(await response.json())
  }

  async #readProblem(response: Response): Promise<ProblemDetails> {
    try {
      return (await response.json()) as ProblemDetails
    } catch {
      return {}
    }
  }
}
