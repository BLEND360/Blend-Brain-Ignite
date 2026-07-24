import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { useState, type ReactNode } from "react"

import type { KnowledgeRepository } from "@/lib/api/knowledge-repository"
import { RepositoryProvider } from "@/lib/api/repository-provider"

type AppProvidersProps = {
  repository: KnowledgeRepository
  children: ReactNode
}

export function AppProviders({ repository, children }: AppProvidersProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: (failureCount, error) =>
              !(error instanceof DOMException && error.name === "AbortError") && failureCount < 2,
            refetchOnWindowFocus: false,
          },
        },
      }),
  )

  return (
    <RepositoryProvider repository={repository}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </RepositoryProvider>
  )
}
