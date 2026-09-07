import { Menu, Moon, Sun, X } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { navigationItems } from "../constants/navigation";
import { useTheme } from "../contexts/ThemeContext";
import { IntelligenceSyncBar } from "../components/common/IntelligenceSyncBar";

export function DashboardLayout() {
  const { theme, toggleTheme } = useTheme();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isCompactNavigation, setIsCompactNavigation] = useState(() =>
    typeof window === "undefined" || !window.matchMedia ? false : window.matchMedia("(max-width: 1100px)").matches
  );
  const now = new Date();
  const primaryNavigation = navigationItems.filter((item) =>
    ["Dashboard", "GIS Map", "Predictions", "Alerts", "Settings"].includes(item.label)
  );

  useEffect(() => {
    if (!window.matchMedia) return;
    const media = window.matchMedia("(max-width: 1100px)");
    const handleChange = () => {
      setIsCompactNavigation(media.matches);
      if (!media.matches) setIsSidebarOpen(false);
    };
    handleChange();
    media.addEventListener("change", handleChange);
    return () => media.removeEventListener("change", handleChange);
  }, []);

  const toggleNavigation = () => {
    if (isCompactNavigation) {
      setIsSidebarOpen((current) => !current);
      return;
    }
    setIsSidebarCollapsed((current) => !current);
  };
  const navigationButtonLabel = isCompactNavigation
    ? isSidebarOpen ? "Close navigation" : "Open navigation"
    : isSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar";

  return (
    <div className={`app-shell ${isSidebarCollapsed ? "sidebar-collapsed" : ""} ${isSidebarOpen ? "sidebar-open" : ""}`}>
      <button className="sidebar-backdrop" type="button" aria-label="Close navigation" onClick={() => setIsSidebarOpen(false)} />
      <aside className="sidebar">
        <div className="sidebar-header">
          <NavLink to="/" className="brand" onClick={() => setIsSidebarOpen(false)}>
            <span className="brand-logo" aria-hidden="true">
              <img src="/favicon.svg" alt="" />
            </span>
            <div>
              <strong>FireSight AI</strong>
              <small>Environmental Intelligence</small>
            </div>
          </NavLink>
          <button className="sidebar-close-button" type="button" aria-label="Close navigation" onClick={() => setIsSidebarOpen(false)}>
            <X size={18} />
          </button>
        </div>
        <nav>
          {primaryNavigation.map((item) => (
            <NavLink
              to={item.href}
              key={item.label}
              title={!isCompactNavigation && isSidebarCollapsed ? item.label : undefined}
              aria-label={item.label}
              onClick={() => setIsSidebarOpen(false)}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              <item.icon size={18} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <button className="icon-button" type="button" onClick={toggleNavigation} aria-label={navigationButtonLabel}>
            {isCompactNavigation && isSidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <div className="topbar-spacer" />
          <div className="topbar-actions">
            <span className="date-chip">
              {now.toLocaleDateString()} · {now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
            <button className="icon-button" type="button" onClick={toggleTheme} aria-label="Toggle theme">
              {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
            </button>
            <div className="profile">FO</div>
          </div>
        </header>
        <main className="content">
          <IntelligenceSyncBar />
          <Outlet />
        </main>
      </div>
    </div>
  );
}
