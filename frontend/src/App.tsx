import { Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./auth/ProtectedRoute";
import Layout from "./layout/Layout";
import NotFound from "./pages/NotFound";
import Placeholder from "./pages/Placeholder";
import TicketList from "./pages/TicketList";
import TicketDetail from "./pages/TicketDetail";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Placeholder title="Login" />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/tickets" replace />} />
          <Route path="/tickets" element={<TicketList />} />
          <Route path="/tickets/:id" element={<TicketDetail />} />
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