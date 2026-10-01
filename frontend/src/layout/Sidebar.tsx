import { NavLink } from "react-router-dom";
import type { CurrentUser } from "../auth/types";
import { NAV_ITEMS } from "./navConfig";

interface SidebarProps {
  user: CurrentUser | null;
}

export default function Sidebar({ user }: SidebarProps) {
  const items = user
    ? NAV_ITEMS.filter((item) => item.roles.includes(user.role))
    : [];

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-gray-200 bg-white">
      <div className="flex h-14 items-center border-b border-gray-200 px-5 text-lg font-semibold">
        Helpdesk
      </div>

      <nav className="flex-1 space-y-1 p-3">
        {items.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.end}
            className={({ isActive }) =>
              [
                "block rounded-md px-3 py-2 text-sm font-medium",
                isActive
                  ? "bg-indigo-50 text-indigo-700"
                  : "text-gray-600 hover:bg-gray-100 hover:text-gray-900",
              ].join(" ")
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}