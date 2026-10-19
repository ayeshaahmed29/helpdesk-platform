import { Navigate } from "react-router-dom";

import { useAuth } from "../auth/useAuth";

export default function HomeRedirect() {
  const { user } = useAuth();

  if (user?.role === "customer") {
    return <Navigate to="/portal" replace />;
  }
  return <Navigate to="/tickets" replace />;
}