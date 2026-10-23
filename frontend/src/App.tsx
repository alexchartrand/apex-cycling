import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { RouteFallback } from "./components/RouteFallback";
import { ForgotPasswordPage } from "./features/auth/ForgotPasswordPage";
import { LoginPage } from "./features/auth/LoginPage";
import { ResetPasswordPage } from "./features/auth/ResetPasswordPage";
import { SignupPage } from "./features/auth/SignupPage";
import { ProtectedRoute } from "./routes/ProtectedRoute";

// Every page after sign-in is its own chunk, so charts and the physics code
// only load where they are used.
const AdminPage = lazy(() => import("./routes/AdminPage").then((m) => ({ default: m.AdminPage })));
const ClubPage = lazy(() => import("./routes/ClubPage").then((m) => ({ default: m.ClubPage })));
const ClubsPage = lazy(() => import("./routes/ClubsPage").then((m) => ({ default: m.ClubsPage })));
const CoachPage = lazy(() => import("./routes/CoachPage").then((m) => ({ default: m.CoachPage })));
const HomePage = lazy(() => import("./routes/HomePage").then((m) => ({ default: m.HomePage })));
const ActivityPage = lazy(() => import("./routes/ActivityPage").then((m) => ({ default: m.ActivityPage })));
const EquipmentPage = lazy(() => import("./routes/EquipmentPage").then((m) => ({ default: m.EquipmentPage })));
const AeroPage = lazy(() => import("./routes/AeroPage").then((m) => ({ default: m.AeroPage })));
const ImportPage = lazy(() => import("./routes/ImportPage").then((m) => ({ default: m.ImportPage })));
const PowerCurvePage = lazy(() => import("./routes/PowerCurvePage").then((m) => ({ default: m.PowerCurvePage })));
const JoinPage = lazy(() => import("./routes/JoinPage").then((m) => ({ default: m.JoinPage })));
const LogPage = lazy(() => import("./routes/LogPage").then((m) => ({ default: m.LogPage })));
const ProgressPage = lazy(() => import("./routes/ProgressPage").then((m) => ({ default: m.ProgressPage })));
const RecordsPage = lazy(() => import("./routes/RecordsPage").then((m) => ({ default: m.RecordsPage })));
const PursuitBoardPage = lazy(() => import("./routes/PursuitBoardPage").then((m) => ({ default: m.PursuitBoardPage })));
const SessionDetailPage = lazy(() => import("./routes/SessionDetailPage").then((m) => ({ default: m.SessionDetailPage })));
const SettingsPage = lazy(() => import("./routes/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const ToolsPage = lazy(() => import("./routes/ToolsPage").then((m) => ({ default: m.ToolsPage })));

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
        {/* Full screen at the track side, without the app chrome. */}
        <Route
          path="/tools/pursuit/board"
          element={
            <Suspense fallback={<RouteFallback />}>
              <PursuitBoardPage />
            </Suspense>
          }
        />
        <Route element={<AppShell />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/log" element={<LogPage />} />
          <Route path="/sessions/:eventId" element={<SessionDetailPage />} />
          <Route path="/activities/:activityId" element={<ActivityPage />} />
          <Route path="/records" element={<RecordsPage />} />
          <Route path="/progress" element={<ProgressPage />} />
          <Route path="/power" element={<PowerCurvePage />} />
          <Route path="/tools/*" element={<ToolsPage />} />
          <Route path="/aero" element={<AeroPage />} />
          <Route path="/equipment" element={<EquipmentPage />} />
          <Route path="/coach" element={<CoachPage />} />
          <Route path="/club" element={<ClubsPage />} />
          <Route path="/club/:clubId/*" element={<ClubPage />} />
          <Route path="/join" element={<JoinPage />} />
          <Route path="/admin" element={<AdminPage />} />
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
