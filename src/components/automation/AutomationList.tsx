import { useState } from "react";
import { Automation } from "@/types/automation";
import { AutomationCard } from "./AutomationCard";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, Filter, Plus, Bot, Sparkles } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Skeleton } from "@/components/ui/skeleton";

interface AutomationListProps {
  automations: Automation[];
  isLoading: boolean;
  onDelete: (id: string) => void;
  onToggleStatus: (id: string, isActive: boolean) => void;
  onExecute: (id: string, withLivePreview?: boolean) => void;
}

type FilterStatus = 'all' | 'active' | 'inactive';

export function AutomationList({ 
  automations, 
  isLoading,
  onDelete, 
  onToggleStatus, 
  onExecute 
}: AutomationListProps) {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all');

  const filteredAutomations = automations.filter((automation) => {
    const matchesSearch = 
      automation.name.toLowerCase().includes(search.toLowerCase()) ||
      automation.description?.toLowerCase().includes(search.toLowerCase());
    
    const matchesFilter = 
      filterStatus === 'all' ||
      (filterStatus === 'active' && automation.is_active) ||
      (filterStatus === 'inactive' && !automation.is_active);

    return matchesSearch && matchesFilter;
  });

  const handleEdit = (id: string) => {
    navigate(`/automation/${id}`);
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex gap-4">
          <Skeleton className="h-10 flex-1 max-w-sm" />
          <Skeleton className="h-10 w-32" />
          <Skeleton className="h-10 w-40" />
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-56 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header com busca e filtros */}
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        <div className="flex flex-1 gap-2 w-full sm:w-auto">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Buscar automações..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 bg-card"
            />
          </div>
          <Select value={filterStatus} onValueChange={(v) => setFilterStatus(v as FilterStatus)}>
            <SelectTrigger className="w-36 bg-card">
              <Filter className="h-4 w-4 mr-2 text-muted-foreground" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas</SelectItem>
              <SelectItem value="active">Ativas</SelectItem>
              <SelectItem value="inactive">Inativas</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button 
          onClick={() => navigate('/automation/new')}
          className="gap-2 gradient-primary text-primary-foreground shadow-lg shadow-primary/25 hover:shadow-primary/40 transition-shadow"
        >
          <Plus className="h-4 w-4" />
          Nova Automação
        </Button>
      </div>

      {/* Lista de automações */}
      {filteredAutomations.length === 0 ? (
        <div className="text-center py-16 px-4">
          <div className="inline-flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-primary/20 to-accent/20 mb-6">
            <Bot className="h-10 w-10 text-primary" />
          </div>
          <h3 className="text-xl font-semibold">Nenhuma automação encontrada</h3>
          <p className="text-muted-foreground mt-2 max-w-md mx-auto">
            {search || filterStatus !== 'all' 
              ? "Tente ajustar os filtros de busca"
              : "Crie sua primeira automação para começar a extrair dados do seu ERP automaticamente"
            }
          </p>
          {!search && filterStatus === 'all' && (
            <Button 
              className="mt-6 gap-2 gradient-primary text-primary-foreground shadow-lg shadow-primary/25"
              onClick={() => navigate('/automation/new')}
            >
              <Sparkles className="h-4 w-4" />
              Criar Primeira Automação
            </Button>
          )}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredAutomations.map((automation) => (
            <AutomationCard
              key={automation.id}
              automation={automation}
              onEdit={handleEdit}
              onDelete={onDelete}
              onToggleStatus={onToggleStatus}
              onExecute={onExecute}
            />
          ))}
        </div>
      )}
    </div>
  );
}
