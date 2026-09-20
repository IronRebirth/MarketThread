export interface NavigationItem {
  label: string;
  href: string;
  description: string;
}

export const primaryNavigation: NavigationItem[] = [
  { label: "Market Intelligence", href: "/", description: "Global market signals and developments." },
  { label: "News", href: "/news", description: "News and information affecting markets." },
  { label: "Events", href: "/events", description: "Important global events and market catalysts." },
  { label: "Companies", href: "/companies", description: "Company-level research and impact analysis." },
  { label: "Market Impact", href: "/market-impacts", description: "Economic transmission paths from events to companies." },
  { label: "Recommendations", href: "/recommendations", description: "Research recommendations derived from persisted signals." },
  { label: "Watchlists", href: "/watchlists", description: "Track companies, sectors, and market themes." },
  { label: "Notifications", href: "/notifications", description: "Review persisted watchlist alert notifications." },
  { label: "Portfolio", href: "/portfolio", description: "Risk-aware portfolio intelligence and allocation." },
  { label: "Backtesting", href: "/backtests", description: "Evaluate signals across historical market outcomes." },
  { label: "Research Assistant", href: "/research", description: "Ask questions and explore market evidence." },
];
