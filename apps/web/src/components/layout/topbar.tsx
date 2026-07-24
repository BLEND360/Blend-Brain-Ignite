import { Search } from "lucide-react"
import { type SyntheticEvent, useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"

import { Brand } from "@/components/layout/brand"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export function Topbar() {
  const navigate = useNavigate()
  const location = useLocation()
  const [query, setQuery] = useState("")

  function submit(event: SyntheticEvent<HTMLFormElement, SubmitEvent>) {
    event.preventDefault()
    const normalized = query.trim()
    if (normalized) {
      void navigate(`/search?q=${encodeURIComponent(normalized)}`)
      setQuery("")
    }
  }

  return (
    <header className="sticky top-0 z-20 flex h-18 items-center border-b border-border/80 bg-background/85 px-4 backdrop-blur-xl sm:px-6 lg:ml-64 lg:px-8">
      <div className="flex w-full items-center gap-4">
        <div className="lg:hidden">
          <Brand compact />
        </div>
        <form
          className="relative hidden w-full max-w-xl sm:block"
          role="search"
          onSubmit={submit}
        >
          <Search
            className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search projects, outcomes, technologies…"
            aria-label="Search organizational knowledge"
            className="h-10 bg-white/80 pr-16 pl-10"
          />
          <kbd className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 rounded border bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
            ↵
          </kbd>
        </form>
        <div className="ml-auto flex items-center gap-3">
          {location.pathname !== "/search" ? (
            <Button
              className="sm:hidden"
              size="icon"
              variant="ghost"
              aria-label="Open search"
              onClick={() => void navigate("/search")}
            >
              <Search />
            </Button>
          ) : null}
          <div className="hidden text-right md:block">
            <p className="text-xs font-semibold">Blend workspace</p>
            <p className="text-[11px] text-muted-foreground">Internal knowledge</p>
          </div>
          <div
            className="grid size-9 place-items-center rounded-full border border-primary/10 bg-primary/8 text-xs font-bold text-primary"
            aria-hidden="true"
          >
            B
          </div>
        </div>
      </div>
    </header>
  )
}
