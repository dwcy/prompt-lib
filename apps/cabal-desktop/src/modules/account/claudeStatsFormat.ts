// Compact number/currency formatting for the Claude stats tile grid.
export function formatCompactNumber(value: number): string {
  return Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(
    value,
  );
}

export function formatMoney(value: number): string {
  return Intl.NumberFormat(undefined, { style: "currency", currency: "USD" }).format(value);
}

export function formatCount(value: number): string {
  return Intl.NumberFormat().format(value);
}
