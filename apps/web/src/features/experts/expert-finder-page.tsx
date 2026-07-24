import { useQuery } from "@tanstack/react-query"
import { ArrowRight, Search, ShieldCheck, UserRound } from "lucide-react"
import type { SyntheticEvent } from "react"
import { Link, useSearchParams } from "react-router-dom"

import { PageHeader } from "@/components/layout/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusPanel } from "@/components/ui/status-panel"
import { expertSearchQuery } from "@/lib/api/queries"
import { useKnowledgeRepository } from "@/lib/api/repository-context"

export function ExpertFinderPage() {
  const [params, setParams] = useSearchParams()
  const query = params.get("q")?.trim() ?? ""
  const repository = useKnowledgeRepository()
  const result = useQuery(expertSearchQuery(repository, query))

  function submit(event: SyntheticEvent<HTMLFormElement, SubmitEvent>) {
    event.preventDefault()
    const value = new FormData(event.currentTarget).get("query")
    const normalized = typeof value === "string" ? value.trim() : ""
    if (normalized) setParams({ q: normalized })
  }

  return (
    <>
      <PageHeader
        eyebrow="Evidence-backed expertise"
        title="Find the right Blend expert"
        description="Search by capability, technology, industry, or business problem. Rankings use relevant projects and retain their source evidence."
      />
      <form className="mb-7 flex flex-col gap-2 sm:flex-row" role="search" onSubmit={submit}>
        <div className="relative flex-1">
          <Search className="absolute top-1/2 left-4 size-[18px] -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input
            key={query}
            name="query"
            defaultValue={query}
            className="h-13 bg-white pl-11 shadow-card"
            placeholder="e.g. Snowflake retail forecasting"
            aria-label="Expert capability query"
          />
        </div>
        <Button size="lg" className="h-13 px-7">
          Find experts <ArrowRight aria-hidden="true" />
        </Button>
      </form>

      {!query ? (
        <StatusPanel
          kind="empty"
          title="Describe the expertise you need"
          description="Only experts explicitly identified in accessible project sources can appear."
        />
      ) : null}
      {query && result.isPending ? <Skeleton className="h-80 rounded-2xl" /> : null}
      {query && result.isError ? (
        <StatusPanel
          kind="error"
          title="Expert search is unavailable"
          description="The evidence-ranked expert index could not complete this search."
          actionLabel="Try again"
          onAction={() => void result.refetch()}
        />
      ) : null}
      {query && result.isSuccess && result.data.experts.length === 0 ? (
        <StatusPanel
          kind="empty"
          title="No grounded expert matches"
          description="No source-named experts met the relevance threshold for this query."
        />
      ) : null}
      {result.data?.experts.length ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {result.data.experts.map((expert) => (
            <Card key={expert.expertId}>
              <CardHeader className="flex-row items-start gap-4">
                <div className="grid size-11 place-items-center rounded-2xl bg-primary/8 text-primary">
                  <UserRound className="size-5" aria-hidden="true" />
                </div>
                <div className="min-w-0 flex-1">
                  <CardTitle>{expert.name}</CardTitle>
                  <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                    <ShieldCheck className="size-3.5 text-emerald-600" aria-hidden="true" />
                    {Math.round(expert.score * 100)}% relevance · {expert.projectIds.length} projects
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <Progress value={expert.score * 100} />
                <div className="mt-4 flex flex-wrap gap-2">
                  {expert.matchedSignals.map((signal) => (
                    <Badge key={`${signal.kind}-${signal.value}`} variant="neutral">{signal.value}</Badge>
                  ))}
                </div>
                <div className="mt-5 space-y-2">
                  {expert.projectIds.slice(0, 4).map((projectId) => (
                    <Link key={projectId} className="block truncate text-xs font-semibold text-primary hover:underline" to={`/projects/${encodeURIComponent(projectId)}`}>
                      View supporting project {projectId.slice(0, 18)}…
                    </Link>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}
    </>
  )
}
