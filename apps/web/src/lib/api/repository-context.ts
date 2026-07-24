import { createContext, use } from "react"

import type { KnowledgeRepository } from "./knowledge-repository"

export const RepositoryContext = createContext<KnowledgeRepository | null>(null)

export function useKnowledgeRepository(): KnowledgeRepository {
  const repository = use(RepositoryContext)
  if (repository === null) {
    throw new Error("RepositoryProvider is required")
  }
  return repository
}
