import { queryOptions } from "@tanstack/react-query"

import type { KnowledgeRepository } from "./knowledge-repository"

export const dashboardQuery = (repository: KnowledgeRepository) =>
  queryOptions({
    queryKey: ["dashboard"],
    queryFn: ({ signal }) => repository.getDashboard({ signal }),
    staleTime: 60_000,
  })

export const projectCatalogQuery = (repository: KnowledgeRepository) =>
  queryOptions({
    queryKey: ["project-catalog"],
    queryFn: ({ signal }) => repository.getProjects("", { signal }),
    staleTime: 5 * 60_000,
  })

export const searchQuery = (repository: KnowledgeRepository, question: string) =>
  queryOptions({
    queryKey: ["search", question],
    queryFn: ({ signal }) => repository.search(question, { signal }),
    enabled: question.length > 0,
    staleTime: 5 * 60_000,
  })

export const projectQuery = (repository: KnowledgeRepository, projectId: string) =>
  queryOptions({
    queryKey: ["projects", projectId],
    queryFn: ({ signal }) => repository.getProject(projectId, { signal }),
    staleTime: 5 * 60_000,
  })

export const projectDnaQuery = (repository: KnowledgeRepository, projectId: string) =>
  queryOptions({
    queryKey: ["projects", projectId, "dna"],
    queryFn: ({ signal }) => repository.getProjectDna(projectId, { signal }),
    staleTime: 5 * 60_000,
  })

export const similarProjectsQuery = (repository: KnowledgeRepository, projectId: string) =>
  queryOptions({
    queryKey: ["projects", projectId, "similar"],
    queryFn: ({ signal }) => repository.getSimilarProjects(projectId, { signal }),
    staleTime: 5 * 60_000,
  })

export const expertSearchQuery = (repository: KnowledgeRepository, query: string) =>
  queryOptions({
    queryKey: ["experts", query],
    queryFn: ({ signal }) => repository.findExperts(query, { signal }),
    enabled: query.length > 0,
    staleTime: 5 * 60_000,
  })
