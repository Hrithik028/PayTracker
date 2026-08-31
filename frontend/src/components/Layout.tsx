import {
  Clock3,
  History,
  LayoutDashboard,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  PlusCircle,
  Settings,
  ShieldCheck,
  X,
} from "lucide-react";
import { type ReactNode, useState } from "react";
import { Link, useLocationPath } from "../services/navigation";

const links = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/new", label: "New pay period", icon: PlusCircle },
  { to: "/history", label: "History", icon: History },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Layout({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(
    () => window.localStorage.getItem("paytracker.sidebar.collapsed") === "true",
  );
  const path = useLocationPath();
  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    window.localStorage.setItem("paytracker.sidebar.collapsed", String(next));
  };
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-30 flex h-16 items-center justify-between bg-navy-900 px-4 text-white lg:hidden">
        <div className="flex items-center gap-2 font-bold"><Clock3 /> PayTracker</div>
        <button className="rounded-lg p-2" onClick={() => setOpen(!open)} aria-label="Toggle navigation">
          {open ? <X /> : <Menu />}
        </button>
      </header>
      <aside className={`${open ? "translate-x-0" : "-translate-x-full"} ${collapsed ? "lg:w-20 lg:px-3" : "lg:w-72 lg:px-5"} fixed inset-y-0 left-0 z-20 w-72 bg-navy-900 px-5 py-5 text-white transition-all duration-200 lg:translate-x-0`}>
        <div className={`mb-10 hidden lg:flex ${collapsed ? "flex-col items-center gap-3" : "items-center justify-between gap-3 px-2"}`}>
          <div className="flex items-center gap-3 text-xl font-bold">
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-blue-500"><Clock3 /></span>
            {!collapsed && "PayTracker"}
          </div>
          <button className="grid h-10 w-10 shrink-0 place-items-center rounded-lg text-blue-100 hover:bg-white/10 hover:text-white" onClick={toggleCollapsed} aria-label={collapsed ? "Expand sidebar" : "Minimize sidebar"} title={collapsed ? "Expand sidebar" : "Minimize sidebar"}>
            {collapsed ? <PanelLeftOpen size={20} /> : <PanelLeftClose size={20} />}
          </button>
        </div>
        <nav className="mt-16 space-y-1 lg:mt-0" aria-label="Main navigation">
          {links.map(({ to, label, icon: Icon, end }) => (
            <Link
              key={to}
              to={to}
              onClick={() => setOpen(false)}
              title={collapsed ? label : undefined}
              className={`flex min-h-12 items-center gap-3 rounded-xl px-4 font-medium ${collapsed ? "lg:justify-center lg:gap-0 lg:px-0" : ""} ${(end ? path === to : path.startsWith(to)) ? "bg-blue-600 text-white" : "text-blue-100 hover:bg-white/10"}`}
            >
              <Icon className="shrink-0" size={20} aria-hidden="true" /> <span className={collapsed ? "lg:sr-only" : ""}>{label}</span>
            </Link>
          ))}
        </nav>
        <div className={`${collapsed ? "lg:left-3 lg:right-3 lg:p-3" : ""} absolute bottom-6 left-5 right-5 rounded-xl bg-white/10 p-4 text-sm text-blue-100`} title={collapsed ? "Local and private" : undefined}>
          <div className={`flex items-center font-semibold text-white ${collapsed ? "lg:justify-center" : "mb-1 gap-2"}`}><ShieldCheck size={18} /> <span className={collapsed ? "lg:sr-only" : ""}>Local and private</span></div>
          <span className={collapsed ? "lg:sr-only" : ""}>Your documents stay on this computer.</span>
        </div>
      </aside>
      {open && <button aria-label="Close navigation" className="fixed inset-0 z-10 bg-slate-950/40 lg:hidden" onClick={() => setOpen(false)} />}
      <main className={`${collapsed ? "lg:ml-20" : "lg:ml-72"} p-4 transition-[margin] duration-200 sm:p-6 lg:p-8`}>
        <div className="mx-auto max-w-7xl">{children}</div>
      </main>
    </div>
  );
}
