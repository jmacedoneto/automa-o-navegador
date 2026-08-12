# Design: NavRunner — Framework de Automações de Navegador

**Data:** 2026-08-12
**Status:** Aprovado pelo usuário (5/5 seções)

---

## Contexto e problema

O `autonavegador` (stack em `apvsiguatemi.net/navegador`) já roda, mas:

1. **Autoria de automações é fricção alta.** Cada novo fluxo exige escrever Python imperativo (ex: `cotacao_pvs/automacao_cotacao.py`, 544 linhas).
2. **Debugging é manual.** Quando algo falha no meio, abre logs, abre `fix_*.py`, roda de novo até funcionar — "uma novela" (palavras do usuário).
3. **Não existe captura de "como o usuário faz".** Toda automation nasce codificada; o conhecimento tá na cabeça de quem usou manualmente.
4. **IA só é usada pra planejar, não dentro do run.** O agent gera steps iniciais mas não ajuda a extrair dados estruturados durante a execução.

A `cotacao_pvs` é o caso de teste oficial: hoje é 544 linhas Python que faz login no `app.apvs.vc` e preenche 7-8 telas com loops sobre FAIXAS/REGIÕES/TIPOS de veículo. Tabela FIPE + autenticação quebradiça ilustram todos os 4 problemas acima.

**Objetivo:** construir um framework declarativo, observável e IA-nativo dentro do `autonavegador`, validado pela `cotacao_pvs` em 2-3 semanas, e que reduza a fricção de criar/debugar futuras automações em ~80%.

---

## Decisões de design (consolidadas das 5 seções)

| Dimensão | Decisão |
|---|---|
| **Escopo** | Framework reutilizável, com `cotacao_pvs` como piloto de validação |
| **Autoria** | Híbrida — JSON declarativo + blocos `run_python` quando necessário |
| **Falha** | Retry declarativo por step, com `on_fail` configurável |
| **Entrada de dados** | Híbrida — aceita inputs pré-extraídos + tem steps nativos de extração (incl. `run_ai`) |
| **Runtime** | Playwright Python dentro do `autonavegador_autopilot_worker` existente, conectando ao `autopilot_browser` (Browserless) via CDP |

---

## Arquitetura

```
┌──────────────────────────────────────────────────────────────┐
│  Camada de Autoria                                           │
│  ┌──────────────────┐  ┌─────────────────┐  ┌────────────┐   │
│  │ Chrome Extension │  │ Editor JSON/Web │  │ AI Planner │   │
│  │ (NavRecorder)    │  │ (painel /nav.)  │  │ (GPT-5)    │   │
│  └────────┬─────────┘  └────────┬────────┘  └─────┬──────┘   │
│           └──────────────┬─────┘                  │          │
│                          ▼                         │          │
│                ┌─────────────────────┐             │          │
│                │ steps.json canônico │◀────────────┘          │
│                └──────────┬──────────┘                        │
└───────────────────────────┼──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  Runtime — dENTRO de autonavegador_autopilot_worker          │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ NavRunner.run(automation_id, inputs)                 │    │
│  │  ├─ load steps.json + resolver credenciais           │    │
│  │  ├─ para cada step:                                  │    │
│  │  │   executa via Playwright (Browserless via CDP)    │    │
│  │  │   aplica retry declarativo, captura screenshot    │    │
│  │  │   emite span no Langfuse                          │    │
│  │  └─ post-hooks: outputs (webhook/whatsapp/sheets)    │    │
│  └──────────────────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ Step Interpreter (DSL → Playwright commands)         │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  Storage / Observability / Delivery (já existente)           │
│  Supabase   — automation_versions, automation_runs, steps    │
│  Langfuse   — traces por run + por step                     │
│  MinIO      — screenshots + arquivos extraídos              │
│  Evolution  — alertas WhatsApp em falha                     │
│  N8N        — webhooks externos                             │
│  Browserless — pool de browsers (CDP endpoint)              │
└──────────────────────────────────────────────────────────────┘
```

**Nada disso exige container novo.** O worker atual (Celery + Redis + rede Deltanet) já fala com tudo. Só ganha Playwright e novos módulos Python.

---

## Estrutura de arquivos proposta

```
backend/
├── app/automation/                # NOVO módulo
│   ├── __init__.py
│   ├── runner.py                  # executor principal
│   ├── interpreter.py             # DSL → Playwright
│   ├── steps/                     # catálogo de steps nativos
│   │   ├── navigation.py          # goto, reload, wait_for, ...
│   │   ├── interaction.py         # click, fill, select, ...
│   │   ├── assertion.py           # assert_text, assert_visible, ...
│   │   ├── extraction.py          # extract_text, extract_table, screenshot
│   │   ├── ai.py                  # run_ai (tool-calling + schema)
│   │   └── control.py             # if, for_each, block
│   ├── retry.py                   # lógica declarativa
│   ├── schemas/                   # Pydantic models nomeados
│   │   └── resultado_cotacao.py
│   ├── credentials.py             # resolve {{cfg.*}} / {{vault.*}}
│   ├── bindings.py                # runtime de bindings
│   ├── recorder.py                # Playwright trace → steps.json
│   ├── alerts.py                  # WhatsApp via Evolution
│   ├── ui/                        # rotas FastAPI
│   │   ├── routes_runs.py
│   │   └── routes_versions.py
│   └── langfuse_trace.py          # helpers de tracing
├── app/workers/
│   └── tasks.py                   # já tem run_automation; ganha navrunner wrapper
└── tests/
    └── automation/                # testes do runner + DSL
```

```
chrome-extension-v2/               # NOVA extensão (ou rebranding)
├── manifest.json
├── recorder/                      # captura interações
└── exporter/                      # exporta .trace.json
```

```
chrome-extension/                  # já existe (talvez reaproveitar base)
```

---

## DSL canônico (`steps.json`)

### Catálogo de steps

| Categoria | Step | Exemplo |
|---|---|---|
| **Navegação** | `goto` | `{"goto": "https://app.apvs.vc/cotacao"}` |
| | `reload`, `go_back` | `{"reload": true}` |
| | `wait_for` | `{"wait_for": {"selector": ".dash", "timeout_ms": 15000}}` |
| | `wait_for_url`, `wait_for_response`, `sleep` | |
| **Interação** | `click` | `{"click": {"selector": "button#cotar"}}` |
| | `fill` | `{"fill": {"#nome": "{{input.nome}}"}}` |
| | `select`, `check`, `upload`, `hover`, `scroll`, `keyboard` | |
| **Asserts** | `assert` | `{"assert": {"text": "Salvo", "timeout_ms": 5000}}` |
| | `assert_visible`, `assert_url`, `assert_no_errors` | |
| **Extração** | `extract_text`, `extract_attr`, `extract_table`, `screenshot` | `{"extract_text": {"selector": ".valor", "bind": "valor"}}` |
| **IA** | `run_ai` | `{"run_ai": {"schema": "ResultadoCotacao", "bind": "resultado"}}` |
| **Code** | `run_python` | `{"run_python": "...", "bind": "x", "timeout_ms": 30000}` |
| **Controle** | `for_each`, `block`, `if` | `{"for_each": {"items": "{{faixas}}", "as": "faixa", "steps": [...]}}` |
| **Retry / hooks** | `retry`, `pre_hook`, `post_hook` | `{"retry": {"attempts": 3, "on_fail": "alert"}}` |

### Interpolação e bindings

- `{{input.*}}` — entrada da execução
- `{{resultado.*}}` ou `{{<bind>.*}}` — extraído por step anterior
- `{{cfg.*}}` — settings globais (Supabase `settings` table)
- `{{vault.*}}` — passar pelo agents vault (futuro)
- `{{env.*}}` — env vars do worker

Bindings são explícitos (`"bind": "resultado"`). Sem efeito colateral implícito.

### `auth` block (formato)

Top-level no `steps.json`. Runner trata como pré-requisito implícito antes do primeiro step explícito:

```json
"auth": {
  "type": "form_login",
  "url": "https://app.apvs.vc/login",
  "credentials_ref": "app_login",
  "selectors": {
    "user": "#cnpj",
    "pass": "#senha",
    "submit": "button[type=submit]"
  },
  "success_assert": { "selector": ".dashboard", "timeout_ms": 15000 }
}
```

**Tipos suportados em P0:** `form_login` (HTML form). P5 adiciona `cookie_reuse` e `otp_via_telegram`.

`success_assert` é mandatório — runner considera login ok quando o assert passa. Se `auth` falha após retries, run morre imediatamente com `error_category=auth_failure` (alerta prioritário).

### Controle: `for_each`

```json
{
  "for_each": {
    "items": "{{faixas}}",
    "as": "faixa",
    "steps": [
      { "id": "preencher", "fill": { "#valor": "{{faixa.inicio}}" } },
      { "id": "submeter", "click": { "selector": "button#cotar" } },
      { "id": "capturar", "extract_text": { "selector": ".resultado", "bind": "resultado_{{ loop.index }}" } }
    ],
    "max_iterations": 100,
    "on_iteration_fail": "continue | abort"
  }
}
```

- `{{ loop.index }}` disponível dentro do body (1-based).
- `max_iterations` cortafogo de segurança (default 50).
- Bindings criados dentro do loop viram lista (`bindings["resultado"]` = `[r1, r2, ...]`).

### Controle: `if` (mínimo)

```json
{
  "if": {
    "condition": "{{input.tipo}} == 'carros'",
    "then_steps": [...],
    "else_steps": [...]
  }
}
```

Operadores: `==`, `!=`, `<`, `>`, `in`, `and`, `or`. Literais numéricos/strings. Sem comparação de objetos. Pra lógica complexa → `run_python`.

### Versionamento

- `"version": 1` no root. Quebra de schema = bump major.
- Cada save gera nova linha em `automation_versions` (não destrutivo).
- Execução sempre referencia uma versão específica (não "latest").

### Anti-escopo do DSL

- Sem lógica condicional complexa no nível raiz → `run_python` ou `for_each`.
- Sem tipagem forte obrigatória — schema é validado pela IA quando preenche.
- Não tenta ser linguagem de programação.

---

## Retry declarativo

```json
"retry": {
  "attempts": 3,
  "backoff": "linear | exponential | fixed",
  "initial_delay_ms": 1000,
  "max_delay_ms": 30000,
  "on_fail": "abort | skip_continue | alert | run_block:<id>",
  "retry_if": "selector_missing | timeout | any_error"
}
```

`on_fail`:

| Valor | Comportamento |
|---|---|
| `abort` (default) | Para pipeline, dispara alerta |
| `skip_continue` | Marca como `failed`, segue próximo step |
| `alert` | Como `abort` + WhatsApp prioritário |
| `run_block:<id>` | Executa block de recovery e tenta novamente |

---

## Credenciais

Resolução por `auth.credentials_ref` no `steps.json`:

1. `cfg.<name>` — settings Supabase (já existe)
2. `vault.<name>` — agents vault via REST (futuro)
3. `secret_ref.<name>` — Docker secret (raro)

**Nunca literal no `steps.json`.** Sempre `{{cfg.app_login.user}}`. Redact automático no trace Langfuse.

---

## IA inline (`run_ai`)

```json
{
  "id": "extrair_resultado",
  "run_ai": {
    "schema": "ResultadoCotacao",
    "instruction": "extraia valor_total, prazo_meses, status",
    "max_tokens": 800,
    "bind": "resultado"
  }
}
```

Schema Pydantic único por nome em `app/automation/schemas/`:

```python
class ResultadoCotacao(BaseModel):
    valor_total: float
    prazo_meses: int
    status: Literal["ok", "rejeitado", "revisao"]
    motivo_rejeicao: str | None = None
```

Fluxo:

1. Runner pega `page.content()` ou `page.accessibility.snapshot()` (escolha por tamanho).
2. Redact automático: `type=password`, atributos `data-secret`, regex configurável.
3. Chama OpenAI com `tool_choice` forçado contra schema.
4. Pydantic valida output. `ValidationError` → retry com mensagem do erro.
5. Sucesso → expõe como `{{resultado.*}}`.

---

## Observabilidade (3 pilares)

### Pilar 1 — Langfuse: traces por step

Cada step emite span. Hierarchy:

```
cotacao_pvs run #4821        (root)
├─ step:abrir_form           (input, output, latency, attempt)
├─ step:esperar_form
├─ step:preencher_dados
│   └─ run_ai:extract_via_ai (OpenAI call — langfuse auto-traced)
├─ step:escolher_tipo
│   ├─ attempt 1 (failed, 2s)
│   └─ attempt 2 (ok, 1.4s)
└─ step:extrair_resultado
```

User acessa `langfuse.apvsiguatemi.net` e navega a timeline completa.

### Pilar 2 — MinIO + Supabase: screenshots e logs

Screenshots em MinIO:

```
s3.apvsiguatemi.net/automation-screenshots/{run_id}/{step_id}_before.png
s3.apvsiguatemi.net/automation-screenshots/{run_id}/{step_id}_after.png
s3.apvsiguatemi.net/automation-screenshots/{run_id}/{step_id}_on_fail.png  (sempre em falha)
```

Tabelas Supabase:

```sql
automation_versions (
  id uuid pk,
  automation_id uuid fk,
  version int,
  steps jsonb,
  inputs_schema text,
  created_at timestamptz,
  created_by text,
  unique(automation_id, version)
);

automation_runs (
  id uuid pk,
  automation_id uuid fk,
  version_id uuid fk,
  status text,         -- pending | running | success | failed | partial
  started_at timestamptz,
  finished_at timestamptz,
  inputs jsonb,
  bindings jsonb,
  error_message text,
  trace_id text        -- Langfuse
);

automation_steps_log (
  id uuid pk,
  run_id uuid fk,
  step_id text,
  attempt int,
  status text,         -- ok | failed | skipped
  started_at timestamptz,
  finished_at timestamptz,
  error text,
  screenshots jsonb,   -- urls MinIO
  bindings jsonb
);
```

### Pilar 3 — Evolution API: alertas WhatsApp

Quando `status=failed`, runner chama Evolution (se configurado):

```
❌ cotacao_pvs #4821 falhou em `extrair_resultado` (tentativa 3/3).

URL: https://navegador.apvsiguatemi.net/runs/4821
Screenshot: https://s3.apvsiguatemi.net/.../extrair_resultado_on_fail.png
Trace: https://langfuse.apvsiguatemi.net/trace/{id}
Ação: "Re-rodar deste step" no painel.
```

Se Evolution não configurado: fallback pra webhook genérico.

### Painel web — `runs/{id}`

- Timeline vertical: cada step com ícone de status.
- Click em step → screenshot inline + bindings + erro + botão "Re-rodar deste step".
- Botão "Re-rodar tudo" cria novo run.

---

## Record-replay (autoria zero-ceremony)

**Pipeline:**

```
Usuário abre app.apvs.vc manualmente (1x)
       │
       ▼
Extensão Chrome "NavRecorder" gravando
  └─ exporta .trace.json (formato Playwright Tracer)
       │
       ▼
recorder.py:
  ├─ parse trace + heurísticas:
  │   • form com password  →  sugere block auth
  │   • submit final       →  sugere assert
  │   • tabela HTML        →  sugere extract_table
  │   • padrão de loop     →  sugere for_each
  ├─ prompt pra GPT: "gere steps.json mínimo"
  └─ salva versão draft em automation_versions
       │
       ▼
Painel web: diff lado-a-lado trace ↔ steps.json gerado
       │
       ▼
Usuário revisa (5 min), ajusta credenciais/inputs/outputs, publica
```

**Estado inicial:** estender `chrome-extension-v2/` (já existe como base).

---

## Reúso do que já existe (nada de novo)

| Componente | Como o NavRunner usa |
|---|---|
| `autonavegador_autopilot_worker` (Celery + Redis) | Hospeda o runner |
| `autonavegador_autopilot_browser` (Browserless) | CDP endpoint pra Playwright |
| `supabase.apvsiguatemi.net` | Tabelas novas |
| `langfuse.apvsiguatemi.net` | Tracing |
| `s3.apvsiguatemi.net` (MinIO) | Screenshots |
| `evolution.suavps.com` (quando configurado) | Alertas WhatsApp |
| `n8n.apvsiguatemi.net` | Webhooks externos |
| `chrome-extension-v2/` | Base da extensão |

---

## Faseamento

| Fase | Duração | Entrega | Critério de done |
|---|---|---|---|
| **P0** Skeleton | 3-4 dias | `app/automation/` (runner, interpreter, 5 steps, retry, screenshot); cotação roda como legado | Hello World `steps.json` end-to-end |
| **P1** Cotação migrada | 4-5 dias | `cotacao_pvs` em DSL; retry + screenshot + trace | Run end-to-end da cotação via NavRunner, 0 intervenção |
| **P2** IA + outputs | 3-4 dias | `run_ai`, `extract_table`, outputs WhatsApp+Sheets | Alerta WhatsApp chega em falha simulada |
| **P3** Record-replay | 5-7 dias | Extensão + recorder.py + painel "gravar" | Gravar nova automation end-to-end funciona |
| **P4** Painel de runs | 3-4 dias | UI `runs/{id}` com timeline + screenshot inline + "re-rodar deste step" | User usa painel pra diagnosticar, não terminal |
| **P5** Hardening | contínuo | Login MFA, retry strategy pra auth expiry, alertas Slack, dashboard de saúde | — |

**Total P0+P1+P2 = ~2 semanas.** Sucesso de P2 = framework validado pela cotação.

---

## Casos de teste oficiais

A cada fase, a cotação é o teste de aceitação:

- **P0 done:** runner executa `steps.json` mínimo (login + click + assert) em Browserless.
- **P1 done:** cotação inteira (login + 7-8 telas + extração) roda via NavRunner. 0 erros de seletor. Retry cuida de 1 falha intermitente simulada.
- **P2 done:** quebra simulada num `run_ai` → alerta WhatsApp chega com link pra tela do run com screenshot da falha.
- **P3 done:** gravar nova automation X (ex: baixar tabela do IPE) funciona e roda depois autonomamente.
- **P4 done:** painel diagnostica run com falha em 3 cliques.

---

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Playwright dentro do worker estoura memória | Conectar via CDP ao Browserless (sem Chromium local); bump memory limit pra 4GB; `--shm-size=512m` |
| Login com MFA/bloqueio por IP | `auth` strategy expansível (cookie reuse, OTP via Telegram, etc.); P5 |
| Seletor CSS muda na UI | Recorder permite re-gravar; `run_ai` extrai semanticamente quando seletor falha |
| IA extrai dado errado | Pydantic schema valida; valor suspeito vira `confidence` baixo + alerta |
| Operação em escala (50+ runs/dia) | Browserless escala horizontal; Celery já tem Redis; Painel filtra por status |

---

## Out of scope (não-objetivos)

- Construção de novo serviço Swarm dedicado. (Run dentro do worker existente.)
- Multi-tenancy/RLS por organização. (Hoje tudo é single-tenant Macedo.)
- Editor visual drag-and-drop de steps. (JSON + painel web já basta.)
- Marketplace de automações. (Single-user.)
- Suporte a apps mobile. (Apenas desktop Chromium.)
