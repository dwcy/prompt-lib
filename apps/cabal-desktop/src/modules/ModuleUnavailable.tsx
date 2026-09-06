// Honest stub rendered for every module that has not shipped yet, naming its delivery phase.
import { EmptyState } from "@/components/EmptyState";

export interface ModuleUnavailableProps {
  title: string;
  phase: number;
}

export function ModuleUnavailable({ title, phase }: ModuleUnavailableProps) {
  return (
    <EmptyState
      title={`${title} is not available yet`}
      body={`This module arrives in phase ${phase} of the web UI overhaul.`}
    />
  );
}
