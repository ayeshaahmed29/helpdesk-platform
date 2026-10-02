import { Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./auth/ProtectedRoute";
import Layout from "./layout/Layout";
import NotFound from "./pages/NotFound";
import Placeholder from "./pages/Placeholder";

export default function App() {
  return (
    <Routes>
      {/* Temporary: replaced by the real login page in its own issue. */}
      <Route path="/login" element={<Placeholder title="Login" />} />

      {/* Everything below requires a logged-in user. */}
      <Route element={<ProtectedRoute />}>
        {/* Everything inside the shared layout. */}
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/tickets" replace />} />
          <Route path="/tickets" element={<Placeholder title="Tickets" />} />
          <Route path="/tickets/:id" element={<Placeholder title="Ticket detail" />} />
          <Route path="/portal" element={<Placeholder title="My tickets" />} />
          <Route path="/settings" element={<Placeholder title="Settings" />} />
          <Route path="/settings/team" element={<Placeholder title="Team" />} />
          <Route path="/audit-log" element={<Placeholder title="Audit log" />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}