// Shared byte-size and timestamp formatting for the Agent Setup tree and file preview.

export function formatBytes(bytes: number | null): string {
  if (bytes === null) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatModified(isoTimestamp: string | null): string {
  if (isoTimestamp === null) return "";
  const parsed = new Date(isoTimestamp);
  return Number.isNaN(parsed.getTime()) ? isoTimestamp : parsed.toLocaleString();
}
