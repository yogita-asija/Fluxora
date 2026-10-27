import { api } from "../api/client.js";
import { Badge, Card, PageHeader } from "../components/ui.jsx";
import { useFetch } from "../hooks/useFetch.js";

const listProducts = () => api.get("/products");

function formatPrice(price, currency) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(Number(price));
}

export default function Products() {
  const { data: products, error, loading, reload } = useFetch(listProducts);

  return (
    <>
      <PageHeader title="Products" description="Catalogue served by GET /api/v1/products.">
        <button
          type="button"
          onClick={reload}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
        >
          Refresh
        </button>
      </PageHeader>

      <Card className="overflow-hidden">
        {loading && <p className="p-6 text-sm text-slate-500">Loading products…</p>}

        {error && (
          <div className="p-6 text-sm text-rose-600 dark:text-rose-400">
            Could not load products: {error}
          </div>
        )}

        {!loading && !error && products.length === 0 && (
          <div className="p-6 text-sm text-slate-500 dark:text-slate-400">
            No products yet. Run the seed command (see README) to load demo data.
          </div>
        )}

        {!loading && !error && products.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
                <tr>
                  <th className="px-5 py-3 font-medium">SKU</th>
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 text-right font-medium">Price</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {products.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                    <td className="px-5 py-3 font-mono text-xs text-slate-500 dark:text-slate-400">
                      {p.sku}
                    </td>
                    <td className="px-5 py-3 font-medium">{p.name}</td>
                    <td className="px-5 py-3 text-right tabular-nums">
                      {formatPrice(p.price, p.currency)}
                    </td>
                    <td className="px-5 py-3">
                      <Badge tone={p.is_active ? "green" : "slate"}>
                        {p.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
