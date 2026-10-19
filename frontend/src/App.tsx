import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { LoginPage } from "./features/auth/LoginPage";
import { SignupPage } from "./features/auth/SignupPage";
import { HomePage } from "./routes/HomePage";
import { ImportPage } from "./routes/ImportPage";
import { ProfilePage } from "./routes/ProfilePage";
import { ProgressionPage } from "./routes/ProgressionPage";
import { ProtectedRoute } from "./routes/ProtectedRoute";
import { SessionsPage } from "./routes/SessionsPage";

// Dev-only living style guide; the lazy import keeps it out of prod bundles.
const StyleguidePage = import.meta.env.DEV
  ? lazy(() => import("./routes/dev/StyleguidePage").then((m) => ({ default: m.StyleguidePage })))
  : null;

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
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
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/import" element={<ImportPage />} />
          <Route path="/sessions" element={<SessionsPage />} />
          <Route path="/sessions/:eventId" element={<SessionsPage />} />
          <Route path="/progression" element={<ProgressionPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
