import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { signIn } from "../api/authApi";

export default function SignInPage() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");

    if (!email.trim()) {
      setError("Please enter your email.");
      return;
    }

    if (!password.trim()) {
      setError("Please enter your password.");
      return;
    }

    try {
      setLoading(true);

      const res = await signIn({ email, password });

      if (res?.message === "Login successful") {
        navigate("/dashboard");
      } else {
        setError("Login unsuccessful");
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Login unsuccessful");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="ef-auth-page">
      <div className="ef-auth-shell">
        <div className="ef-auth-left">
          <div className="ef-auth-brand">
            <div className="ef-auth-brand-icon">♻️</div>
            <div className="ef-auth-brand-text">
              <h1>EcoFit</h1>
              <p>Municipal waste intelligence platform</p>
            </div>
          </div>

          <div className="ef-auth-hero">
            <div className="ef-auth-hero-kicker">Welcome back</div>
            <h2 className="ef-auth-hero-title">
              Sign in to access the municipal dashboard.
            </h2>
            <p className="ef-auth-hero-text">
              Monitor complaints, manage service logs, view ward risk maps,
              and generate action plans from one platform.
            </p>
          </div>
        </div>

        <div className="ef-auth-right">
          <div className="ef-auth-card">
            <div className="ef-auth-card-header">
              <h2 className="ef-auth-card-title">Sign In</h2>
              <p className="ef-auth-card-subtitle">
                Enter your account credentials to continue.
              </p>
            </div>

            <form className="ef-form" onSubmit={handleSubmit}>
              <div className="ef-field">
                <label className="ef-label">Email</label>
                <input
                  className="ef-input"
                  type="email"
                  placeholder="Enter your email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              <div className="ef-field">
                <label className="ef-label">Password</label>
                <div className="ef-password-wrap">
                  <input
                    className="ef-input ef-password-input"
                    type={showPassword ? "text" : "password"}
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    className="ef-eye-btn"
                    onClick={() => setShowPassword((v) => !v)}
                  >
                    {showPassword ? "🙈" : "👁️"}
                  </button>
                </div>
              </div>

              {error ? <div className="ef-alert ef-alert-error">{error}</div> : null}

              <button type="submit" className="ef-btn" disabled={loading}>
                {loading ? "Signing In..." : "Sign In"}
              </button>
            </form>

            <div className="ef-auth-footer">
              Don't have an account?{" "}
              <Link to="/sign-up" className="ef-auth-link">
                Sign Up
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}