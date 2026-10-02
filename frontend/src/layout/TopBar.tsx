import { useLocation } from "react-router-dom";
import type { CurrentUser } from "../auth/types";
import { NAV_ITEMS } from "./navConfig";

interface TopBarProps {
  user: CurrentUser | null;
  loading: boolean;
  onLogout: () => void;
}

function usePageTitle(): string {
  const { pathname } = useLocation();
  const matches = NAV_ITEMS.filter(
    (item) => pathname === item.path || pathname.startsWith(`${item.path}/`),
  );
  // Longest path wins, so /settings/team beats /settings.
  matches.sort((a, b) => b.path.length - a.path.length);
  return matches[0]?.label ?? "Helpdesk";
}

export default function TopBar({ user, loading, onLogout }: TopBarProps) {
  const title = usePageTitle();
  const displayName = user ? (user.full_name ?? user.email) : null;

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-gray-200 bg-white px-6">
      <h1 className="text-base font-semibold">{title}</h1>

      <div className="flex items-center gap-4">
        {loading && <span className="text-sm text-gray-500">Loading...</span>}

        {user && (
          <div className="text-right leading-tight">
            <div className="text-sm font-medium">{displayName}</div>
            <div className="text-xs capitalize text-gray-500">{user.role}</div>
          </div>
        )}

        {!loading && !user && (
          <span className="text-sm text-gray-500">Not signed in</span>
        )}

        <button
          type="button"
          onClick={onLogout}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100"
        >
          Log out
        </button>
      </div>
    </header>
  );
}