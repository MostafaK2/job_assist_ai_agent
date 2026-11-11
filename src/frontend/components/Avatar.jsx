import Image from "next/image";

/** The user's photo, or their initials, or a plain person icon if we don't know who they are yet. */
export default function Avatar({ user, size = 32 }) {
  const style = { width: size, height: size };

  if (user?.picture) {
    return (
      <Image
        src={user.picture}
        alt=""
        width={size}
        height={size}
        className="rounded-full object-cover"
        referrerPolicy="no-referrer"
      />
    );
  }

  const initials = (user?.name || "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");

  return (
    <span style={style} className="flex items-center justify-center rounded-full bg-ink text-xs font-bold text-white">
      {initials || (
        <svg viewBox="0 0 24 24" aria-hidden="true" className="h-1/2 w-1/2 fill-current">
          <path d="M12 12a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9Zm0 2c-4.4 0-8 2.2-8 5v1h16v-1c0-2.8-3.6-5-8-5Z" />
        </svg>
      )}
    </span>
  );
}