import { useRef, useState } from "react";
import { api, errorMessage, newIdempotencyKey } from "../api/client.js";
import { useFetch } from "../hooks/useFetch.js";
import { formatMoney } from "../lib/format.js";
import { Alert, Button, Card, inputBase } from "./ui.jsx";

const listProducts = () => api.get("/products", { params: { limit: 200 } });
const MAX_QUANTITY = 100; // keep in sync with the API (schemas/order.py)

let nextLineId = 1;
const newLine = () => ({ id: nextLineId++, productId: "", quantity: 1 });

export default function NewOrderForm({ onCreated, onCancel }) {
  const { data: products, error: productsError, loading } = useFetch(listProducts);
  const [lines, setLines] = useState([newLine()]);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // One idempotency key per order attempt. It is replaced whenever the order is edited, so a
  // retry of the *same* order (e.g. after a network error) can never create a duplicate,
  // while a changed order is always a new request.
  const keyRef = useRef(newIdempotencyKey());

  const priceOf = (productId) => products?.find((p) => p.id === productId);
  const chosen = lines.filter((line) => line.productId);
  const total = chosen.reduce(
    (sum, line) => sum + Number(priceOf(line.productId)?.price ?? 0) * line.quantity,
    0,
  );
  const currency = priceOf(chosen[0]?.productId)?.currency ?? "USD";

  function edit(updater) {
    keyRef.current = newIdempotencyKey();
    setLines(updater);
  }

  const updateLine = (id, patch) =>
    edit((current) => current.map((line) => (line.id === id ? { ...line, ...patch } : line)));
  const removeLine = (id) => edit((current) => current.filter((line) => line.id !== id));

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    if (chosen.length === 0) {
      setError("Add at least one product.");
      return;
    }
    setSubmitting(true);
    try {
      const { data } = await api.post(
        "/orders",
        { items: chosen.map((l) => ({ product_id: l.productId, quantity: l.quantity })) },
        { headers: { "Idempotency-Key": keyRef.current } },
      );
      onCreated(data);
    } catch (err) {
      setError(errorMessage(err));
      setSubmitting(false);
    }
  }

  return (
    <Card className="mb-6 p-5">
      <h2 className="mb-4 text-base font-medium">New order</h2>

      {loading && <p className="text-sm text-slate-500">Loading products…</p>}
      {productsError && <Alert>Could not load products: {productsError}</Alert>}

      {products && (
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <Alert>{error}</Alert>}

          <div className="space-y-3">
            {lines.map((line, index) => (
              <div key={line.id} className="flex flex-wrap items-center gap-3">
                <select
                  aria-label={`Product ${index + 1}`}
                  value={line.productId}
                  onChange={(e) => updateLine(line.id, { productId: e.target.value })}
                  className={`${inputBase} min-w-0 flex-1 basis-64`}
                >
                  <option value="">Select a product…</option>
                  {products.map((p) => (
                    <option
                      key={p.id}
                      value={p.id}
                      // A product may appear once per order; hide it from the other rows.
                      disabled={p.id !== line.productId && lines.some((l) => l.productId === p.id)}
                    >
                      {p.name} — {formatMoney(p.price, p.currency)}
                    </option>
                  ))}
                </select>
                <input
                  aria-label={`Quantity ${index + 1}`}
                  type="number"
                  min={1}
                  max={MAX_QUANTITY}
                  step={1}
                  value={line.quantity}
                  onChange={(e) =>
                    updateLine(line.id, {
                      quantity: Math.min(MAX_QUANTITY, Math.max(1, Math.floor(Number(e.target.value)) || 1)),
                    })
                  }
                  className={`${inputBase} w-24`}
                />
                <Button
                  variant="secondary"
                  onClick={() => removeLine(line.id)}
                  disabled={lines.length === 1}
                  aria-label={`Remove line ${index + 1}`}
                >
                  Remove
                </Button>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <Button
              variant="secondary"
              onClick={() => edit((current) => [...current, newLine()])}
              disabled={lines.length >= products.length}
            >
              Add product
            </Button>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Estimated total:{" "}
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {formatMoney(total, currency)}
              </span>
              <span className="ml-1 text-xs">(final price is set by the server)</span>
            </p>
          </div>

          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={onCancel} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Placing order…" : "Place order"}
            </Button>
          </div>
        </form>
      )}
    </Card>
  );
}
