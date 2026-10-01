import { Outlet, useNavigate } from "react-router-dom";
import { apiFetch, clearToken } from "../api/client";
import { useCurrentUser } from "../auth/useCurrentUser";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

export default function Layout() {
  const { user, loading } = useCurrentUser();
  const navigate = useNavigate();

  async function handleLogout() {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } catch {
      // Clear the local token even if the server call fails.
    }
    clearToken();
    navigate("/login", { replace: true });
  }

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900">
      <Sidebar user={user} />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar user={user} loading={loading} onLogout={handleLogout} />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}