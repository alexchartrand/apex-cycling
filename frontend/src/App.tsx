import { Navigate, Route, Routes } from "react-router-dom";
import { LoginPage } from "./features/auth/LoginPage";
import { SignupPage } from "./features/auth/SignupPage";
import { DashboardPage } from "./routes/DashboardPage";
import { ProgressionPage } from "./routes/ProgressionPage";
import { ProtectedRoute } from "./routes/ProtectedRoute";
import { SessionDetailPage } from "./routes/SessionDetailPage";
import { SessionsPage } from "./routes/SessionsPage";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/sessions" element={<SessionsPage />} />
        <Route path="/sessions/:eventId" element={<SessionDetailPage />} />
        <Route path="/progression" element={<ProgressionPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
