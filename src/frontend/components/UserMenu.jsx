"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import Avatar from "@/components/Avatar";

const ITEMS = [
  { href: "/account", label: "Your account" },
  { href: "/settings", label: "Settings" },
  { href: "/help", label: "Get help" },
];

/** Profile button on the far right of the header. Click it to open the account menu. */
export default function UserMenu({ user }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const buttonRef = useRef(null);
  const itemRefs = useRef([]);
  const pathname = usePathname();

  // Close when the page changes.
  const [lastPath, setLastPath] = useState(pathname);
  if (pathname !== lastPath) {
    setLastPath(pathname);
    setOpen(false);
  }

  // Close on a click outside the menu, or on Escape.
  useEffect(() => {
    if (!open) return;
    function onPointerDown(e) {
      if (!rootRef.current?.contains(e.target)) setOpen(false);
    }
    function onKeyDown(e) {
      if (e.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  function openAndFocus(index) {
    setOpen(true);
    requestAnimationFrame(() => itemRefs.current[index]?.focus());
  }

  function onButtonKeyDown(e) {
    if (e.key === "ArrowDown") { e.preventDefault(); openAndFocus(0); }
    if (e.key === "ArrowUp") { e.preventDefault(); openAndFocus(ITEMS.length - 1); }
  }

  // Up/Down arrows move between menu items.
  function onMenuKeyDown(e) {
    const current = itemRefs.current.indexOf(document.activeElement);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const step = e.key === "ArrowDown" ? 1 : -1;
      itemRefs.current[(current + step + ITEMS.length) % ITEMS.length]?.focus();
    }
    if (e.key === "Tab") setOpen(false);
  }

  const label = user?.name ? `Account menu for ${user.name}` : "Account menu";

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        onKeyDown={onButtonKeyDown}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls="user-menu"
        aria-label={label}
        className="flex items-center gap-2 rounded-full p-0.5 pr-2 hover:bg-paper aria-expanded:bg-paper"
      >
        <Avatar user={user} />
        {user?.name && <span className="hidden max-w-40 truncate text-sm font-medium sm:block">{user.name}</span>}
        <svg viewBox="0 0 20 20" aria-hidden="true" className={`h-4 w-4 fill-muted transition-transform ${open ? "rotate-180" : ""}`}>
          <path d="M5.3 7.3a1 1 0 0 1 1.4 0L10 10.6l3.3-3.3a1 1 0 1 1 1.4 1.4l-4 4a1 1 0 0 1-1.4 0l-4-4a1 1 0 0 1 0-1.4Z" />
        </svg>
      </button>

      {open && (
        <div
          id="user-menu"
          role="menu"
          aria-label="Account"
          onKeyDown={onMenuKeyDown}
          className="absolute right-0 z-20 mt-2 w-60 overflow-hidden rounded-lg border border-line bg-surface shadow-lg"
        >
          {(user?.name || user?.email) && (
            <div className="border-b border-line px-4 py-3">
              {user.name && <p className="truncate font-medium">{user.name}</p>}
              {user.email && <p className="truncate text-sm text-muted">{user.email}</p>}
            </div>
          )}
          <ul className="py-1">
            {ITEMS.map((item, i) => (
              <li key={item.href} role="none">
                <Link
                  ref={(el) => { itemRefs.current[i] = el; }}
                  href={item.href}
                  role="menuitem"
                  className="block px-4 py-2 text-sm hover:bg-paper focus:bg-paper focus:outline-none"
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}