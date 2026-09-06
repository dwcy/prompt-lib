// Bottom-right footer strip a card renders to host its RefreshButton; `margin-top: auto` pins it
// to the card's bottom edge in flex-column cards and keeps it clear of the card's content.
import type { ReactNode } from "react";

export interface CardRefreshFooterProps {
  children: ReactNode;
}

export function CardRefreshFooter({ children }: CardRefreshFooterProps) {
  return <footer className="card-refresh-footer">{children}</footer>;
}
