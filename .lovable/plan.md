
# Plano: Corrigir Bug de Navegação "Nova Automação"

## Problema Identificado

Quando o usuário clica em "Nova Automação", a tela fica carregando infinitamente.

### Causa Raiz

No arquivo `src/App.tsx`, existem duas rotas conflitantes:

```typescript
<Route path="/automation/new" element={<AutomationEditor />} />
<Route path="/automation/:id" element={<AutomationEditor />} />
```

Quando o usuário acessa `/automation/new`:
- A **primeira rota** (path exato) é correspondida
- O parâmetro `id` do `useParams()` fica **undefined** (não há `:id` nessa rota)
- No `AutomationEditor`, a verificação `id === 'new'` retorna **false**
- `isLoading` começa como **true** (pois `!isNew` = `!false` = `true`)
- O componente tenta carregar uma automação com `id = undefined`, que falha
- A tela fica presa no estado de carregamento

### Solução

Corrigir a lógica de verificação em `AutomationEditor.tsx`:

```typescript
// Antes (incorreto)
const isNew = id === 'new';

// Depois (correto)
const isNew = !id;  // Se não há id, é uma nova automação
```

Ou alternativamente, remover a rota duplicada e usar apenas a rota com parâmetro:

```typescript
// Apenas uma rota
<Route path="/automation/:id" element={<AutomationEditor />} />
```

E atualizar a navegação para usar `/automation/new` (onde `id` seria `'new'`).

---

## Arquivos a Modificar

### 1. src/pages/AutomationEditor.tsx

**Alteração na linha 35:**

```typescript
// Antes
const isNew = id === 'new';

// Depois  
const isNew = !id || id === 'new';
```

Isso cobre ambos os casos:
- Quando `id` é `undefined` (rota `/automation/new`)
- Quando `id` é `'new'` (rota `/automation/:id` com valor `new`)

---

## Correções Adicionais (Warnings React)

Os warnings de "Function components cannot be given refs" são causados por componentes que não usam `forwardRef`. Embora não bloqueiem a funcionalidade, devem ser corrigidos:

### 2. src/pages/AutomationEditor.tsx

Converter para `forwardRef`:

```typescript
import { forwardRef } from "react";

const AutomationEditor = forwardRef<HTMLDivElement>((props, ref) => {
  // ... código existente
});

export default AutomationEditor;
```

### 3. src/components/layout/Header.tsx

```typescript
import { forwardRef } from "react";

export const Header = forwardRef<HTMLElement>((props, ref) => {
  // ... código existente, adicionar ref ao <header>
});
```

### 4. src/pages/Dashboard.tsx

```typescript
import { forwardRef } from "react";

const Dashboard = forwardRef<HTMLDivElement>((props, ref) => {
  // ... código existente
});

export default Dashboard;
```

### 5. src/pages/Settings.tsx

```typescript
import { forwardRef } from "react";

const Settings = forwardRef<HTMLDivElement>((props, ref) => {
  // ... código existente
});

export default Settings;
```

---

## Resumo das Alterações

| Arquivo | Tipo | Descrição |
|---------|------|-----------|
| `AutomationEditor.tsx` | Correção Crítica | Ajustar lógica de `isNew` para aceitar `undefined` |
| `AutomationEditor.tsx` | Melhoria | Adicionar `forwardRef` |
| `Header.tsx` | Melhoria | Adicionar `forwardRef` |
| `Dashboard.tsx` | Melhoria | Adicionar `forwardRef` |
| `Settings.tsx` | Melhoria | Adicionar `forwardRef` |

---

## Resultado Esperado

Após a correção:
1. Clicar em "Nova Automação" abrirá imediatamente o editor em branco
2. Não haverá mais loading infinito
3. Os warnings de `forwardRef` desaparecerão do console
4. A navegação entre páginas funcionará corretamente
