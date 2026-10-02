import { Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

export default function Layout() {
  const { user, loading, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    // logout() calls the API, clears the token, and resets the shared user.
    await logout();
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