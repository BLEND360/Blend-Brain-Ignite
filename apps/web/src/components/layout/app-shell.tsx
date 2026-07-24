import { Outlet } from "react-router-dom"

import { Sidebar } from "@/components/layout/sidebar"
import { Topbar } from "@/components/layout/topbar"

export function AppShell() {
  return (
    <div className="min-h-screen">
      <Sidebar />
      <Topbar />
      <main id="main-content" className="px-4 py-6 sm:px-6 sm:py-8 lg:ml-64 lg:px-8 xl:px-10">
        <div className="mx-auto w-full max-w-[1440px]">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
