import { useQuery } from "@tanstack/react-query"
import {
  ArrowLeft,
  BrainCircuit,
  CheckCircle2,
  Cloud,
  FileText,
  Layers3,
  Target,
  UserRound,
} from "lucide-react"
import { Link, useParams } from "react-router-dom"

import { PageHeader } from "@/components/layout/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusPanel } from "@/components/ui/status-panel"
import { ProjectNavigation } from "@/features/projects/project-navigation"
import { projectQuery } from "@/lib/api/queries"
import { similarProjectsQuery } from "@/lib/api/queries"
import { useKnowledgeRepository } from "@/lib/api/repository-context"
import { formatDate } from "@/lib/utils"

const formatLabels = {
  pptx: "PowerPoint",
  docx: "Word",
  pdf: "PDF",
  markdown: "Markdown",
  txt: "Text",
}

export function ProjectDetailsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  if (!projectId) {
    throw new Error("Project identifier is required")
  }
  const repository = useKnowledgeRepository()
  const project = useQuery(projectQuery(repository, projectId))
  const similar = useQuery(similarProjectsQuery(repository, projectId))

  if (project.isPending) {
    return <ProjectSkeleton />
  }
  if (project.isError) {
    return (
      <StatusPanel
        kind="error"
        title="Project intelligence is unavailable"
        description="This project could not be loaded from the platform API."
        actionLabel="Try again"
        onAction={() => void project.refetch()}
      />
    )
  }

  const data = project.data
  return (
    <>
      <Button asChild variant="ghost" size="sm" className="mb-4 -ml-3">
        <Link to="/">
          <ArrowLeft aria-hidden="true" /> Dashboard
        </Link>
      </Button>
      <PageHeader
        eyebrow={data.engagementType ?? "Blend project"}
        title={data.name}
        description={[data.client, data.industry, `Updated ${formatDate(data.updatedAt)}`]
          .filter(Boolean)
          .join(" · ")}
        actions={
          data.dna ? (
            <Button asChild variant="outline">
              <Link to={`/projects/${encodeURIComponent(data.id)}/dna`}>
                <BrainCircuit aria-hidden="true" /> View Project DNA
              </Link>
            </Button>
          ) : undefined
        }
      />
      <ProjectNavigation projectId={data.id} />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(300px,0.65fr)]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Project overview</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-7 text-foreground/85">
                {data.summary ?? "No source-grounded project summary is available."}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Similar Blend projects</CardTitle>
              <p className="text-xs text-muted-foreground">Project DNA similarity with shared graph signals</p>
            </CardHeader>
            <CardContent className="space-y-3">
              {similar.isPending ? <Skeleton className="h-28 rounded-xl" /> : null}
              {similar.isError ? <p className="text-sm text-muted-foreground">Similarity is temporarily unavailable.</p> : null}
              {similar.data?.projects.map((match) => (
                <Link key={match.projectId} to={`/projects/${encodeURIComponent(match.projectId)}`} className="block rounded-xl border p-4 transition-colors hover:border-primary/30 hover:bg-primary/3">
                  <div className="flex items-start justify-between gap-4">
                    <p className="text-sm font-semibold">{match.displayName}</p>
                    <Badge variant="neutral">{Math.round(match.score * 100)}%</Badge>
                  </div>
                  <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">
                    {match.sharedSignals.map((signal) => signal.value).join(" · ") || "Semantic Project DNA match"}
                  </p>
                </Link>
              ))}
              {similar.isSuccess && similar.data.projects.length === 0 ? (
                <p className="text-sm text-muted-foreground">No projects meet the similarity threshold.</p>
              ) : null}
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            <NarrativeCard icon={Target} title="Business challenge" value={data.challenge} />
            <NarrativeCard icon={Layers3} title="Solution" value={data.solution} />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Outcomes</CardTitle>
            </CardHeader>
            <CardContent>
              {data.outcomes.length > 0 ? (
                <ul className="grid gap-3 sm:grid-cols-2">
                  {data.outcomes.map((outcome) => (
                    <li key={outcome} className="flex gap-3 rounded-xl bg-emerald-50/70 p-4 text-sm leading-6">
                      <CheckCircle2 className="mt-1 size-4 shrink-0 text-emerald-600" aria-hidden="true" />
                      {outcome}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">No verified outcomes were extracted.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Source documents</CardTitle>
              <p className="text-xs text-muted-foreground">Knowledge used to construct this project profile</p>
            </CardHeader>
            <CardContent className="divide-y p-0 sm:px-6 sm:pb-6">
              {data.documents.length > 0 ? (
                data.documents.map((document) => (
                  <div key={document.id} className="flex items-center gap-4 py-4 first:pt-0 last:pb-0">
                    <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-muted text-muted-foreground">
                      <FileText className="size-[18px]" aria-hidden="true" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold">{document.filename}</p>
                      <p className="mt-1 text-[11px] text-muted-foreground">
                        {formatLabels[document.format]} · {document.sectionCount} sections · Updated {formatDate(document.updatedAt)}
                      </p>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">No accessible documents are attached.</p>
              )}
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Technology footprint</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {data.technologies.length > 0 ? (
                  data.technologies.map((technology) => <Badge key={technology}>{technology}</Badge>)
                ) : (
                  <span className="text-sm text-muted-foreground">No technologies extracted.</span>
                )}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Capabilities</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {data.capabilities.length > 0 ? (
                data.capabilities.map((capability) => (
                  <div key={capability} className="flex items-center gap-3 text-sm">
                    <Cloud className="size-4 shrink-0 text-primary" aria-hidden="true" />
                    {capability}
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">No capabilities extracted.</p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Project experts</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {data.experts.length > 0 ? (
                data.experts.map((expert) => (
                  <div key={expert.id} className="flex items-center gap-3">
                    <div className="grid size-9 place-items-center rounded-full bg-primary/8 text-primary">
                      <UserRound className="size-4" aria-hidden="true" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold">{expert.name}</p>
                      {expert.role ? <p className="text-xs text-muted-foreground">{expert.role}</p> : null}
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">No experts are identified in the sources.</p>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>
    </>
  )
}

function NarrativeCard({
  icon: Icon,
  title,
  value,
}: {
  icon: typeof Target
  title: string
  value: string | null
}) {
  return (
    <Card className="p-5 sm:p-6">
      <div className="mb-4 grid size-9 place-items-center rounded-xl bg-primary/8 text-primary">
        <Icon className="size-4" aria-hidden="true" />
      </div>
      <h2 className="text-sm font-semibold">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        {value ?? "No grounded information is available."}
      </p>
    </Card>
  )
}

function ProjectSkeleton() {
  return (
    <div aria-label="Loading project" aria-busy="true">
      <Skeleton className="h-24 w-2xl max-w-full" />
      <Skeleton className="mt-6 h-12" />
      <div className="mt-6 grid gap-6 xl:grid-cols-[1.45fr_0.65fr]">
        <Skeleton className="h-[34rem] rounded-2xl" />
        <Skeleton className="h-[24rem] rounded-2xl" />
      </div>
    </div>
  )
}
