import { useQuery } from "@tanstack/react-query"
import {
  ArrowRight,
  BrainCircuit,
  FileStack,
  FolderKanban,
  Search,
  Sparkles,
  UsersRound,
} from "lucide-react"
import { type SyntheticEvent, useState } from "react"
import { Link, useNavigate } from "react-router-dom"

import { PageHeader } from "@/components/layout/page-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusPanel } from "@/components/ui/status-panel"
import { ProjectCard } from "@/features/projects/project-card"
import { dashboardQuery } from "@/lib/api/queries"
import { useKnowledgeRepository } from "@/lib/api/repository-context"
import { formatCompactNumber, formatDate } from "@/lib/utils"

export function DashboardPage() {
  const repository = useKnowledgeRepository()
  const dashboard = useQuery(dashboardQuery(repository))
  const navigate = useNavigate()
  const [question, setQuestion] = useState("")

  function submit(event: SyntheticEvent<HTMLFormElement, SubmitEvent>) {
    event.preventDefault()
    const normalized = question.trim()
    if (normalized) {
      void navigate(`/search?q=${encodeURIComponent(normalized)}`)
    }
  }

  if (dashboard.isPending) {
    return <DashboardSkeleton />
  }
  if (dashboard.isError) {
    const errorMessage =
      dashboard.error instanceof Error ? dashboard.error.message : "Unknown dashboard error"
    return (
      <StatusPanel
        kind="error"
        title="Knowledge overview is unavailable"
        description={`The dashboard API could not be reached: ${errorMessage}`}
        actionLabel="Try again"
        onAction={() => void dashboard.refetch()}
      />
    )
  }

  const data = dashboard.data
  return (
    <>
      <PageHeader
        eyebrow="Organizational intelligence"
        title="Good to have the whole story."
        description={`Your view of Blend's project memory, grounded in indexed source material. Last synchronized ${formatDate(data.updatedAt)}.`}
      />

      <section className="surface-grid relative mb-7 overflow-hidden rounded-3xl bg-[#101f3e] px-5 py-7 text-white shadow-xl shadow-slate-900/10 sm:px-8 sm:py-9">
        <div className="absolute -top-24 -right-20 size-72 rounded-full bg-[#3968ff]/25 blur-3xl" />
        <div className="absolute -bottom-32 left-1/3 size-64 rounded-full bg-[#22b7aa]/15 blur-3xl" />
        <div className="relative max-w-3xl">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/6 px-3 py-1.5 text-[11px] font-semibold text-[#8ee4dc]">
            <Sparkles className="size-3.5" aria-hidden="true" />
            Grounded answers across Blend knowledge
          </div>
          <h2 className="text-balance text-2xl leading-tight font-semibold tracking-[-0.025em] sm:text-3xl">
            What do you want to know about our work?
          </h2>
          <p className="mt-2 max-w-xl text-sm leading-6 text-slate-300">
            Ask about solutions, outcomes, technology choices, industries, or relevant experience.
          </p>
          <form className="mt-6 flex flex-col gap-2 sm:flex-row" role="search" onSubmit={submit}>
            <div className="relative flex-1">
              <Search
                className="absolute top-1/2 left-4 size-[18px] -translate-y-1/2 text-slate-400"
                aria-hidden="true"
              />
              <Input
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                className="h-13 border-white/10 bg-white text-slate-900 shadow-xl pl-11"
                placeholder="e.g. Which projects used demand forecasting?"
                aria-label="Ask a question about Blend projects"
              />
            </div>
            <Button size="lg" className="h-13 bg-[#5a78ff] hover:bg-[#6a85ff]">
              Ask the Brain
              <ArrowRight aria-hidden="true" />
            </Button>
          </form>
        </div>
      </section>

      <section aria-labelledby="metrics-title">
        <h2 id="metrics-title" className="sr-only">
          Knowledge metrics
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Projects remembered"
            value={formatCompactNumber(data.totalProjects)}
            icon={FolderKanban}
            accent="blue"
          />
          <MetricCard
            label="Documents indexed"
            value={formatCompactNumber(data.indexedDocuments)}
            icon={FileStack}
            accent="teal"
          />
          <MetricCard
            label="Experts identified"
            value={formatCompactNumber(data.identifiedExperts)}
            icon={UsersRound}
            accent="violet"
          />
          <Card className="p-5 sm:p-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-muted-foreground">Knowledge coverage</p>
                <p className="mt-2 text-2xl font-semibold tracking-tight">
                  {Math.round(data.knowledgeCoverage * 100)}%
                </p>
              </div>
              <div className="grid size-10 place-items-center rounded-xl bg-amber-50 text-amber-600">
                <BrainCircuit className="size-[18px]" aria-hidden="true" />
              </div>
            </div>
            <Progress className="mt-5" value={data.knowledgeCoverage * 100} />
          </Card>
        </div>
      </section>

      <div className="mt-7 grid gap-7 xl:grid-cols-[minmax(0,2fr)_minmax(280px,0.8fr)]">
        <section aria-labelledby="recent-projects-title">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 id="recent-projects-title" className="text-lg font-semibold tracking-tight">
                Recently enriched projects
              </h2>
              <p className="mt-1 text-xs text-muted-foreground">Latest additions to organizational memory</p>
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link to="/search">
                Explore all <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
          </div>
          {data.recentProjects.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2">
              {data.recentProjects.slice(0, 4).map((project) => (
                <ProjectCard key={project.id} project={project} />
              ))}
            </div>
          ) : (
            <StatusPanel
              kind="empty"
              title="No enriched projects yet"
              description="Projects will appear here after approved source documents complete enrichment."
            />
          )}
        </section>

        <section aria-labelledby="industries-title">
          <Card>
            <CardHeader>
              <CardTitle id="industries-title">Knowledge by industry</CardTitle>
              <p className="text-xs text-muted-foreground">Indexed project distribution</p>
            </CardHeader>
            <CardContent className="space-y-5">
              {data.topIndustries.length > 0 ? (
                data.topIndustries.slice(0, 6).map((industry) => {
                  const maximum = Math.max(...data.topIndustries.map((item) => item.projectCount))
                  return (
                    <div key={industry.name}>
                      <div className="mb-2 flex items-center justify-between text-xs">
                        <span className="font-medium">{industry.name}</span>
                        <span className="text-muted-foreground">{industry.projectCount}</span>
                      </div>
                      <Progress value={(industry.projectCount / maximum) * 100} />
                    </div>
                  )
                })
              ) : (
                <p className="text-sm text-muted-foreground">No industry classification is available.</p>
              )}
            </CardContent>
          </Card>
        </section>
      </div>
    </>
  )
}

type MetricCardProps = {
  label: string
  value: string
  icon: typeof FolderKanban
  accent: "blue" | "teal" | "violet"
}

const accents = {
  blue: "bg-blue-50 text-blue-600",
  teal: "bg-teal-50 text-teal-600",
  violet: "bg-violet-50 text-violet-600",
}

function MetricCard({ label, value, icon: Icon, accent }: MetricCardProps) {
  return (
    <Card className="p-5 sm:p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          <p className="mt-2 text-2xl font-semibold tracking-tight">{value}</p>
        </div>
        <div className={`grid size-10 place-items-center rounded-xl ${accents[accent]}`}>
          <Icon className="size-[18px]" aria-hidden="true" />
        </div>
      </div>
    </Card>
  )
}

function DashboardSkeleton() {
  return (
    <div aria-label="Loading dashboard" aria-busy="true">
      <Skeleton className="h-18 w-96 max-w-full" />
      <Skeleton className="mt-7 h-72 rounded-3xl" />
      <div className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-32 rounded-2xl" />
        ))}
      </div>
    </div>
  )
}
