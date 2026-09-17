import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import api from "../api/client";

export default function Register() {
  const [f, setF] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const nav = useNavigate();
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/auth/register", f);
      nav("/login");
    } catch (err) {
      const d = err.response?.data?.detail;
      setError(typeof d === "string" ? d : "Check your details (password min 8 characters)");
    }
  };

  return (
    <form onSubmit={submit} style={{ maxWidth: 320, margin: "40px auto", display: "grid", gap: 8 }}>
      <h2>Create account</h2>
      <input placeholder="Name" value={f.name} onChange={set("name")} />
      <input placeholder="Email" value={f.email} onChange={set("email")} />
      <input type="password" placeholder="Password" value={f.password} onChange={set("password")} />
      <button type="submit">Register</button>
      {error && <p style={{ color: "red" }}>{error}</p>}
      <Link to="/login">Back to login</Link>
    </form>
  );
}