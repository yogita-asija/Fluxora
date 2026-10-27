import { useCallback, useEffect, useState } from "react";
import { health } from "../api/client.js";
import { Badge, Card, PageHeader } from "../components/ui.jsx";

const REFRESH_MS = 15000;

// Readiness returns a JSON body even on 503, so read it from the error response too.
async function probe(path) {
  try {
    const response = await health.get(path);
    return { reachable: true, ok: true, body: response.data };
  } catch (err) {
    if (err.response) return { reachable: true, ok: false, body: err.response.data };
    return { reachable: false, ok: false, body: null };
  }
}

function StatusBadge({ ok, reachable = true }) {
  if (!reachable) return <Badge tone="red">Unreachable</Badge>;
  return <Badge tone={ok ? "green" : "red"}>{ok ? "Healthy" : "Unavailable"}</Badge>;
}

function Row({ label, detail, badge }) {
  return (
    <div className="flex items-center justify-between gap-4 px-5 py-4">
      <div>
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-slate-500 dark:text-slate-400">{detail}</p>
      </div>
      {badge}
    </div>
  );
}

export default function SystemHealth() {
  const [live, setLive] = useState(null);
  const [ready, setReady] = useState(null);
  const [checkedAt, setCheckedAt] = useState(null);

  const refresh = useCallback(async () => {
    const [liveResult, readyResult] = await Promise.all([probe("/live"), probe("/ready")]);
    setLive(liveResult);
    setReady(readyResult);
    setCheckedAt(new Date());
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, REFRESH_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  const dbStatus = ready?.body?.checks?.database;

  return (
    <>
      <PageHeader
        title="System Health"
        description={
          checkedAt
            ? `Last checked ${checkedAt.toLocaleTimeString()} · refreshes every ${REFRESH_MS / 1000}s`
            : "Checking…"
        }
      >
        <button
          type="button"
          onClick={refresh}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
        >
          Check now
        </button>
      </PageHeader>

      <Card className="divide-y divide-slate-100 dark:divide-slate-800">
        <Row
          label="API liveness"
          detail="GET /health/live: the process is running"
          badge={live ? <StatusBadge ok={live.ok} reachable={live.reachable} /> : <Badge>Checking</Badge>}
        />
        <Row
          label="API readiness"
          detail="GET /health/ready: dependencies are reachable"
          badge={ready ? <StatusBadge ok={ready.ok} reachable={ready.reachable} /> : <Badge>Checking</Badge>}
        />
        <Row
          label="PostgreSQL"
          detail="Reported by the readiness check"
          badge={
            dbStatus ? <StatusBadge ok={dbStatus === "ok"} /> : <Badge>{ready ? "Unknown" : "Checking"}</Badge>
          }
        />
        {["Redis", "RabbitMQ", "Kafka"].map((name) => (
          <Row
            key={name}
            label={name}
            detail="Running in Docker Compose; not used by the API yet"
            badge={<Badge>Not wired</Badge>}
          />
        ))}
      </Card>
    </>
  );
}
