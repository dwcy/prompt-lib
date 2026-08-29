// Client-side pre-check mirroring the backend's post-normalisation escape rule for new-service
// destinations (FR-011a, research.md R10). The authoritative check still happens server-side in
// codegen.new_service — this only gives the user an early, honest answer before submitting.
export interface ProjectRelativeDestinationResult {
  normalized: string | null;
  error: string | null;
}

const DRIVE_LETTER_PATTERN = /^[A-Za-z]:[\\/]/;

export function resolveProjectRelativeDestination(raw: string): ProjectRelativeDestinationResult {
  const trimmed = raw.trim();
  if (trimmed.length === 0) {
    return { normalized: null, error: "Enter a destination inside the selected project." };
  }
  if (trimmed.startsWith("/") || trimmed.startsWith("\\") || DRIVE_LETTER_PATTERN.test(trimmed)) {
    return {
      normalized: null,
      error: "Destination must be a path inside the project, not an absolute path.",
    };
  }

  const segments = trimmed.split(/[\\/]+/).filter((segment) => segment.length > 0);
  const resolved: string[] = [];
  for (const segment of segments) {
    if (segment === ".") continue;
    if (segment === "..") {
      if (resolved.length === 0) {
        return { normalized: null, error: "Destination escapes the selected project's directory." };
      }
      resolved.pop();
      continue;
    }
    resolved.push(segment);
  }

  if (resolved.length === 0) {
    return { normalized: null, error: "Destination must name a folder inside the project." };
  }

  return { normalized: resolved.join("/"), error: null };
}
