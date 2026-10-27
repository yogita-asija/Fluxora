import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import Icon from "./icons.jsx";
import { useTheme } from "../hooks/useTheme.js";

const NAV_ITEMS = [
  { to: "/orders", label: "Orders", icon: "orders" },
  { to: "/products", label: "Products", icon: "products" },
  { to: "/inventory", label: "Inventory", icon: "inventory" },
  { to: "/analytics", label: "Analytics", icon: "analytics" },
  { to: "/system-health", label: "System Health", icon: "health" },
];

function SidebarContent({ onNavigate }) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center gap-2 px-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
          O
        </div>
        <span className="text-lg font-semibold tracking-tight">OrderFlow</span>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4" aria-label="Main">
        {NAV_ITEMS.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onNavigate}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800/60 dark:hover:text-slate-100"
              }`
            }
          >
            <Icon name={icon} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-6 py-4 text-xs text-slate-400 dark:text-slate-500">v0.1.0 · foundation</div>
    </div>
  );
}

export default function Layout() {
  const { dark, toggle } = useTheme();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="min-h-screen">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-slate-200 bg-white lg:block dark:border-slate-800 dark:bg-slate-900">
        <SidebarContent />
      </aside>

      {/* Mobile drawer */}
      {menuOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setMenuOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 bg-white dark:bg-slate-900">
            <SidebarContent onNavigate={() => setMenuOpen(false)} />
          </aside>
        </div>
      )}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-white/80 px-4 backdrop-blur sm:px-8 dark:border-slate-800 dark:bg-slate-900/80">
          <button
            type="button"
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden dark:text-slate-300 dark:hover:bg-slate-800"
            onClick={() => setMenuOpen(true)}
            aria-label="Open navigation"
          >
            <Icon name="menu" />
          </button>
          <div className="hidden lg:block" />
          <button
            type="button"
            onClick={toggle}
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
            aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
          >
            <Icon name={dark ? "sun" : "moon"} />
          </button>
        </header>

        <main className="mx-auto max-w-6xl px-4 py-8 sm:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
