import { PageHeader, Placeholder, StatCard } from "../components/ui.jsx";

export default function Inventory() {
  return (
    <>
      <PageHeader title="Inventory" description="Stock levels and reservations." />
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <StatCard label="SKUs tracked" value="—" />
        <StatCard label="Low stock" value="—" />
        <StatCard label="Units reserved" value="—" />
      </div>
      <Placeholder
        title="Stock levels"
        items={[
          "On-hand, reserved, and available quantities per product",
          "Low-stock alerts based on reorder levels",
          "Live view of active inventory reservations and expiries",
        ]}
      />
    </>
  );
}
