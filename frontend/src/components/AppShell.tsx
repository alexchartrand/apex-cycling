import { NavLink, Outlet } from "react-router-dom";
import { useCurrentUser, useLogout } from "../features/auth/useAuth";
import "./AppShell.css";

const NAV_ITEMS = [
  { to: "/", label: "Home", end: true },
  { to: "/profile", label: "Profile" },
  { to: "/import", label: "Import" },
  { to: "/sessions", label: "Sessions" },
  { to: "/progression", label: "Progress" },
];

export function AppShell() {
  const { data: user } = useCurrentUser();
  const logout = useLogout();

  return (
    <div className="app-shell">
      <aside className="app-shell__sidebar">
        <p className="app-shell__brand">Track Trainer</p>
        <nav className="app-shell__nav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? "app-shell__nav-link--active" : undefined)}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="app-shell__account">
          <span className="app-shell__account-email">{user?.email}</span>
          <button onClick={() => logout.mutate()} disabled={logout.isPending}>
            Log out
          </button>
        </div>
      </aside>
      <main className="app-shell__main">
        <div className="app-shell__content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
