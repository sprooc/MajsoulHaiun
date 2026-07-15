import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { createAdminSession, deleteAdminSession, getAccessRole, type AccessRole } from "../api/client";


type AccessState = "checking" | AccessRole;

interface AccessContextValue {
  role: AccessState;
  login: (secret: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AccessContext = createContext<AccessContextValue | null>(null);


export function AccessProvider({ children }: { children: ReactNode }) {
  const [role, setRole] = useState<AccessState>("checking");

  useEffect(() => {
    const controller = new AbortController();
    void getAccessRole(controller.signal)
      .then((response) => setRole(response.role))
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) setRole("guest");
      });
    return () => controller.abort();
  }, []);

  const value = useMemo<AccessContextValue>(() => ({
    role,
    login: async (secret: string) => {
      const response = await createAdminSession(secret);
      setRole(response.role);
    },
    logout: async () => {
      await deleteAdminSession();
      setRole("guest");
    },
  }), [role]);

  return <AccessContext.Provider value={value}>{children}</AccessContext.Provider>;
}


export function useAccess(): AccessContextValue {
  const value = useContext(AccessContext);
  if (value === null) throw new Error("useAccess must be used within AccessProvider");
  return value;
}


export function RequireAdmin({ children }: { children: ReactNode }) {
  const { role } = useAccess();
  if (role === "checking") return <main className="workspace"><p className="empty-state">…</p></main>;
  if (role !== "admin") return <Navigate to="/" replace />;
  return children;
}
