import { BrowserRouter, Routes, Route, Navigate, Link } from "react-router-dom";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Alerts from "./pages/Alerts";
import Settings from "./pages/Settings";
import Admin from "./pages/Admin";

function Protected({ children, admin }) {
  if (!localStorage.getItem("token")) return <Navigate to="/login" />;
  if (admin && localStorage.getItem("role") !== "admin") return <Navigate to="/" />;
  return children;
}

export default function App() {
  const logout = () => {
    localStorage.clear();
    window.location.href = "/login";
  };
  return (
    <BrowserRouter>
      <nav style={{ display: "flex", gap: 16, padding: 12 }}>
        <Link to="/">Dashboard</Link>
        <Link to="/alerts">Alerts</Link>
        <Link to="/settings">Settings</Link>
        <Link to="/admin">Admin</Link>
        <button onClick={logout}>Logout</button>
      </nav>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/" element={<Protected><Dashboard /></Protected>} />
        <Route path="/alerts" element={<Protected><Alerts /></Protected>} />
        <Route path="/settings" element={<Protected><Settings /></Protected>} />
        <Route path="/admin" element={<Protected admin><Admin /></Protected>} />
      </Routes>
    </BrowserRouter>
  );
}