import { Card } from "./ui.jsx";

// Centered card shared by the login and register pages.
export default function AuthLayout({ title, footer, children }) {
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
            O
          </div>
          <span className="text-xl font-semibold tracking-tight">OrderFlow</span>
        </div>
        <Card className="p-6">
          <h1 className="mb-5 text-lg font-semibold">{title}</h1>
          {children}
        </Card>
        <p className="mt-5 text-center text-sm text-slate-500 dark:text-slate-400">{footer}</p>
      </div>
    </div>
  );
}
