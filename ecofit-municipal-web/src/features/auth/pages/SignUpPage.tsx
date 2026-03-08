import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { signUp } from "../api/authApi";

export default function SignUpPage() {
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState("Municipal Officer");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [organization, setOrganization] = useState("Colombo Municipal Council");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [agree, setAgree] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");

    if (!fullName.trim()) {
      setError("Please enter your full name.");
      return;
    }

    if (!email.trim()) {
      setError("Please enter your email.");
      return;
    }

    if (!password.trim()) {
      setError("Please enter a password.");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    if (!agree) {
      setError("Please accept the terms to continue.");
      return;
    }

    try {
      setLoading(true);

      await signUp({
        fullName,
        role,
        email,
        phone,
        password,
        organization,
      });

      navigate("/sign-in");
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Sign up failed.");
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
            <div className="ef-auth-hero-kicker">Create account</div>
            <h2 className="ef-auth-hero-title">
              Join a smarter municipal operations network.
            </h2>
            <p className="ef-auth-hero-text">
              Create your account to access complaint management, service log
              operations, ward risk prediction, and route planning tools.
            </p>
          </div>

          <div className="ef-auth-points">
            <div className="ef-auth-point">
              <div className="ef-auth-point-icon">🧾</div>
              <div>Track complaints, incidents, and operational changes</div>
            </div>

            <div className="ef-auth-point">
              <div className="ef-auth-point-icon">🗺️</div>
              <div>Use prediction-backed priority maps and route planning</div>
            </div>

            <div className="ef-auth-point">
              <div className="ef-auth-point-icon">🏛️</div>
              <div>Built for municipal teams, supervisors, and field operations</div>
            </div>
          </div>
        </div>

        <div className="ef-auth-right">
          <div className="ef-auth-card">
            <div className="ef-auth-card-header">
              <h2 className="ef-auth-card-title">Sign Up</h2>
              <p className="ef-auth-card-subtitle">
                Create your EcoFit municipal dashboard account.
              </p>
            </div>

            <form className="ef-form" onSubmit={handleSubmit}>
              <div className="ef-input-row">
                <div className="ef-field">
                  <label className="ef-label">Full Name</label>
                  <input
                    className="ef-input"
                    type="text"
                    placeholder="Enter your full name"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                  />
                </div>

                <div className="ef-field">
                  <label className="ef-label">Role</label>
                  <select
                    className="ef-select"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                  >
                    <option>Municipal Officer</option>
                    <option>Operations Manager</option>
                    <option>Field Supervisor</option>
                    <option>Admin</option>
                  </select>
                </div>
              </div>

              <div className="ef-input-row">
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
                  <label className="ef-label">Phone</label>
                  <input
                    className="ef-input"
                    type="text"
                    placeholder="Enter your phone number"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                  />
                </div>
              </div>

              <div className="ef-field">
                <label className="ef-label">Organization</label>
                <input
                  className="ef-input"
                  type="text"
                  placeholder="Municipal organization"
                  value={organization}
                  onChange={(e) => setOrganization(e.target.value)}
                />
              </div>

              <div className="ef-input-row">
                <div className="ef-field">
                  <label className="ef-label">Password</label>
                  <div className="ef-password-wrap">
                    <input
                      className="ef-input ef-password-input"
                      type={showPassword ? "text" : "password"}
                      placeholder="Create password"
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

                <div className="ef-field">
                  <label className="ef-label">Confirm Password</label>
                  <div className="ef-password-wrap">
                    <input
                      className="ef-input ef-password-input"
                      type={showConfirmPassword ? "text" : "password"}
                      placeholder="Confirm password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                    />
                    <button
                      type="button"
                      className="ef-eye-btn"
                      onClick={() => setShowConfirmPassword((v) => !v)}
                    >
                      {showConfirmPassword ? "🙈" : "👁️"}
                    </button>
                  </div>
                </div>
              </div>

              <label className="ef-checkbox-row">
                <input
                  type="checkbox"
                  checked={agree}
                  onChange={(e) => setAgree(e.target.checked)}
                />
                <span>I agree to the terms and platform usage policy</span>
              </label>

              {error ? <div className="ef-alert ef-alert-error">{error}</div> : null}

              <button type="submit" className="ef-btn" disabled={loading}>
                {loading ? "Creating Account..." : "Create Account"}
              </button>
            </form>

            <div className="ef-auth-footer">
              Already have an account?{" "}
              <Link to="/sign-in" className="ef-auth-link">
                Sign In
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}