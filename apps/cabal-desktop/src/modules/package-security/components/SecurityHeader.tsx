// Package security table header: bold title + muted ecosystem-scope description, a right-aligned
// mono severity/kind summary strip, and the rescan action (existing behavior, re-skinned).
import type { SecurityScan } from "@/api/securityEnvironment";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { RefreshButton } from "@/components/RefreshButton";
import { countsByKind, scopeDescription } from "@/modules/package-security/packageSecurityStatus";

export interface SecurityHeaderProps {
  scan: SecurityScan;
  isRescanning: boolean;
  onRescan: () => void;
}

export function SecurityHeader({ scan, isRescanning, onRescan }: SecurityHeaderProps) {
  const counts = countsByKind(scan.findings);
  const noticeCount = scan.notices.length;

  return (
    <header className="pkgsec-header">
      <div className="pkgsec-header__copy">
        <b>Package security check</b>
        <span>{scopeDescription(scan.ecosystems)}</span>
      </div>
      <div className="pkgsec-header__summary">
        <span data-tone={counts.vulnerable > 0 ? "danger" : "ok"}>
          {counts.vulnerable} vulnerable
        </span>
        <span data-tone={counts.outdated > 0 ? "warning" : "ok"}>{counts.outdated} outdated</span>
        <span data-tone={counts.deprecated > 0 ? "warning" : "ok"}>
          {counts.deprecated} deprecated
        </span>
        <span data-tone={noticeCount > 0 ? "info" : "neutral"}>
          {noticeCount > 0 ? `⚑ ${noticeCount} notice${noticeCount === 1 ? "" : "s"}` : "0 notices"}
        </span>
      </div>
      <CardRefreshFooter>
        <RefreshButton label="security scan" onRefresh={onRescan} isFetching={isRescanning} />
      </CardRefreshFooter>
    </header>
  );
}
