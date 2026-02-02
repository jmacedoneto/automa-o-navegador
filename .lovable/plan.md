

# Plano: Redesign Visual + Pagina de Configuracoes

## Resumo

O layout atual esta muito simples (preto e branco basico) e falta uma pagina centralizada para configurar as credenciais do Browserless. Este plano implementa:
1. **Novo design system** com cores vibrantes e modernas
2. **Pagina de Configuracoes** para URL e Token do Browserless (global)

---

## 1. Novo Design System

### Paleta de Cores (Tema Azul/Roxo Moderno)

O design atual usa cores neutras cinzas. Vamos adicionar uma paleta mais vibrante e profissional:

```text
Tema Claro:
- Primary: Azul vibrante (#3B82F6 / 217 91% 60%)
- Accent: Roxo (#8B5CF6 / 263 70% 66%)
- Background: Cinza claro com leve toque (#F8FAFC)
- Cards: Brancos com bordas suaves

Tema Escuro:
- Primary: Azul claro
- Background: Azul escuro profundo (#0F172A)
- Cards: Tons de slate
```

### Elementos Visuais Novos
- Gradientes sutis no header
- Icones coloridos (nao apenas cinza)
- Badges com cores por status (verde = sucesso, vermelho = erro, amarelo = pendente)
- Sombras mais pronunciadas nos cards
- Bordas com cores de destaque
- Animacoes suaves de hover

---

## 2. Pagina de Configuracoes

### Nova Rota: `/settings`

Pagina dedicada para configurar dados globais que se aplicam a todas as automacoes:

**Campos:**
- URL do Browserless (ex: `https://browserless.minha-vps.com`)
- Token de Autenticacao do Browserless
- Opcao de testar conexao

### Armazenamento

Nova tabela `settings` no banco de dados:
- `id`: UUID
- `key`: TEXT (chave unica, ex: "browserless_url", "browserless_token")
- `value`: TEXT (valor)
- `created_at`, `updated_at`

Ou alternativamente, uma unica linha com JSON estruturado.

---

## 3. Layout com Navegacao

### Header Fixo Melhorado
- Logo + Nome do sistema a esquerda
- Menu de navegacao (Dashboard | Configuracoes)
- Indicador de conexao Browserless (verde/vermelho)

### Estrutura
```text
+----------------------------------+
|  [Logo] Automacao ERP       [?]  |
|  Dashboard | Configuracoes       |
+----------------------------------+
|                                  |
|        Conteudo da Pagina        |
|                                  |
+----------------------------------+
```

---

## 4. Componentes Atualizados

### Dashboard
- Header com gradiente azul/roxo
- Cards com borda colorida a esquerda indicando status
- Badges coloridos (verde=ativo, cinza=inativo)
- Botoes com cores primarias vibrantes
- Estado vazio com ilustracao

### AutomationCard
- Borda esquerda colorida por status
- Icones com cores (verde check, vermelho X, amarelo clock)
- Hover com elevacao de sombra
- Gradiente sutil no fundo

### AutomationEditor
- Tabs com indicador colorido
- Cards com headers coloridos por secao
- Botao de IA com gradiente especial

---

## Detalhes Tecnicos

### Arquivos a Modificar

**src/index.css**
- Atualizar variaveis CSS com nova paleta
- Adicionar variaveis para success, warning, info

**tailwind.config.ts**
- Adicionar cores success, warning, info
- Adicionar animacoes extras

**Novos Arquivos**
- `src/pages/Settings.tsx` - Pagina de configuracoes
- `src/components/layout/Header.tsx` - Header reutilizavel
- `src/services/settingsService.ts` - CRUD para settings

**Arquivos Existentes a Atualizar**
- `src/App.tsx` - Adicionar rota /settings
- `src/pages/Dashboard.tsx` - Novo design
- `src/components/automation/AutomationCard.tsx` - Novo design
- `src/components/automation/AutomationList.tsx` - Novo design
- `src/pages/AutomationEditor.tsx` - Usar settings globais

### Migracao de Banco

```sql
CREATE TABLE public.settings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key TEXT UNIQUE NOT NULL,
  value TEXT,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Valores padrao
INSERT INTO settings (key, value, description) VALUES
  ('browserless_url', '', 'URL da instancia Browserless'),
  ('browserless_token', '', 'Token de autenticacao do Browserless');
```

---

## Fluxo de Uso

1. Usuario acessa o sistema pela primeira vez
2. Ve aviso no header "Configure seu Browserless"
3. Vai em Configuracoes
4. Preenche URL e Token
5. Clica em "Testar Conexao" (verifica se Browserless responde)
6. Salva
7. Agora pode criar automacoes que usam essas configuracoes globais

---

## Beneficios

- **Visual moderno**: Cores vibrantes e interface profissional
- **Configuracao centralizada**: URL e Token do Browserless em um so lugar
- **Reutilizacao**: Novas automacoes usam config global automaticamente
- **Feedback visual**: Cores indicam status de forma clara
- **Teste de conexao**: Valida se Browserless esta acessivel

