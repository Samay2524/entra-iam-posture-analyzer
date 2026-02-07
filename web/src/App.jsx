import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import Setup from "./pages/Setup";
import Dashboard from "./pages/Dashboard";
import IdentityDetail from "./pages/IdentityDetail";
import Reports from "./pages/Reports";

const navItems = [
  { name: "Setup", path: "/" },
  { name: "Dashboard", path: "/dashboard" },
];

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-[#f8f7f4] text-ink">
        <div className="flex">
          <aside className="hidden md:flex w-64 min-h-screen flex-col border-r border-border bg-[#f3f2ee]">
            <div className="px-6 py-5 border-b border-border">
              <div className="text-lg font-semibold">Entra IAM</div>
              <div className="text-xs uppercase tracking-wide text-muted">Posture Analyzer</div>
            </div>
            <nav className="flex-1 px-3 py-4 space-y-1">
              {navItems.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) =>
                    `flex items-center rounded-lg px-3 py-2 text-sm font-medium ${
                      isActive
                        ? "bg-white text-ink shadow-card"
                        : "text-ink/80 hover:bg-white/60"
                    }`
                  }
                >
                  {item.name}
                </NavLink>
              ))}
            </nav>
            <div className="px-6 py-4 border-t border-border text-xs text-muted">
              Support • Changelog
            </div>
          </aside>

          <main className="flex-1">
            <header className="sticky top-0 z-10 bg-[#f8f7f4]/80 backdrop-blur border-b border-border">
              <div className="px-6 py-4 flex items-center justify-between">
                <div className="text-sm text-muted">Good afternoon</div>
                <div className="text-xs text-muted">Last week</div>
              </div>
            </header>

            <div className="px-4 py-6 max-w-none">
              <Routes>
                <Route path="/" element={<Setup />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/identity" element={<IdentityDetail />} />
                <Route path="/reports" element={<Reports />} />
              </Routes>
            </div>
          </main>
      </div>
      </div>
    </BrowserRouter>
  );
}

export default App;
