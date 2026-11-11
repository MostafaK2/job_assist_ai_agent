"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import UserMenu from "@/components/UserMenu";

const NAV = [
  { href: "/chat", label: "Chat" },
  { href: "/jobs", label: "Jobs" },
];

export default function TopNav({ user }) {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-10 border-b border-line bg-surface">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="whitespace-nowrap text-lg font-bold tracking-tight">
          Job Assist
        </Link>

        <div className="flex items-center gap-2 sm:gap-4">
          <nav aria-label="Main" className="flex items-center gap-1">
            {NAV.map(({ href, label }) => {
              const active = pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={`rounded-md px-3 py-1.5 text-sm ${
                    active ? "bg-ink font-medium text-white" : "text-muted hover:bg-paper hover:text-ink"
                  }`}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
          <span aria-hidden="true" className="h-6 w-px bg-line" />
          <UserMenu user={user} />
        </div>
      </div>
    </header>
  );
}