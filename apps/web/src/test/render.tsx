import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render } from "@testing-library/react"
import type { ReactElement } from "react"
import { MemoryRouter } from "react-router-dom"
import { vi } from "vitest"

import type { KnowledgeRepository } from "@/lib/api/knowledge-repository"
import { RepositoryProvider } from "@/lib/api/repository-provider"

export function createRepository(): KnowledgeRepository {
  return {
    getDashboard: vi.fn(),
    getProjects: vi.fn(),
    search: vi.fn(),
    getProject: vi.fn(),
    getProjectDna: vi.fn(),
    getSimilarProjects: vi.fn().mockResolvedValue({ projects: [] }),
    findExperts: vi.fn(),
    generateProposal: vi.fn(),
    generateOnePager: vi.fn(),
    exportArtifactPdf: vi.fn(),
  }
}

export function renderPage(
  element: ReactElement,
  repository: KnowledgeRepository,
  initialPath = "/",
) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <RepositoryProvider repository={repository}>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[initialPath]}>{element}</MemoryRouter>
      </QueryClientProvider>
    </RepositoryProvider>,
  )
}
