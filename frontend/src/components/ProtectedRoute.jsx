import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

// Gate for pages that need a logged-in user.
export default function ProtectedRoute({ children }) {
  const { token, loading } = useAuth();
  if (loading) return <div className="p-8 text-slate-400">Loading…</div>;
  return token ? children : <Navigate to="/login" replace />;
}
