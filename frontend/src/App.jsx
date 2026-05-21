import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Dashboard    from "./pages/Dashboard";
import Clients      from "./pages/Clients";
import RiskAnalytics from "./pages/RiskAnalytics";
import TopInvestors  from "./pages/TopInvestors";
import AIFeed        from "./pages/AIFeed";
import Assistant     from "./pages/Assistant";
import AWSStatus     from "./pages/AWSStatus";

const NAV = [
  { to: "/",          icon: "📊", label: "Dashboard"     },
  { to: "/clients",   icon: "👥", label: "Clients"        },
  { to: "/risk",      icon: "⚠️",  label: "Risk Analytics" },
  { to: "/investors", icon: "🏆", label: "Top Investors"  },
  { to: "/feed",      icon: "📡", label: "AI Feed"        },
  { to: "/assistant", icon: "🤖", label: "AI Assistant"   },
  { to: "/aws",       icon: "☁️",  label: "AWS Services"  },
];

export default function App() {
  return (
    <BrowserRouter>
      <div className="layout">
        <nav className="sidebar">
          <div className="sidebar-logo">
            AI Portfolio
            <span>Risk Intelligence Platform</span>
          </div>
          {NAV.map(n => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) => "nav" + (isActive ? " active" : "")}
            >
              <span className="nav-icon">{n.icon}</span>
              <span>{n.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="main">
          <Routes>
            <Route path="/"          element={<Dashboard />}     />
            <Route path="/clients"   element={<Clients />}       />
            <Route path="/risk"      element={<RiskAnalytics />} />
            <Route path="/investors" element={<TopInvestors />}  />
            <Route path="/feed"      element={<AIFeed />}        />
            <Route path="/assistant" element={<Assistant />}     />
            <Route path="/aws"       element={<AWSStatus />}     />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}
