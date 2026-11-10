export function formatMoney(amount, currency = "USD") {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(Number(amount));
}

export function formatDate(iso) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

// Order ids are UUIDs: the first block is enough to recognise one at a glance.
export function shortId(id) {
  return id.slice(0, 8);
}
