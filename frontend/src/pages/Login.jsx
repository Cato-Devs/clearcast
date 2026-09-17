import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import api from "../api/client";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const nav = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.post("/auth/login", { email, password });
      localStorage.setItem("token", data.access_token);
      localStorage.setItem("role", data.role);
      nav("/");
    } catch {
      setError("Invalid email or password");
    }
  };

  return (
    <form onSubmit={submit} style={{ maxWidth: 320, margin: "40px auto", display: "grid", gap: 8 }}>
      <h2>ClearCast Login</h2>
      <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
      <button type="submit">Sign in</button>
      {error && <p style={{ color: "red" }}>{error}</p>}
      <Link to="/register">Register</Link>
    </form>
  );
}