# /auditoria — Auditoria Completa do AutoPilot

Você é um engenheiro de QA sênior fazendo uma auditoria completa do sistema AutoPilot. Execute as etapas abaixo **em sequência**, sem pular nenhuma.

## FASE 1 — Leitura e mapeamento do sistema

Leia os seguintes arquivos para entender o estado atual do sistema:

**Backend:**
- `backend/main.py`
- `backend/app/api/routes/automations.py`
- `backend/app/api/routes/executions.py`
- `backend/app/api/routes/schedules.py`
- `backend/app/api/routes/ai.py`
- `backend/app/api/routes/settings.py`
- `backend/app/models/schemas.py`
- `backend/app/workers/tasks.py`
- `backend/app/services/browser_executor.py`
- `backend/app/core/database.py`
- `backend/app/core/config.py`

**Frontend:**
- `src/services/automationService.ts`
- `src/services/executionService.ts`
- `src/services/api.ts`
- `src/types/automation.ts`
- `src/pages/Dashboard.tsx`
- `src/pages/AutomationEditor.tsx`
- `src/pages/ExecutionLogs.tsx`
- `src/pages/Settings.tsx`

## FASE 2 — Auditoria do banco de dados

Execute via `mcp__supabase-db__execute_sql`:

1. Liste todas as tabelas: `SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';`
2. Para cada tabela encontrada, descreva as colunas com tipos e constraints
3. Compare as colunas com os schemas Pydantic do backend e os tipos TypeScript do frontend
4. Identifique: colunas faltando, tipos incompatíveis, constraints problemáticas

## FASE 3 — Testes funcionais de cada endpoint

Use `Bash` com `curl` para testar cada endpoint de `https://navegador.apvsiguatemi.net/api/`:

### Automações
- `GET /api/automations` — lista todas
- `POST /api/automations` — cria uma automação de teste com nome `"__audit_test__"` e steps `[{"type":"navigate","url":"https://example.com"}]`
- `GET /api/automations/{id}` — busca por ID
- `PUT /api/automations/{id}` — atualiza
- `POST /api/automations/{id}/execute` — enfileira execução (background)
- `POST /api/automations/{id}/execute` com `{"withLivePreview": true}` — verifica se retorna `liveUrl` e `execution_id`
- `DELETE /api/automations/{id}` — apaga ao final

### Execuções
- `GET /api/executions` — lista logs
- `GET /api/executions?automation_id={id}` — filtra por automação

### Agendamentos
- `POST /api/schedules` — cria agendamento diário
- `GET /api/schedules?automation_id={id}` — lista agendamentos
- `DELETE /api/schedules/{id}` — apaga

### IA
- `POST /api/ai/generate-steps` — testa geração de passos (sem OpenAI key é esperado erro 4xx, não 5xx)

### Settings
- `GET /api/settings` — lista configurações

## FASE 4 — Cruzamento de cenários críticos

Teste os seguintes fluxos completos:

1. **Fluxo completo de criação e execução:**
   - Cria automação → Executa em background → Verifica que log foi criado com status `pending` ou `running` → Verifica que `task_id` veio na resposta → Aguarda 5s → Verifica se log mudou de status

2. **Fluxo live preview:**
   - Cria automação → Executa com `withLivePreview: true` → Verifica `liveUrl` e `execution_id` na resposta → Verifica acesso à URL do devtools: `curl -s -o /dev/null -w "%{http_code}" "{liveUrl}"`

3. **Fluxo de credenciais:**
   - Cria automação com `credentials: {username: "test", password: "test"}` → Verifica que foi salvo e retornado corretamente

4. **Fluxo de outputs:**
   - Cria automação com `outputs: [{type:"webhook", url:"https://httpbin.org/post"}]` → Verifica que foi salvo

5. **Fluxo de agendamento:**
   - Cria automação → Cria agendamento do tipo `interval` com 60 min → Verifica que foi salvo → Pausa → Verifica `is_active: false`

6. **Erro proposital — automação inexistente:**
   - `GET /api/automations/00000000-0000-0000-0000-000000000000` → deve retornar 404, não 500

7. **Erro proposital — payload inválido:**
   - `POST /api/automations` sem `name` → deve retornar 422, não 500

## FASE 5 — Análise de erros potenciais futuros

Para cada problema encontrado, classifique como:
- 🔴 **CRÍTICO** — quebra funcionalidade principal
- 🟡 **MÉDIO** — pode causar problema em cenário específico
- 🟢 **MELHORIA** — não quebra, mas pode ser melhorado

Analise também os seguintes riscos potenciais no código:
1. O worker Celery usa `maybe_single()` em `tasks.py` — pode quebrar em versões futuras do postgrest-py
2. A execução do browser via Playwright não tem timeout global — pode rodar indefinidamente
3. O `execute_automation` no `automations.py` aceita `payload: dict = {}` — FastAPI não valida o body
4. A entrega de outputs falha silenciosamente (só printa, não registra no log)
5. Sessões do Supabase Realtime no frontend não são limpas em todos os casos de erro
6. O `AuthGate` em `App.tsx` mostra `null` durante loading — pode piscar na tela

## FASE 6 — Geração do relatório

Gere um relatório estruturado no seguinte formato:

```
# Relatório de Auditoria AutoPilot
Data: {data atual}

## Resumo Executivo
{X críticos | Y médios | Z melhorias}

## Problemas Encontrados

### 🔴 CRÍTICOS
1. [título]
   - Onde: arquivo:linha
   - O que acontece: ...
   - Reprodução: curl ...
   - Fix necessário: ...

### 🟡 MÉDIOS
...

### 🟢 MELHORIAS
...

## Resultados dos Testes
| Endpoint | Status | Observação |
|---|---|---|
| GET /api/automations | ✅ 200 | ... |
| ... | ... | ... |

## Schema DB vs Código
| Tabela | Campo | DB | Código | Status |
|---|---|---|---|---|
```

## FASE 7 — Reparos automáticos

Para cada item 🔴 CRÍTICO e 🟡 MÉDIO encontrado:
1. Anuncie o reparo que vai fazer
2. Edite o arquivo afetado
3. Confirme o reparo

Para reparos que requerem mudanças no banco (ADD COLUMN, ALTER TABLE), use `mcp__supabase-db__execute_sql`.

Ao final, faça rebuild e redeploy via Portainer API:
```bash
# Build
tar -czf /tmp/autopilot-build.tar.gz --exclude=node_modules --exclude=dist --exclude=.git .
curl -s -X POST "https://portainer.apvsiguatemi.net/api/endpoints/1/docker/build?t=autopilot:latest&dockerfile=Dockerfile" \
  -H "X-API-Key: ptr_0ojqVAf/Z+r2KaOEvU37sjtMAXc+unRfqkFjNQQWy54=" \
  -H "Content-Type: application/x-tar" \
  --data-binary @/tmp/autopilot-build.tar.gz 2>&1 | grep "Successfully"

# Redeploy api e worker
for SVC in kibem21hj7nr zdlafclmrh5o; do
  SPEC=$(curl -s "https://portainer.apvsiguatemi.net/api/endpoints/1/docker/services/$SVC" -H "X-API-Key: ptr_0ojqVAf/Z+r2KaOEvU37sjtMAXc+unRfqkFjNQQWy54=")
  VER=$(echo "$SPEC" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['Version']['Index'])")
  echo "$SPEC" | python3 -c "import json,sys; d=json.load(sys.stdin); spec=d['Spec']; spec['TaskTemplate']['ForceUpdate']=spec['TaskTemplate'].get('ForceUpdate',0)+1; print(json.dumps(spec))" > /tmp/svc.json
  curl -s -X POST "https://portainer.apvsiguatemi.net/api/endpoints/1/docker/services/$SVC/update?version=$VER" \
    -H "X-API-Key: ptr_0ojqVAf/Z+r2KaOEvU37sjtMAXc+unRfqkFjNQQWy54=" \
    -H "Content-Type: application/json" --data @/tmp/svc.json > /dev/null
  echo "Redeployado: $SVC"
done
```

Após o deploy, aguarde 20s e verifique: `curl -s https://navegador.apvsiguatemi.net/health`

Ao final exiba o relatório completo e confirme quais reparos foram aplicados com sucesso.
