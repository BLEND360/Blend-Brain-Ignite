import { isRouteErrorResponse, Link, useRouteError } from "react-router-dom"

import { Button } from "@/components/ui/button"

export function RouteErrorPage() {
  const error = useRouteError()
  const notFound = isRouteErrorResponse(error) && error.status === 404

  return (
    <main className="grid min-h-screen place-items-center bg-background px-6">
      <div className="max-w-lg text-center">
        <p className="text-sm font-bold tracking-[0.18em] text-primary uppercase">
          {notFound ? "404" : "Application error"}
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">
          {notFound ? "This knowledge view does not exist." : "We could not open this view."}
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          {notFound
            ? "The link may be outdated or the resource may no longer be available."
            : "Return to the dashboard and try again. If the issue continues, contact the platform team."}
        </p>
        <Button asChild className="mt-6">
          <Link to="/">Return to dashboard</Link>
        </Button>
      </div>
    </main>
  )
}
