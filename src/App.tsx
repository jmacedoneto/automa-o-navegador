import React from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import type { Session } from "@supabase/supabase-js";
import Dashboard from "./pages/Dashboard";
import AutomationEditor from "./pages/AutomationEditor";
import Settings from "./pages/Settings";
import ExecutionLogs from "./pages/ExecutionLogs";
import Cobranca from "./pages/Cobranca";
import NotFound from "./pages/NotFound";
import Login from "./pages/Login";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1 },
  },
});

// ── Error Boundary ────────────────────────────────────────────────────────────

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: string }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: "" };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error?.message || "Erro desconhecido" };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-background p-8">
          <p className="text-lg font-semibold text-destructive">Algo deu errado</p>
          <p className="text-sm text-muted-foreground max-w-md text-center">{this.state.error}</p>
          <button
            className="px-4 py-2 rounded bg-primary text-primary-foreground text-sm"
            onClick={() => window.location.reload()}
          >
            Recarregar página
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Auth Gate ─────────────────────────────────────────────────────────────────

function AuthGate({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null | undefined>(undefined);

  useEffect(() => {
    // Fallback: if Supabase takes too long, show login rather than blank screen
    const timeout = setTimeout(() => {
      setSession((prev) => (prev === undefined ? null : prev));
    }, 6000);

    supabase.auth
      .getSession()
      .then(({ data }) => {
        clearTimeout(timeout);
        setSession(data.session);
      })
      .catch(() => {
        clearTimeout(timeout);
        setSession(null);
      });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, s) => setSession(s));

    return () => {
      clearTimeout(timeout);
      subscription.unsubscribe();
    };
  }, []);

  if (session === undefined) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!session) return <Login />;
  return <>{children}</>;
}

// ── App ───────────────────────────────────────────────────────────────────────

const App = () => (
  <ErrorBoundary>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <AuthGate>
            <ErrorBoundary>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/logs" element={<ExecutionLogs />} />
                <Route path="/cobranca" element={<Cobranca />} />
                <Route path="/automation/new" element={<AutomationEditor />} />
                <Route path="/automation/:id" element={<AutomationEditor />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </ErrorBoundary>
          </AuthGate>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  </ErrorBoundary>
);

export default App;
