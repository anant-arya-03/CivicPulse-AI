import { FilePlus2, LayoutDashboard, ListChecks, Settings, type LucideIcon } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

/** Navigation for the authenticated app (sidebar on desktop, bottom bar on mobile). */
export const APP_NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/report", label: "Report Issue", icon: FilePlus2 },
  { href: "/complaints", label: "My Complaints", icon: ListChecks },
  { href: "/settings", label: "Settings", icon: Settings },
];

/** Links in the public (marketing) header. */
export const PUBLIC_NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/#how-it-works", label: "How It Works" },
  { href: "/#features", label: "Features" },
];

export function isActivePath(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
