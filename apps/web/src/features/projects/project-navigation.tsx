import { NavLink } from "react-router-dom"

import { cn } from "@/lib/utils"

type ProjectNavigationProps = {
  projectId: string
}

export function ProjectNavigation({ projectId }: ProjectNavigationProps) {
  const encodedId = encodeURIComponent(projectId)
  return (
    <nav className="mb-6 flex gap-1 overflow-x-auto border-b" aria-label="Project views">
      <ProjectTab to={`/projects/${encodedId}`} end>
        Overview
      </ProjectTab>
      <ProjectTab to={`/projects/${encodedId}/dna`}>Project DNA</ProjectTab>
    </nav>
  )
}

function ProjectTab({ to, end = false, children }: { to: string; end?: boolean; children: string }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          "relative px-4 py-3 text-sm font-semibold whitespace-nowrap outline-none after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:rounded-full focus-visible:ring-2 focus-visible:ring-primary/30",
          isActive
            ? "text-primary after:bg-primary"
            : "text-muted-foreground after:bg-transparent hover:text-foreground",
        )
      }
    >
      {children}
    </NavLink>
  )
}
