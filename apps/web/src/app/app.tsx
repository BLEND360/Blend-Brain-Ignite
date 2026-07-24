import { AppProviders } from "./providers"
import { AppRouter } from "./router"

import type { KnowledgeRepository } from "@/lib/api/knowledge-repository"

type AppProps = {
  repository: KnowledgeRepository
}

export function App({ repository }: AppProps) {
  return (
    <AppProviders repository={repository}>
      <AppRouter />
    </AppProviders>
  )
}
