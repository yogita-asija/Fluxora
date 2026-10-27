import { PageHeader, Placeholder, StatCard } from "../components/ui.jsx";

export default function Orders() {
  return (
    <>
      <PageHeader title="Orders" description="Track orders from placement to fulfilment." />
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <StatCard label="Open orders" value="—" />
        <StatCard label="Awaiting payment" value="—" />
        <StatCard label="Fulfilled today" value="—" />
      </div>
      <Placeholder
        title="Order list"
        items={[
          "Searchable, filterable order table with status badges",
          "Order detail view: items, payments, and reservation state",
          "Place an order (idempotent, event-driven workflow)",
        ]}
      />
    </>
  );
}
