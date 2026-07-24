import { createBrowserRouter, RouterProvider } from "react-router-dom"

import { AppShell } from "@/components/layout/app-shell"
import { DashboardPage } from "@/features/dashboard/dashboard-page"
import { ProjectDetailsPage } from "@/features/projects/project-details-page"
import { ProjectDnaPage } from "@/features/projects/project-dna-page"
import { SearchPage } from "@/features/search/search-page"
import { ExpertFinderPage } from "@/features/experts/expert-finder-page"
import { ArtifactGeneratorPage } from "@/features/artifacts/artifact-generator-page"

import { RouteErrorPage } from "./route-error-page"

const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    errorElement: <RouteErrorPage />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "search", element: <SearchPage /> },
      { path: "experts", element: <ExpertFinderPage /> },
      { path: "proposals", element: <ArtifactGeneratorPage kind="proposal" /> },
      { path: "one-pagers", element: <ArtifactGeneratorPage kind="project_one_pager" /> },
      { path: "projects/:projectId", element: <ProjectDetailsPage /> },
      { path: "projects/:projectId/dna", element: <ProjectDnaPage /> },
    ],
  },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}
