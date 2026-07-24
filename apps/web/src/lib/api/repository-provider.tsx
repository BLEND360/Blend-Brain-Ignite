import type { ReactNode } from "react"

import type { KnowledgeRepository } from "./knowledge-repository"
import { RepositoryContext } from "./repository-context"

type RepositoryProviderProps = {
  repository: KnowledgeRepository
  children: ReactNode
}

export function RepositoryProvider({ repository, children }: RepositoryProviderProps) {
  return <RepositoryContext value={repository}>{children}</RepositoryContext>
}
