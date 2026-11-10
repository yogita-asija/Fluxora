import { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage } from "../api/client.js";
import { Alert, Button, Card, PageHeader, StatusBadge } from "../components/ui.jsx";
import { useFetch } from "../hooks/useFetch.js";
import { formatDate, formatMoney } from "../lib/format.js";

export default function OrderDetail() {
  const { orderId } = useParams();
  const request = useCallback(() => api.get(`/orders/${orderId}`), [orderId]);
  const { data: order, error, loading, reload } = useFetch(request);

  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState(null);

  async function handleCancel() {
    if (!window.confirm("Cancel this order? This cannot be undone.")) return;
    setCancelError(null);
    setCancelling(true);
    try {
      await api.post(`/orders/${orderId}/cancel`);
      await reload();
    } catch (err) {
      setCancelError(errorMessage(err));
    } finally {
      setCancelling(false);
    }
  }

  const back = (
    <Link to="/orders" className="text-sm text-indigo-600 hover:underline dark:text-indigo-400">
      ← All orders
    </Link>
  );

  if (loading && !order) return <p className="text-sm text-slate-500">Loading order…</p>;

  if (error) {
    return (
      <>
        <div className="mb-4">{back}</div>
        <Alert>{error}</Alert>
      </>
    );
  }

  return (
    <>
      <div className="mb-4">{back}</div>
      <PageHeader
        title={`Order ${order.id.slice(0, 8)}`}
        description={`Placed ${formatDate(order.created_at)}`}
      >
        <div className="flex items-center gap-3">
          <StatusBadge status={order.status} />
          {order.status === "pending" && (
            <Button variant="danger" onClick={handleCancel} disabled={cancelling}>
              {cancelling ? "Cancelling…" : "Cancel order"}
            </Button>
          )}
        </div>
      </PageHeader>

      {cancelError && (
        <div className="mb-4">
          <Alert>{cancelError}</Alert>
        </div>
      )}

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
              <tr>
                <th className="px-5 py-3 font-medium">Product</th>
                <th className="px-5 py-3 text-right font-medium">Unit price</th>
                <th className="px-5 py-3 text-right font-medium">Qty</th>
                <th className="px-5 py-3 text-right font-medium">Line total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {order.items.map((item) => (
                <tr key={item.product_id}>
                  <td className="px-5 py-3">
                    <p className="font-medium">{item.product_name}</p>
                    <p className="font-mono text-xs text-slate-500 dark:text-slate-400">
                      {item.product_sku}
                    </p>
                  </td>
                  <td className="px-5 py-3 text-right tabular-nums">
                    {formatMoney(item.unit_price, order.currency)}
                  </td>
                  <td className="px-5 py-3 text-right tabular-nums">{item.quantity}</td>
                  <td className="px-5 py-3 text-right tabular-nums">
                    {formatMoney(item.line_total, order.currency)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="border-t border-slate-200 dark:border-slate-800">
              <tr>
                <td colSpan={3} className="px-5 py-3 text-right font-medium">
                  Total
                </td>
                <td className="px-5 py-3 text-right text-base font-semibold tabular-nums">
                  {formatMoney(order.total_amount, order.currency)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </Card>
    </>
  );
}
