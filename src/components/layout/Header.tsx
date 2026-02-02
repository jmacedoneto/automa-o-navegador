import { forwardRef } from "react";
import { Link, useLocation } from "react-router-dom";
import { Bot, Settings, LayoutDashboard, Wifi, WifiOff, History } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useEffect, useState } from "react";
import { getBrowserlessSettings, testBrowserlessConnection } from "@/services/settingsService";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export const Header = forwardRef<HTMLElement, object>(function Header(_props, ref) {
  const location = useLocation();
  const [isConnected, setIsConnected] = useState<boolean | null>(null);
  const [isChecking, setIsChecking] = useState(false);

  useEffect(() => {
    checkConnection();
  }, [location.pathname]);

  const checkConnection = async () => {
    setIsChecking(true);
    try {
      const settings = await getBrowserlessSettings();
      if (settings.url) {
        const connected = await testBrowserlessConnection(settings.url, settings.token);
        setIsConnected(connected);
      } else {
        setIsConnected(null);
      }
    } catch {
      setIsConnected(false);
    } finally {
      setIsChecking(false);
    }
  };

  const isActive = (path: string) => location.pathname === path;

  return (
    <header ref={ref} className="sticky top-0 z-50 w-full border-b bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/60">
      <div className="container flex h-16 items-center justify-between">
        {/* Logo e Nome */}
        <Link to="/" className="flex items-center gap-3 transition-opacity hover:opacity-80">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl gradient-primary">
            <Bot className="h-6 w-6 text-primary-foreground" />
          </div>
          <div className="hidden sm:block">
            <h1 className="font-bold text-lg text-gradient-primary">Automação ERP</h1>
            <p className="text-xs text-muted-foreground">Browserless + IA</p>
          </div>
        </Link>

        {/* Navegação Central */}
        <nav className="flex items-center gap-1">
          <Button
            variant={isActive("/") ? "secondary" : "ghost"}
            size="sm"
            asChild
            className={cn(
              "gap-2",
              isActive("/") && "bg-primary/10 text-primary"
            )}
          >
            <Link to="/">
              <LayoutDashboard className="h-4 w-4" />
              <span className="hidden sm:inline">Dashboard</span>
            </Link>
          </Button>
          <Button
            variant={isActive("/logs") ? "secondary" : "ghost"}
            size="sm"
            asChild
            className={cn(
              "gap-2",
              isActive("/logs") && "bg-primary/10 text-primary"
            )}
          >
            <Link to="/logs">
              <History className="h-4 w-4" />
              <span className="hidden sm:inline">Logs</span>
            </Link>
          </Button>
          <Button
            variant={isActive("/settings") ? "secondary" : "ghost"}
            size="sm"
            asChild
            className={cn(
              "gap-2",
              isActive("/settings") && "bg-primary/10 text-primary"
            )}
          >
            <Link to="/settings">
              <Settings className="h-4 w-4" />
              <span className="hidden sm:inline">Configurações</span>
            </Link>
          </Button>
        </nav>

        {/* Status de Conexão */}
        <Tooltip>
          <TooltipTrigger asChild>
            <div
              className={cn(
                "flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
                isConnected === true && "bg-success/10 text-success",
                isConnected === false && "bg-destructive/10 text-destructive",
                isConnected === null && "bg-warning/10 text-warning"
              )}
            >
              {isChecking ? (
                <div className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
              ) : isConnected === true ? (
                <Wifi className="h-3 w-3" />
              ) : isConnected === false ? (
                <WifiOff className="h-3 w-3" />
              ) : (
                <WifiOff className="h-3 w-3" />
              )}
              <span className="hidden md:inline">
                {isConnected === true
                  ? "Conectado"
                  : isConnected === false
                  ? "Desconectado"
                  : "Não configurado"}
              </span>
            </div>
          </TooltipTrigger>
          <TooltipContent>
            {isConnected === true
              ? "Browserless está acessível"
              : isConnected === false
              ? "Não foi possível conectar ao Browserless"
              : "Configure a URL do Browserless nas configurações"}
          </TooltipContent>
        </Tooltip>
      </div>
    </header>
  );
});
