import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate } from "react-router-dom";
import { useAccess } from "../access/access-context";
import { ApiError } from "../api/client";


export function AdminAccessPage() {
  const { t } = useTranslation();
  const { role, login } = useAccess();
  const navigate = useNavigate();
  const [secret, setSecret] = useState("");
  const [state, setState] = useState<"idle" | "submitting" | "invalid" | "limited">("idle");

  if (role === "admin") return <Navigate to="/analyses" replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!secret) return;
    setState("submitting");
    try {
      await login(secret);
      setSecret("");
      navigate("/analyses", { replace: true });
    } catch (error) {
      setSecret("");
      setState(error instanceof ApiError && error.status === 429 ? "limited" : "invalid");
    }
  }

  return (
    <main className="admin-access-page">
      <section className="admin-access-copy">
        <p>{t("access.kicker")}</p>
        <h1>{t("access.title")}</h1>
        <span>{t("access.description")}</span>
      </section>
      <form className="admin-access-form" onSubmit={(event) => void submit(event)}>
        <span className="admin-access-mark" aria-hidden="true">運</span>
        <label>
          <span>{t("access.password")}</span>
          <input
            aria-label={t("access.password")}
            autoComplete="current-password"
            type="password"
            value={secret}
            onChange={(event) => setSecret(event.target.value)}
          />
        </label>
        <button type="submit" disabled={!secret || state === "submitting"}>
          {state === "submitting" ? t("access.submitting") : t("access.submit")}
        </button>
        {state === "invalid" && <p className="inline-error" role="alert">{t("access.invalid")}</p>}
        {state === "limited" && <p className="inline-error" role="alert">{t("access.rateLimited")}</p>}
      </form>
    </main>
  );
}
