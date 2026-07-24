import { Brain, FileOutput, LayoutDashboard, Search, Sparkles } from "lucide-react"
import { NavLink } from "react-router-dom"

import { Brand } from "@/components/layout/brand"
import { cn } from "@/lib/utils"

const navigation = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/search", label: "Search knowledge", icon: Search, end: false },
  { to: "/experts", label: "Expert Finder", icon: Brain, end: false },
  { to: "/proposals", label: "Proposal Generator", icon: FileOutput, end: false },
  { to: "/one-pagers", label: "Project One-Pager", icon: Sparkles, end: false },
]

export function Sidebar() {
  return (
    <aside className="surface-grid fixed inset-y-0 left-0 z-30 hidden w-64 flex-col overflow-hidden bg-[#0d1b36] text-slate-300 lg:flex">
      <div className="px-6 pt-7 pb-8">
        <Brand inverse />
      </div>
      <nav className="flex-1 px-3" aria-label="Primary navigation">
        <p className="px-3 pb-2 text-[10px] font-bold tracking-[0.16em] text-slate-500 uppercase">
          Workspace
        </p>
        <div className="space-y-1">
          {navigation.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-[#61d4cb]/50",
                  isActive
                    ? "bg-white/10 text-white shadow-inner shadow-white/5"
                    : "hover:bg-white/5 hover:text-white",
                )
              }
            >
              <Icon className="size-[18px]" aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </div>
      </nav>
      <div className="m-4 rounded-2xl border border-white/8 bg-white/5 p-4">
        <div className="mb-3 grid size-8 place-items-center rounded-lg bg-[#61d4cb]/10 text-[#61d4cb]">
          <Sparkles className="size-4" aria-hidden="true" />
        </div>
        <p className="text-xs font-semibold text-white">Organizational memory</p>
        <p className="mt-1 text-[11px] leading-5 text-slate-400">
          Grounded intelligence from approved Blend project knowledge.
        </p>
      </div>
    </aside>
  )
}
