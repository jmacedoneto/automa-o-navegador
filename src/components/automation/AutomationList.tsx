import { useState } from "react";
import { Automation } from "@/types/automation";
import { AutomationCard } from "./AutomationCard";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, Filter, Plus, Bot } from "lucide-react";
import { useNavigate } from "react-router-dom";

interface AutomationListProps {
  automations: Automation[];
  isLoading: boolean;
  onDelete: (id: string) => void;
  onToggleStatus: (id: string, isActive: boolean) => void;
  onExecute: (id: string) => void;
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
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-48 rounded-lg bg-muted animate-pulse" />
        ))}
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
              className="pl-9"
            />
          </div>
          <Select value={filterStatus} onValueChange={(v) => setFilterStatus(v as FilterStatus)}>
            <SelectTrigger className="w-32">
              <Filter className="h-4 w-4 mr-2" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas</SelectItem>
              <SelectItem value="active">Ativas</SelectItem>
              <SelectItem value="inactive">Inativas</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button onClick={() => navigate('/automation/new')}>
          <Plus className="h-4 w-4 mr-2" />
          Nova Automação
        </Button>
      </div>

      {/* Lista de automações */}
      {filteredAutomations.length === 0 ? (
        <div className="text-center py-12">
          <Bot className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-medium">Nenhuma automação encontrada</h3>
          <p className="text-muted-foreground mt-1">
            {search || filterStatus !== 'all' 
              ? "Tente ajustar os filtros"
              : "Crie sua primeira automação para começar"
            }
          </p>
          {!search && filterStatus === 'all' && (
            <Button className="mt-4" onClick={() => navigate('/automation/new')}>
              <Plus className="h-4 w-4 mr-2" />
              Criar Automação
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
