import { useCallback, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import NewOrderForm from "../components/NewOrderForm.jsx";
import { Alert, Button, Card, PageHeader, StatusBadge, inputBase } from "../components/ui.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useFetch } from "../hooks/useFetch.js";
import { formatDate, formatMoney, shortId } from "../lib/format.js";

const PAGE_SIZE = 10;
const STATUSES = ["pending", "reserved", "paid", "fulfilled", "cancelled", "failed"];

export default function Orders() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [creating, setCreating] = useState(false);

  const request = useCallback(
    () => api.get("/orders", { params: { status: status || undefined, limit: PAGE_SIZE, offset } }),
    [status, offset],
  );
  const { data, error, loading, reload } = useFetch(request);

  const orders = data?.items ?? [];
  const total = data?.total ?? 0;
  const isAdmin = user.role === "admin";

  return (
    <>
      <PageHeader
        title="Orders"
        description={
          isAdmin ? "All customers' orders (admin view)." : "Your orders, from placement to delivery."
        }
      >
        {!creating && <Button onClick={() => setCreating(true)}>New order</Button>}
      </PageHeader>

      {creating && (
        <NewOrderForm
          onCreated={(order) => navigate(`/orders/${order.id}`)}
          onCancel={() => setCreating(false)}
        />
      )}

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label htmlFor="status-filter" className="text-sm text-slate-500 dark:text-slate-400">
          Status
        </label>
        <select
          id="status-filter"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setOffset(0);
          }}
          className={`${inputBase} w-40`}
        >
          <option value="">All</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </option>
          ))}
        </select>
        <Button variant="secondary" onClick={reload}>
          Refresh
        </Button>
      </div>

      {error && <Alert>Could not load orders: {error}</Alert>}

      {!error && (
        <Card className="overflow-hidden">
          {loading && !data && <p className="p-6 text-sm text-slate-500">Loading orders…</p>}

          {data && orders.length === 0 && (
            <div className="p-6 text-sm text-slate-500 dark:text-slate-400">
              {status ? "No orders with this status." : "No orders yet. Place your first one above."}
            </div>
          )}

          {orders.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
                  <tr>
                    <th className="px-5 py-3 font-medium">Order</th>
                    <th className="px-5 py-3 font-medium">Placed</th>
                    <th className="px-5 py-3 text-right font-medium">Items</th>
                    <th className="px-5 py-3 text-right font-medium">Total</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {orders.map((order) => (
                    <tr key={order.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                      <td className="px-5 py-3">
                        <Link
                          to={`/orders/${order.id}`}
                          className="font-mono text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-400"
                        >
                          {shortId(order.id)}
                        </Link>
                      </td>
                      <td className="px-5 py-3 text-slate-600 dark:text-slate-300">
                        {formatDate(order.created_at)}
                      </td>
                      <td className="px-5 py-3 text-right tabular-nums">
                        {order.items.reduce((sum, item) => sum + item.quantity, 0)}
                      </td>
                      <td className="px-5 py-3 text-right tabular-nums">
                        {formatMoney(order.total_amount, order.currency)}
                      </td>
                      <td className="px-5 py-3">
                        <StatusBadge status={order.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {total > 0 && (
            <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3 text-sm dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400">
                {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button
                  variant="secondary"
                  disabled={offset + PAGE_SIZE >= total}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}
    </>
  );
}
