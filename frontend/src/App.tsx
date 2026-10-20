import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ForgotPasswordPage } from "./features/auth/ForgotPasswordPage";
import { LoginPage } from "./features/auth/LoginPage";
import { ResetPasswordPage } from "./features/auth/ResetPasswordPage";
import { SignupPage } from "./features/auth/SignupPage";
import { ComingSoonPage } from "./routes/ComingSoonPage";
import { HomePage } from "./routes/HomePage";
import { ImportPage } from "./routes/ImportPage";
import { LogPage } from "./routes/LogPage";
import { ProgressPage } from "./routes/ProgressPage";
import { RecordsPage } from "./routes/RecordsPage";
import { ProtectedRoute } from "./routes/ProtectedRoute";
import { SessionDetailPage } from "./routes/SessionDetailPage";
import { SettingsPage } from "./routes/SettingsPage";

// Dev-only living style guide; the lazy import keeps it out of prod bundles.
const StyleguidePage = import.meta.env.DEV
  ? lazy(() => import("./routes/dev/StyleguidePage").then((m) => ({ default: m.StyleguidePage })))
  : null;

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      {StyleguidePage && (
        <Route
          path="/styleguide"
          element={
            <Suspense fallback={null}>
              <StyleguidePage />
            </Suspense>
          }
        />
      )}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/log" element={<LogPage />} />
          <Route path="/sessions/:eventId" element={<SessionDetailPage />} />
          <Route path="/activities/:activityId" element={<ComingSoonPage section="log" />} />
          <Route path="/records" element={<RecordsPage />} />
          <Route path="/progress" element={<ProgressPage />} />
          <Route path="/tools/*" element={<ComingSoonPage section="tools" />} />
          <Route path="/aero" element={<ComingSoonPage section="aero" />} />
          <Route path="/equipment" element={<ComingSoonPage section="equipment" />} />
          <Route path="/coach" element={<ComingSoonPage section="coach" />} />
          <Route path="/club/*" element={<ComingSoonPage section="club" />} />
          <Route path="/import" element={<ImportPage />} />
          <Route path="/settings/*" element={<SettingsPage />} />

          {/* Pre-redesign URLs */}
          <Route path="/sessions" element={<Navigate to="/log" replace />} />
          <Route path="/progression" element={<Navigate to="/progress" replace />} />
          <Route path="/profile" element={<Navigate to="/settings/profile" replace />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
