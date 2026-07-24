import { useMutation, useQuery } from "@tanstack/react-query"
import { Check, ChevronDown, Download, FileOutput, LoaderCircle, Sparkles, X } from "lucide-react"
import { useState, type SyntheticEvent } from "react"
import { useSearchParams } from "react-router-dom"

import { PageHeader } from "@/components/layout/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { StatusPanel } from "@/components/ui/status-panel"
import type { BusinessArtifact } from "@/lib/api/contracts"
import { projectCatalogQuery } from "@/lib/api/queries"
import { useKnowledgeRepository } from "@/lib/api/repository-context"

type ArtifactGeneratorPageProps = {
  kind: "proposal" | "project_one_pager"
}

const fieldClass =
  "min-h-28 w-full rounded-xl border border-input bg-white px-4 py-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/15"

function requestId(): string {
  const runtimeCrypto = globalThis.crypto as Crypto | undefined
  if (runtimeCrypto && typeof runtimeCrypto.randomUUID === "function") {
    return runtimeCrypto.randomUUID()
  }
  return `artifact-${Date.now().toString(36)}`
}

function text(value: FormDataEntryValue | null): string {
  return typeof value === "string" ? value : ""
}

function lines(value: FormDataEntryValue | null): string[] {
  return typeof value === "string"
    ? value.split("\n").map((item) => item.trim()).filter(Boolean)
    : []
}

export function ArtifactGeneratorPage({ kind }: ArtifactGeneratorPageProps) {
  const [searchParams] = useSearchParams()
  const repository = useKnowledgeRepository()
  const catalog = useQuery(projectCatalogQuery(repository))
  const [projectQuery, setProjectQuery] = useState("")
  const [projectDropdownOpen, setProjectDropdownOpen] = useState(false)
  const [selectedProjectIds, setSelectedProjectIds] = useState<string[]>(() =>
    Array.from(new Set(searchParams.getAll("project").map((id) => id.trim()).filter(Boolean)))
  )
  const [artifact, setArtifact] = useState<BusinessArtifact | null>(null)
  const [exporting, setExporting] = useState(false)
  const isProposal = kind === "proposal"
  const sourceQuestion = searchParams.get("sourceQuestion")?.trim() ?? ""
  const hasSearchSources = searchParams.getAll("project").length > 0
  const visibleProjects = catalog.data?.projects.filter((project) => {
    const query = projectQuery.trim().toLocaleLowerCase()
    return !query || [project.name, project.client, project.industry]
      .filter(Boolean)
      .some((value) => value?.toLocaleLowerCase().includes(query))
  }) ?? []
  const selectedProjects = catalog.data?.projects.filter((project) =>
    selectedProjectIds.includes(project.id)
  ) ?? []

  function selectProject(projectId: string) {
    setSelectedProjectIds((current) => {
      if (!isProposal) return [projectId]
      return current.includes(projectId)
        ? current.filter((id) => id !== projectId)
        : [...current, projectId]
    })
    setProjectQuery("")
    if (!isProposal) setProjectDropdownOpen(false)
  }

  function removeProject(projectId: string) {
    setSelectedProjectIds((current) => current.filter((id) => id !== projectId))
  }
  const generation = useMutation({
    mutationFn: async (form: FormData) => {
      const projectIds = form.getAll("projectId").filter((value): value is string => typeof value === "string")
      if (!projectIds.length) throw new Error("Select at least one source project.")
      if (isProposal) {
        return repository.generateProposal({
          requestId: requestId(),
          projectIds,
          clientName: text(form.get("clientName")),
          audience: text(form.get("audience")),
          opportunity: text(form.get("opportunity")),
          objectives: lines(form.get("objectives")),
          constraints: lines(form.get("constraints")),
        })
      }
      return repository.generateOnePager({
        requestId: requestId(),
        projectId: projectIds[0] ?? "",
        audience: text(form.get("audience")),
      })
    },
    onSuccess: setArtifact,
  })

  function submit(event: SyntheticEvent<HTMLFormElement, SubmitEvent>) {
    event.preventDefault()
    generation.mutate(new FormData(event.currentTarget))
  }

  async function exportPdf() {
    if (!artifact) return
    setExporting(true)
    try {
      const blob = await repository.exportArtifactPdf(artifact)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = `${artifact.kind}-${artifact.artifactId}.pdf`
      anchor.click()
      URL.revokeObjectURL(url)
    } finally {
      setExporting(false)
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Grounded business collateral"
        title={isProposal ? "Proposal Generator" : "Project One-Pager Generator"}
        description={isProposal
          ? "Create a source-grounded proposal draft from selected Blend project evidence."
          : "Create the required PIH Hackathon one-page sales brief using the supplied format."}
      />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
        <Card className="min-w-0">
          <CardHeader><CardTitle>Generation brief</CardTitle></CardHeader>
          <CardContent>
            <form className="space-y-5" onSubmit={submit}>
              {isProposal ? <Input name="clientName" required placeholder="Client name" /> : null}
              <Input name="audience" required placeholder="Audience, e.g. sales and account teams" />
              {isProposal ? (
                <>
                  <textarea className={fieldClass} name="opportunity" required defaultValue={sourceQuestion} placeholder="Opportunity or client need" />
                  <textarea className={fieldClass} name="objectives" required placeholder="Objectives — one per line" />
                  <textarea className={fieldClass} name="constraints" placeholder="Constraints — one per line (optional)" />
                </>
              ) : null}
              <fieldset>
                <legend className="mb-3 text-sm font-semibold">Source project{isProposal ? "s" : ""}</legend>
                {hasSearchSources ? <div className="mb-3 rounded-xl border border-primary/15 bg-primary/5 px-4 py-3 text-xs leading-5 text-primary">Source projects were selected automatically from the grounded Search Knowledge result. You can adjust them below if needed.</div> : null}
                <div className="relative">
                  <Input
                    value={projectQuery}
                    role="combobox"
                    aria-expanded={projectDropdownOpen}
                    aria-controls="project-options"
                    aria-autocomplete="list"
                    onFocus={() => setProjectDropdownOpen(true)}
                    onKeyDown={(event) => {
                      if (event.key === "Escape") setProjectDropdownOpen(false)
                    }}
                    onChange={(event) => {
                      setProjectQuery(event.target.value)
                      setProjectDropdownOpen(true)
                    }}
                    placeholder="Search by project, client, or industry"
                  />
                  <button
                    type="button"
                    className="absolute top-1/2 right-3 grid size-7 -translate-y-1/2 place-items-center rounded-md text-muted-foreground hover:bg-muted"
                    aria-label={projectDropdownOpen ? "Close project options" : "Open project options"}
                    onClick={() => setProjectDropdownOpen((open) => !open)}
                  >
                    <ChevronDown className={`size-4 transition-transform ${projectDropdownOpen ? "rotate-180" : ""}`} />
                  </button>
                  {projectDropdownOpen ? (
                    <div id="project-options" role="listbox" aria-multiselectable={isProposal} className="absolute z-40 mt-2 max-h-80 w-full min-w-0 overflow-y-auto overflow-x-hidden rounded-xl border bg-white p-1.5 shadow-xl">
                      {visibleProjects.length ? visibleProjects.map((project) => {
                        const selected = selectedProjectIds.includes(project.id)
                        return (
                          <button
                            key={project.id}
                            type="button"
                            role="option"
                            aria-selected={selected}
                            className={`flex w-full min-w-0 items-start gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-muted/60 ${selected ? "bg-primary/8" : ""}`}
                            onClick={() => selectProject(project.id)}
                          >
                            <span className={`mt-0.5 grid size-5 shrink-0 place-items-center rounded border ${selected ? "border-primary bg-primary text-white" : "border-input"}`}>
                              {selected ? <Check className="size-3.5" /> : null}
                            </span>
                            <span className="min-w-0 flex-1">
                              <strong className="block break-words whitespace-normal text-sm leading-5">{project.name}</strong>
                              <span className="mt-0.5 block break-words whitespace-normal text-xs leading-4 text-muted-foreground">{project.client ?? project.industry ?? "Blend project"}</span>
                            </span>
                          </button>
                        )
                      }) : <p className="px-3 py-6 text-center text-sm text-muted-foreground">No matching projects</p>}
                    </div>
                  ) : null}
                </div>
                {catalog.isPending ? <p className="text-sm text-muted-foreground">Loading complete project catalog…</p> : null}
                {catalog.data ? <p className="mt-2 text-xs text-muted-foreground">{visibleProjects.length} matching · {catalog.data.total} accessible projects</p> : null}
                <div className="mt-3 flex flex-wrap gap-2">
                  {selectedProjects.map((project) => (
                    <span key={project.id} className="inline-flex max-w-full items-center gap-2 rounded-lg bg-primary/8 px-3 py-1.5 text-xs font-medium text-primary">
                      <span className="min-w-0 break-words whitespace-normal">{project.name}</span>
                      <button type="button" className="shrink-0 rounded hover:bg-primary/10" aria-label={`Remove ${project.name}`} onClick={() => removeProject(project.id)}><X className="size-3.5" /></button>
                    </span>
                  ))}
                </div>
                {selectedProjectIds.map((projectId) => <input key={projectId} type="hidden" name="projectId" value={projectId} />)}
              </fieldset>
              <Button className="w-full" size="lg" disabled={generation.isPending || catalog.isPending}>
                {generation.isPending ? <LoaderCircle className="animate-spin" /> : isProposal ? <FileOutput /> : <Sparkles />}
                {generation.isPending ? "Generating grounded draft…" : "Generate draft"}
              </Button>
            </form>
          </CardContent>
        </Card>
        <div className="min-w-0">
          {generation.isError ? <StatusPanel kind="error" title="Generation failed" description={generation.error instanceof Error ? generation.error.message : "The artifact could not be generated."} /> : null}
          {!artifact && !generation.isError ? <StatusPanel kind="empty" title="Your grounded draft will appear here" description="Every generated claim must retain an exact citation to the selected project source material." /> : null}
          {artifact ? (
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between gap-4"><div><Badge>Draft</Badge><CardTitle className="mt-3 text-2xl">{artifact.title}</CardTitle>{artifact.subtitle ? <p className="mt-2 text-sm text-muted-foreground">{artifact.subtitle}</p> : null}</div><Button variant="outline" disabled={exporting} onClick={() => void exportPdf()}><Download />{exporting ? "Exporting…" : "PDF"}</Button></div>
              </CardHeader>
              <CardContent className="space-y-6">
                {artifact.sections.map((section) => <section key={section.key}><h3 className="font-semibold text-primary">{section.heading}</h3>{section.statements.length ? <ul className="mt-2 space-y-2 text-sm leading-6">{section.statements.map((statement, index) => <li key={`${section.key}-${index}`}>• {statement.text} <span className="text-xs text-muted-foreground">{statement.citations.map((citation) => `[${citation.sourceId}]`).join(" ")}</span></li>)}</ul> : <p className="mt-2 text-sm text-muted-foreground">Known gap: not documented in the supplied evidence.</p>}</section>)}
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
    </>
  )
}
