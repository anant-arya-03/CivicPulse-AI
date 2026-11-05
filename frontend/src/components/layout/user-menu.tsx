"use client";

import { ChevronsUpDown, LogOut, Settings } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useLogout } from "@/features/authentication/hooks";
import { cn } from "@/lib/utils";
import type { User } from "@/types/api";

export function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : "";
  return (first + last).toUpperCase() || "?";
}

interface UserMenuProps {
  user: User;
  /** "sidebar" shows name + email on the navy sidebar; "compact" shows just the avatar. */
  variant?: "sidebar" | "compact";
}

export function UserMenu({ user, variant = "compact" }: UserMenuProps) {
  const router = useRouter();
  const logout = useLogout();

  function handleLogout() {
    logout.mutate(undefined, {
      onSuccess: () => router.replace("/login"),
      onError: () => toast.error("Couldn't log out. Please try again."),
    });
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          "flex items-center gap-3 rounded-lg text-left outline-none focus-visible:ring-2 focus-visible:ring-ring",
          variant === "sidebar"
            ? "w-full p-2 text-sidebar-foreground hover:bg-sidebar-accent"
            : "p-1 hover:bg-muted",
        )}
      >
        <span className="sr-only">Account menu: </span>
        <Avatar className="size-9" aria-hidden>
          <AvatarFallback className="bg-teal-soft text-sm font-semibold text-teal-strong">
            {getInitials(user.name)}
          </AvatarFallback>
        </Avatar>
        {variant === "sidebar" && (
          <>
            <span className="grid min-w-0 flex-1">
              <span className="truncate text-sm font-medium text-white">{user.name}</span>
              <span className="truncate text-xs">{user.email}</span>
            </span>
            <ChevronsUpDown className="size-4 shrink-0" aria-hidden />
          </>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" side={variant === "sidebar" ? "top" : "bottom"} className="w-56">
        <DropdownMenuLabel className="grid">
          <span className="truncate font-medium">{user.name}</span>
          <span className="truncate text-xs font-normal text-muted-foreground">{user.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/settings">
            <Settings aria-hidden /> Settings
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={handleLogout} disabled={logout.isPending}>
          <LogOut aria-hidden /> {logout.isPending ? "Logging out…" : "Log out"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
