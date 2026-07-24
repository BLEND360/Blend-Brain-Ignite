import { useQuery } from "@tanstack/react-query"
import {
  ArrowRight,
  CheckCircle2,
  FileOutput,
  FileText,
  Lightbulb,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react"
import { useState, type SyntheticEvent } from "react"
import { Link, useSearchParams } from "react-router-dom"

import { PageHeader } from "@/components/layout/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusPanel } from "@/components/ui/status-panel"
import { ProjectCard } from "@/features/projects/project-card"
import type { SearchResponse } from "@/lib/api/contracts"
import { searchQuery } from "@/lib/api/queries"
import { useKnowledgeRepository } from "@/lib/api/repository-context"

const suggestedQuestions = [
  "Which projects solved a forecasting challenge?",
  "Where have we implemented Snowflake on AWS?",
  "What measurable outcomes have we delivered in retail?",
]

export function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const question = searchParams.get("q")?.trim() ?? ""
  const repository = useKnowledgeRepository()
  const result = useQuery(searchQuery(repository, question))

  function submit(event: SyntheticEvent<HTMLFormElement, SubmitEvent>) {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)
    const value = formData.get("question")
    const normalized = typeof value === "string" ? value.trim() : ""
    if (normalized) {
      setSearchParams({ q: normalized })
    }
  }

  function ask(suggestion: string) {
    setSearchParams({ q: suggestion })
  }

  return (
    <>
      <PageHeader
        eyebrow="Hybrid retrieval"
        title="Search Blend knowledge"
        description="Ask a natural-language question. Answers are grounded in approved project sources and include evidence you can inspect."
      />
      <form className="mb-7 flex flex-col gap-2 sm:flex-row" role="search" onSubmit={submit}>
        <div className="relative flex-1">
          <Search
            className="absolute top-1/2 left-4 size-[18px] -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            key={question}
            name="question"
            defaultValue={question}
            className="h-13 bg-white pr-4 pl-11 shadow-card"
            placeholder="Ask about a project, solution, industry, or outcome…"
            aria-label="Knowledge question"
          />
        </div>
        <Button size="lg" className="h-13 px-7">
          Search knowledge
          <ArrowRight aria-hidden="true" />
        </Button>
      </form>

      {!question ? <SearchWelcome onSuggestion={ask} /> : null}
      {question && result.isPending ? <SearchSkeleton /> : null}
      {question && result.isError ? (
        <StatusPanel
          kind="error"
          title="Search is temporarily unavailable"
          description="The grounded question-answering API could not complete this request. Your question has not been answered from unverified data."
          actionLabel="Try again"
          onAction={() => void result.refetch()}
        />
      ) : null}
      {question && result.isSuccess ? <SearchResults response={result.data} /> : null}
    </>
  )
}

function SearchWelcome({ onSuggestion }: { onSuggestion: (question: string) => void }) {
  return (
    <Card className="overflow-hidden">
      <div className="grid md:grid-cols-[1fr_0.8fr]">
        <div className="p-6 sm:p-8">
          <div className="grid size-11 place-items-center rounded-2xl bg-primary/8 text-primary">
            <Sparkles className="size-5" aria-hidden="true" />
          </div>
          <h2 className="mt-5 text-xl font-semibold tracking-tight">Start with a business question</h2>
          <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
            The Brain combines semantic and exact-term retrieval, then produces a concise answer only when the source evidence supports it.
          </p>
          <div className="mt-6 space-y-2">
            {suggestedQuestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => onSuggestion(suggestion)}
                className="group flex w-full cursor-pointer items-center justify-between gap-4 rounded-xl border bg-background px-4 py-3 text-left text-sm font-medium transition-colors hover:border-primary/25 hover:bg-primary/3 focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:outline-none"
              >
                {suggestion}
                <ArrowRight
                  className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary"
                  aria-hidden="true"
                />
              </button>
            ))}
          </div>
        </div>
        <div className="surface-grid flex flex-col justify-center bg-[#101f3e] p-6 text-white sm:p-8">
          <ShieldCheck className="size-7 text-[#61d4cb]" aria-hidden="true" />
          <h3 className="mt-5 text-lg font-semibold">Designed to say “not enough evidence.”</h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Every returned claim carries validated source citations. Confidence reflects retrieval and evidence strength—not an AI self-rating.
          </p>
        </div>
      </div>
    </Card>
  )
}

function SearchResults({ response }: { response: SearchResponse }) {
  const { answer } = response
  if (!answer.answerable) {
    return (
      <StatusPanel
        kind="empty"
        title="The sources do not support an answer"
        description={answer.reason ?? "No sufficiently relevant evidence was found for this question."}
      />
    )
  }

  return (
    <div className="grid gap-7 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.75fr)]">
      <div className="space-y-7">
        <Card className="overflow-hidden">
          <div className="border-b bg-gradient-to-r from-primary/5 to-teal-500/5 px-5 py-4 sm:px-7">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-sm font-semibold">
                <Sparkles className="size-4 text-primary" aria-hidden="true" />
                Grounded answer
              </div>
              <ConfidenceBadge band={answer.confidence.band} score={answer.confidence.score} />
            </div>
          </div>
          <div className="p-5 sm:p-7">
            <div className="space-y-4">
              {answer.claims.map((claim, index) => (
                <div key={`${claim.text}-${index}`} className="flex gap-3">
                  <CheckCircle2 className="mt-1 size-4 shrink-0 text-teal-600" aria-hidden="true" />
                  <p className="text-[15px] leading-7 text-foreground/90">
                    {claim.text}{" "}
                    {claim.citationIds.map((citationId) => (
                      <a
                        key={citationId}
                        href={`#citation-${citationId}`}
                        className="ml-0.5 inline-flex min-w-5 items-center justify-center rounded bg-primary/8 px-1.5 py-0.5 align-super text-[10px] font-bold text-primary hover:bg-primary/15 focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:outline-none"
                        aria-label={`View citation ${citationId}`}
                      >
                        {citationId}
                      </a>
                    ))}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </Card>

        <ArtifactActions key={answer.question} response={response} />

        <section aria-labelledby="sources-title">
          <div className="mb-3 flex items-center justify-between">
            <h2 id="sources-title" className="text-lg font-semibold tracking-tight">
              Evidence
            </h2>
            <span className="text-xs text-muted-foreground">
              {answer.citations.length} validated {answer.citations.length === 1 ? "source" : "sources"}
            </span>
          </div>
          <div className="space-y-3">
            {answer.citations.map((citation) => (
              <Card key={citation.citationId} id={`citation-${citation.citationId}`} className="scroll-mt-24 p-5">
                <div className="flex items-start gap-4">
                  <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-muted text-muted-foreground">
                    <FileText className="size-4" aria-hidden="true" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge>{citation.citationId}</Badge>
                      <Link
                        to={`/projects/${encodeURIComponent(citation.projectId)}`}
                        className="truncate text-xs font-semibold hover:text-primary hover:underline"
                      >
                        {citation.filename}
                      </Link>
                      <span className="text-[11px] text-muted-foreground">
                        {citation.pageNumber
                          ? `Page ${citation.pageNumber}`
                          : citation.slideNumber
                            ? `Slide ${citation.slideNumber}`
                            : `Section ${citation.sectionSequence}`}
                      </span>
                    </div>
                    <blockquote className="mt-3 border-l-2 border-primary/25 pl-4 text-sm leading-6 text-muted-foreground">
                      “{citation.quote}”
                    </blockquote>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </section>

        {response.relatedProjects.length > 0 ? (
          <section aria-labelledby="related-title">
            <h2 id="related-title" className="mb-3 text-lg font-semibold tracking-tight">
              Related projects
            </h2>
            <div className="grid gap-4 md:grid-cols-2">
              {response.relatedProjects.map((project) => (
                <ProjectCard key={project.id} project={project} />
              ))}
            </div>
          </section>
        ) : null}
      </div>

      <aside>
        <Card className="sticky top-24">
          <CardHeader>
            <CardTitle>Evidence strength</CardTitle>
            <p className="text-xs leading-5 text-muted-foreground">
              A transparent heuristic, not a probability of truth.
            </p>
          </CardHeader>
          <CardContent className="space-y-5">
            <ConfidenceRow label="Retrieval relevance" value={answer.confidence.breakdown.retrievalStrength} />
            <ConfidenceRow label="Citation coverage" value={answer.confidence.breakdown.citationCoverage} />
            <ConfidenceRow label="Source diversity" value={answer.confidence.breakdown.sourceDiversity} />
            <div className="rounded-xl bg-muted/70 p-4">
              <div className="flex gap-3">
                <Lightbulb className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden="true" />
                <p className="text-xs leading-5 text-muted-foreground">
                  Open the evidence before reusing material in a proposal or client deliverable.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </aside>
    </div>
  )
}

function ArtifactActions({ response }: { response: SearchResponse }) {
  const projectIds = Array.from(
    new Set(response.answer.citations.map((citation) => citation.projectId)),
  )
  const [onePagerProjectId, setOnePagerProjectId] = useState(projectIds[0] ?? "")
  if (!projectIds.length) return null

  const proposalParams = new URLSearchParams()
  projectIds.forEach((projectId) => proposalParams.append("project", projectId))
  proposalParams.set("sourceQuestion", response.answer.question)
  const onePagerParams = new URLSearchParams()
  if (onePagerProjectId) onePagerParams.append("project", onePagerProjectId)
  onePagerParams.set("sourceQuestion", response.answer.question)

  return (
    <Card className="border-primary/15 bg-gradient-to-br from-primary/5 to-teal-500/5">
      <CardHeader>
        <CardTitle>Turn this grounded research into collateral</CardTitle>
        <p className="text-xs leading-5 text-muted-foreground">
          Cited projects are carried forward automatically. Complete only the remaining business fields.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row">
          <Button asChild className="sm:flex-1">
            <Link to={`/proposals?${proposalParams.toString()}`}>
              <FileOutput /> Generate proposal
            </Link>
          </Button>
          <div className="flex min-w-0 flex-1 gap-2">
            <select
              className="min-w-0 flex-1 rounded-lg border border-input bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-primary/25"
              value={onePagerProjectId}
              aria-label="Project for one-pager"
              onChange={(event) => setOnePagerProjectId(event.target.value)}
            >
              {projectIds.map((projectId) => {
                const project = response.relatedProjects.find((item) => item.id === projectId)
                return <option key={projectId} value={projectId}>{project?.name ?? projectId}</option>
              })}
            </select>
            <Button asChild variant="outline">
              <Link to={`/one-pagers?${onePagerParams.toString()}`}>
                <Sparkles /> One-pager
              </Link>
            </Button>
          </div>
        </div>
        <p className="text-[11px] text-muted-foreground">
          {projectIds.length} cited {projectIds.length === 1 ? "project" : "projects"} selected from this answer.
        </p>
      </CardContent>
    </Card>
  )
}

function ConfidenceBadge({ band, score }: { band: "high" | "medium" | "low"; score: number }) {
  const variant = band === "high" ? "success" : band === "medium" ? "warning" : "neutral"
  return (
    <Badge variant={variant}>
      {band} evidence · {Math.round(score * 100)}
    </Badge>
  )
}

function ConfidenceRow({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="mb-2 flex justify-between text-xs">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground">{Math.round(value * 100)}</span>
      </div>
      <Progress value={value * 100} />
    </div>
  )
}

function SearchSkeleton() {
  return (
    <div aria-label="Searching knowledge" aria-busy="true" className="grid gap-7 xl:grid-cols-[1.55fr_0.75fr]">
      <div className="space-y-4">
        <Skeleton className="h-64 rounded-2xl" />
        <Skeleton className="h-36 rounded-2xl" />
        <Skeleton className="h-36 rounded-2xl" />
      </div>
      <Skeleton className="h-80 rounded-2xl" />
    </div>
  )
}
