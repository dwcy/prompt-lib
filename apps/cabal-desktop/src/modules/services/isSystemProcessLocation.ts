// Predicate backing the Services page's "Hide OS processes" preset filter — flags locations
// under the Windows OS directory (System32, SysWOW64, etc.), regardless of path separator or case.
const WINDOWS_OS_DIR_PATTERN = /^[a-z]:[\\/]+windows(?:[\\/]|$)/i;

export function isSystemProcessLocation(location: string | null): boolean {
  if (location === null) return false;
  return WINDOWS_OS_DIR_PATTERN.test(location);
}
