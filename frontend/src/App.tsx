import { Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./auth/ProtectedRoute";
import Layout from "./layout/Layout";
import AcceptInvite from "./pages/AcceptInvite";
import AuditLog from "./pages/AuditLog";
import ForgotPassword from "./pages/ForgotPassword";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import Placeholder from "./pages/Placeholder";
import ResetPassword from "./pages/ResetPassword";
import Signup from "./pages/Signup";
import TicketList from "./pages/TicketList";
import TicketDetail from "./pages/TicketDetail";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password/:token" element={<ResetPassword />} />
      <Route path="/accept-invite/:token" element={<AcceptInvite />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/tickets" replace />} />
          <Route path="/tickets" element={<TicketList />} />
          <Route path="/tickets/:id" element={<TicketDetail />} />
          <Route path="/portal" element={<Placeholder title="My tickets" />} />
          <Route path="/settings" element={<Placeholder title="Settings" />} />
          <Route path="/settings/team" element={<Placeholder title="Team" />} />
          <Route path="/audit-log" element={<AuditLog />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}