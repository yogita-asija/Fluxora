// Small shared presentational pieces.

export function PageHeader({ title, description, children }) {
  return (
    <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && (
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{description}</p>
        )}
      </div>
      {children}
    </div>
  );
}

export function Card({ className = "", children }) {
  return (
    <div
      className={`rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900 ${className}`}
    >
      {children}
    </div>
  );
}

export function StatCard({ label, value, hint }) {
  return (
    <Card className="p-5">
      <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">{hint}</p>}
    </Card>
  );
}

export function Placeholder({ title, items }) {
  return (
    <Card className="border-dashed p-8">
      <h2 className="text-base font-medium">{title}</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        Placeholder page. Planned for a later phase:
      </p>
      <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-300">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </Card>
  );
}

const BADGE_TONES = {
  green: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300",
  red: "bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300",
  amber: "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300",
  blue: "bg-sky-50 text-sky-700 dark:bg-sky-500/10 dark:text-sky-300",
  slate: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
};

export function Badge({ tone = "slate", children }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${BADGE_TONES[tone]}`}
    >
      {children}
    </span>
  );
}

const STATUS_TONES = {
  pending: "amber",
  reserved: "blue",
  paid: "blue",
  fulfilled: "green",
  cancelled: "slate",
  failed: "red",
};

export function StatusBadge({ status }) {
  return (
    <Badge tone={STATUS_TONES[status] ?? "slate"}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </Badge>
  );
}

const BUTTON_VARIANTS = {
  primary:
    "bg-indigo-600 text-white hover:bg-indigo-500 focus-visible:outline-indigo-600 disabled:bg-indigo-400",
  secondary:
    "border border-slate-300 text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800",
  danger:
    "border border-rose-300 text-rose-700 hover:bg-rose-50 dark:border-rose-500/40 dark:text-rose-300 dark:hover:bg-rose-500/10",
};

export function Button({ variant = "primary", className = "", type = "button", ...props }) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center rounded-lg px-3.5 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60 ${BUTTON_VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}

// Look of a text input / select without any width, so callers can size it themselves.
export const inputBase =
  "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950 dark:placeholder:text-slate-500";

// Full-width variant used in forms.
export const inputClass = `block w-full ${inputBase}`;

export function Field({ label, htmlFor, hint, children }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium">
        {label}
      </label>
      {children}
      {hint && <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{hint}</p>}
    </div>
  );
}

const ALERT_TONES = {
  error:
    "border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200",
  info: "border-sky-200 bg-sky-50 text-sky-800 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-200",
};

export function Alert({ tone = "error", children }) {
  return (
    <div role="alert" className={`rounded-lg border px-3.5 py-2.5 text-sm ${ALERT_TONES[tone]}`}>
      {children}
    </div>
  );
}
