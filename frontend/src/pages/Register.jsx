import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client.js";
import AuthLayout from "../components/AuthLayout.jsx";
import { Alert, Button, Field, inputClass } from "../components/ui.jsx";
import { useAuth } from "../context/AuthContext.jsx";

const MIN_PASSWORD_LENGTH = 10; // keep in sync with the API (schemas/auth.py)

export default function Register() {
  const { user, register } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to="/orders" replace />;

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register({ email, fullName, password });
      navigate("/orders", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Create your account"
      footer={
        <>
          Already registered?{" "}
          <Link to="/login" className="font-medium text-indigo-600 hover:underline dark:text-indigo-400">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <Alert>{error}</Alert>}
        <Field label="Full name" htmlFor="full-name">
          <input
            id="full-name"
            type="text"
            autoComplete="name"
            required
            maxLength={255}
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label="Email" htmlFor="email">
          <input
            id="email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputClass}
          />
        </Field>
        <Field
          label="Password"
          htmlFor="password"
          hint={`At least ${MIN_PASSWORD_LENGTH} characters. A few random words make a good one.`}
        >
          <input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={MIN_PASSWORD_LENGTH}
            maxLength={128}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
          />
        </Field>
        <Button type="submit" disabled={submitting} className="w-full">
          {submitting ? "Creating account…" : "Create account"}
        </Button>
      </form>
    </AuthLayout>
  );
}
