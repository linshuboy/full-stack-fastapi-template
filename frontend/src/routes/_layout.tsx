import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"

// import { Footer } from "@/components/Common/Footer"
import { SidebarAppearance } from "@/components/Common/Appearance"
import AppSidebar from "@/components/Sidebar/AppSidebar"
import { User } from "@/components/Sidebar/User"
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { isLoggedIn } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout")({
  component: Layout,
  beforeLoad: async () => {
    if (!isLoggedIn()) {
      throw redirect({
        to: "/login",
      })
    }
  },
})

function Layout() {
  const { user: currentUser } = useAuth()
  
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center justify-end border-b px-4">
          <div className="flex items-center gap-4">
            <SidebarAppearance />
            <User user={currentUser} />
          </div>
        </header>
        <main className="flex-1 p-6 md:p-8">
          <div className="mx-auto max-w-7xl">
            <Outlet />
          </div>
        </main>
        {/* <Footer /> */}
      </SidebarInset>
    </SidebarProvider>
  )
}

export default Layout
