# Cotação FIPE — Integração no Framework /navegador

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrar a automação de cotação FIPE ao framework /navegador (AutoPilot) como uma automação nativa — com progresso em tempo real, screenshot por veículo, histórico de execuções e agendamento.

**Architecture:** Um novo tipo de step `cotacao_pvs_loop` é adicionado ao `browser_executor.py`. A lógica do loop fica em `backend/app/services/cotacao_executor.py`. O diretório `/root/navegador/cotacao_pvs/` é montado como volume read-only nos containers worker e API para acesso ao `veiculos_referencia.json`.

**Tech Stack:** Python 3.11, Playwright (via Browserless CDP), FastAPI, Celery, Supabase (PostgreSQL + REST API), Docker Swarm

---

## Mapa de arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `backend/app/services/cotacao_executor.py` | **Criar** | Loop de cotação, retry, login, save Supabase |
| `backend/app/services/browser_executor.py` | **Modificar** linha ~240 | Adicionar `elif action == "cotacao_pvs_loop"` |
| `backend/app/workers/tasks.py` | **Modificar** linha 28 | time_limit 900 → 9000 |
| `docker-compose.yml` | **Modificar** | Montar `/root/navegador/cotacao_pvs` nos containers |
| `cotacao_pvs/automacao_cotacao.py` | **Modificar** | Remover `main()`, expor funções como biblioteca |

---

## Task 1: Refatorar `automacao_cotacao.py` como biblioteca

**Files:**
- Modify: `cotacao_pvs/automacao_cotacao.py`

- [ ] **Step 1: Remover `main()` e `argparse`, manter apenas funções**

Substituir o conteúdo de `main()` e imports de `argparse`/`csv` pelo seguinte — deixar apenas as funções reutilizáveis expostas:

```python
# Remover estas linhas do topo:
# import argparse
# import csv

# Remover a função main() inteira (do def main(): até asyncio.run(main()))
# Remover o bloco if __name__ == "__main__":
```

As funções que DEVEM permanecer (não alterar):
- `js_set_input`, `click_ion_button`, `click_ion_item`
- `get_selectable_value`, `select_ionic`, `get_form_errors`
- `do_login`, `do_step1_fipe`, `do_step2_dados`, `do_step3_detalhes`
- `capturar_planos`, `voltar_dashboard`, `fazer_cotacao`
- `fazer_cotacao_com_retry`, `salvar_supabase`
- Constantes: `URL_HOME`, `URL_DASHBOARD`, `TIMEOUT_NAV`, `TIMEOUT_MODEL`
- Constantes: `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_HEADERS`

- [ ] **Step 2: Verificar que o arquivo importa corretamente**

```bash
cd /root/navegador/cotacao_pvs
python3 -c "from automacao_cotacao import do_login, fazer_cotacao_com_retry, salvar_supabase; print('OK')"
```
Esperado: `OK`

- [ ] **Step 3: Commit**

```bash
cd /root/navegador
git add cotacao_pvs/automacao_cotacao.py
git commit -m "refactor: automacao_cotacao vira biblioteca (remove main/argparse)"
```

---

## Task 2: Criar `cotacao_executor.py`

**Files:**
- Create: `backend/app/services/cotacao_executor.py`

- [ ] **Step 1: Criar o arquivo com a lógica do loop**

```python
"""
Loop de cotação FIPE para o framework /navegador.
Executado pelo browser_executor quando action == "cotacao_pvs_loop".
"""
import asyncio
import json
import base64
import sys
from datetime import datetime, timezone
from typing import Callable

sys.path.insert(0, "/app/cotacao_pvs")

VEICULOS_FILE_DEFAULT = "/app/cotacao_pvs/veiculos_referencia.json"
REGIOES_DEFAULT = {
    "capital": "Salvador",
    "interior": "Santo Antônio de Jesus",
}


async def run_cotacao_loop(
    page,
    step: dict,
    credentials: dict,
    on_step: Callable[[int], None] | None = None,
    on_screenshot: Callable[[str], None] | None = None,
) -> dict:
    """
    Roda o loop de cotação FIPE completo.
    Retorna dict com total_ok, total_erro, total_sem_fipe.
    """
    from automacao_cotacao import (
        do_login,
        voltar_dashboard,
        fazer_cotacao_com_retry,
        salvar_supabase,
    )

    veiculos_file = step.get("veiculos_file", VEICULOS_FILE_DEFAULT)
    regioes = step.get("regioes", REGIOES_DEFAULT)
    tentativas = step.get("tentativas", 3)

    login_cnpj = credentials.get("login_cnpj", "")
    login_senha = credentials.get("login_senha", "")

    # Monkey-patch credenciais no módulo
    import automacao_cotacao as _mod
    _mod.LOGIN_CNPJ = login_cnpj
    _mod.LOGIN_SENHA = login_senha

    with open(veiculos_file, "r") as f:
        veiculos = json.load(f)

    # Login inicial
    await do_login(page)

    total_ok = 0
    total_erro = 0
    total_sem_fipe = 0

    veiculos_com_fipe = [v for v in veiculos if v.get("codigo_fipe")]
    total = len(veiculos_com_fipe) * len(regioes)
    n = 0

    for regiao_nome, cidade in regioes.items():
        for veiculo in veiculos:
            fipe = veiculo.get("codigo_fipe")
            tipo = veiculo["tipo"]

            if not fipe:
                total_sem_fipe += 1
                continue

            n += 1
            print(f"[cotacao_loop] [{n}/{total}] {tipo} | {fipe} | {regiao_nome}", flush=True)

            try:
                valor, erro = await fazer_cotacao_com_retry(page, fipe, cidade, tentativas=tentativas)

                row = {
                    "faixa_min": veiculo["faixa_min"],
                    "faixa_max": veiculo["faixa_max"],
                    "tipo": tipo,
                    "regiao": regiao_nome,
                    "cidade": cidade,
                    "codigo_fipe": fipe,
                    "modelo": veiculo.get("modelo", ""),
                    "valor_prata": valor or "",
                    "erro": erro or "",
                    "atualizado_em": datetime.now(timezone.utc).isoformat(),
                }

                await salvar_supabase(row)

                if valor:
                    total_ok += 1
                    print(f"  ✅ Prata={valor}", flush=True)
                else:
                    total_erro += 1
                    print(f"  ❌ {erro}", flush=True)

            except Exception as e:
                total_erro += 1
                print(f"  ❌ Exceção: {e}", flush=True)

            # Screenshot da tela atual (planos ou erro)
            if on_screenshot:
                try:
                    img = await page.screenshot(full_page=False, type="jpeg", quality=70)
                    on_screenshot(base64.b64encode(img).decode())
                except Exception:
                    pass

            # Atualizar progresso na UI
            if on_step:
                on_step(n)

    return {
        "total_ok": total_ok,
        "total_erro": total_erro,
        "total_sem_fipe": total_sem_fipe,
        "total": total,
    }
```

- [ ] **Step 2: Commit**

```bash
cd /root/navegador/automa-o-navegador
git add backend/app/services/cotacao_executor.py
git commit -m "feat: criar cotacao_executor com loop FIPE para o framework navegador"
```

---

## Task 3: Adicionar `cotacao_pvs_loop` no `browser_executor.py`

**Files:**
- Modify: `backend/app/services/browser_executor.py`

- [ ] **Step 1: Adicionar o elif após o bloco `download`**

Localizar o trecho (linha ~240 em diante):
```python
                elif action == "download":
                    # ... bloco download existente ...
```

Logo APÓS o bloco `download` (antes de `steps_completed += 1`), adicionar:

```python
                elif action == "cotacao_pvs_loop":
                    from app.services.cotacao_executor import run_cotacao_loop
                    # Extrair credenciais das variáveis (injetadas pelo tasks.py)
                    creds = {
                        "login_cnpj": variables.get("login_cnpj", ""),
                        "login_senha": variables.get("login_senha", ""),
                    }
                    loop_result = await run_cotacao_loop(
                        page=page,
                        step=step,
                        credentials=creds,
                        on_step=on_step,
                        on_screenshot=on_screenshot,
                    )
                    extracted_data["cotacao_result"] = loop_result
                    # Atualizar total_steps com o número real de veículos processados
                    has_explicit_extraction = True
```

- [ ] **Step 2: Commit**

```bash
cd /root/navegador/automa-o-navegador
git add backend/app/services/browser_executor.py
git commit -m "feat: adicionar action cotacao_pvs_loop no browser_executor"
```

---

## Task 4: Aumentar timeout do Celery worker

**Files:**
- Modify: `backend/app/workers/tasks.py` linha 28

- [ ] **Step 1: Aumentar time_limit**

Alterar a linha 28 de:
```python
@celery.task(bind=True, max_retries=2, default_retry_delay=30, time_limit=900, soft_time_limit=870)
```
Para:
```python
@celery.task(bind=True, max_retries=2, default_retry_delay=30, time_limit=9000, soft_time_limit=8970)
```

- [ ] **Step 2: Commit**

```bash
cd /root/navegador/automa-o-navegador
git add backend/app/workers/tasks.py
git commit -m "feat: aumentar time_limit do run_automation para 9000s (cotacao FIPE)"
```

---

## Task 5: Montar volume `cotacao_pvs` nos containers

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Adicionar volume mount no worker e API**

No `docker-compose.yml`, localizar o serviço `autopilot_worker` e adicionar o volume:

```yaml
  autopilot_worker:
    # ... configuração existente ...
    volumes:
      - autopilot_downloads:/tmp
      - /root/navegador/cotacao_pvs:/app/cotacao_pvs:ro   # ← adicionar esta linha
```

Fazer o mesmo para `autopilot_api` (caso precise importar durante testes):

```yaml
  autopilot_api:
    # ... configuração existente ...
    volumes:
      - autopilot_downloads:/tmp
      - /root/navegador/cotacao_pvs:/app/cotacao_pvs:ro   # ← adicionar esta linha
```

- [ ] **Step 2: Commit**

```bash
cd /root/navegador/automa-o-navegador
git add docker-compose.yml
git commit -m "feat: montar cotacao_pvs como volume nos containers worker e api"
```

---

## Task 6: Rebuild e redeploy dos containers

**Files:** nenhum (operação de infraestrutura)

- [ ] **Step 1: Rebuild a imagem**

```bash
cd /root/navegador/automa-o-navegador
docker build -t autopilot:latest ./backend
```
Esperado: `Successfully tagged autopilot:latest`

- [ ] **Step 2: Atualizar o serviço worker (força restart com nova imagem + novo volume)**

```bash
docker service update --image autopilot:latest --mount-add type=bind,source=/root/navegador/cotacao_pvs,target=/app/cotacao_pvs,readonly autonavegador_autopilot_worker
```

- [ ] **Step 3: Atualizar o serviço API**

```bash
docker service update --image autopilot:latest --mount-add type=bind,source=/root/navegador/cotacao_pvs,target=/app/cotacao_pvs,readonly autonavegador_autopilot_api
```

- [ ] **Step 4: Verificar que o worker está rodando**

```bash
docker service ps autonavegador_autopilot_worker --no-trunc | head -5
```
Esperado: status `Running`

- [ ] **Step 5: Verificar que o volume está montado**

```bash
docker exec $(docker ps -q -f name=autopilot_worker) ls /app/cotacao_pvs/
```
Esperado: `automacao_cotacao.py  buscar_fipe.py  config.py  veiculos_referencia.json  ...`

---

## Task 7: Registrar a automação no banco via API

**Files:** nenhum (chamada de API)

- [ ] **Step 1: Criar a automação via curl**

```bash
curl -s -X POST https://navegador.apvsiguatemi.net/automations \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Cotação FIPE - APVS",
    "description": "Cotação automática de todos os veículos FIPE por faixa de valor (leve/pesado × capital/interior). Salva na tabela cotacoes_fipe do Supabase.",
    "erp_url": "https://app.apvs.vc",
    "credentials": {
      "login_cnpj": "19.186.569/0001-11",
      "login_senha": "Macedo020589#"
    },
    "steps": [
      {
        "action": "cotacao_pvs_loop",
        "description": "Cotar todos os veículos FIPE (leve + pesado × capital + interior)",
        "tentativas": 3,
        "waitTime": 0
      }
    ],
    "outputs": []
  }' | python3 -m json.tool | grep '"id"'
```
Esperado: linha com o UUID da automação criada. **Guardar este ID.**

- [ ] **Step 2: Verificar que aparece na UI**

Acessar `https://navegador.apvsiguatemi.net` e confirmar que "Cotação FIPE - APVS" aparece na lista de automações.

---

## Task 8: Teste de execução manual

**Files:** nenhum

- [ ] **Step 1: Disparar execução via API**

Substituir `<AUTOMATION_ID>` pelo ID obtido na Task 7:

```bash
curl -s -X POST https://navegador.apvsiguatemi.net/executions/automations/<AUTOMATION_ID>/execute \
  -H "Content-Type: application/json" \
  -d '{"variables": {}, "live_preview": false}' | python3 -m json.tool
```
Esperado: `{"status": "queued", "execution_id": "...", "job_id": "...", "run_id": "..."}`

- [ ] **Step 2: Monitorar logs do worker**

```bash
docker service logs autonavegador_autopilot_worker -f --tail 50
```
Esperado: linhas `[cotacao_loop] [1/188] leve | 001124-0 | capital`

- [ ] **Step 3: Verificar screenshots em tempo real na UI**

Acessar a execução na UI do /navegador e confirmar que:
- Barra de progresso avança
- Screenshots aparecem (tela de Planos com preços)

- [ ] **Step 4: Verificar dados no Supabase após algumas cotações**

```bash
docker exec $(docker ps -q -f name=supabase_db) psql -U supabase_admin -d postgres \
  -c "SELECT tipo, regiao, valor_prata, erro FROM cotacoes_fipe ORDER BY atualizado_em DESC LIMIT 10;"
```
Esperado: linhas com `valor_prata` preenchido (ex: `R$156.25`) e `erro` vazio.

---

## Self-Review

### Cobertura do spec

| Requisito do spec | Task que implementa |
|---|---|
| Step `cotacao_pvs_loop` no browser_executor | Task 3 |
| `cotacao_executor.py` isolado | Task 2 |
| Login como primeira ação do loop | Task 2 (run_cotacao_loop chama do_login) |
| Retry por tipo de erro | Task 2 (fazer_cotacao_com_retry já existente) |
| Screenshot por veículo | Task 2 (_on_screenshot após cada cotação) |
| Progresso em tempo real (_on_step) | Task 2 |
| time_limit 9000s | Task 4 |
| Volume mount cotacao_pvs | Task 5 + Task 6 |
| Registro no banco | Task 7 |
| Credenciais via `credentials` da automação | Task 2 + Task 3 |
| `extracted_data` com total_ok/erro | Task 2 (return do run_cotacao_loop) |
| Rebuild e redeploy | Task 6 |

### Verificação de consistência de tipos

- `run_cotacao_loop` retorna `dict` com keys `total_ok, total_erro, total_sem_fipe, total` — usado em Task 3 como `extracted_data["cotacao_result"]` ✅
- `on_step` e `on_screenshot` são `Callable` opcionais — mesma assinatura do browser_executor ✅
- `credentials` passado como dict com `login_cnpj` / `login_senha` — consistente entre Task 2 e Task 3 ✅
- `fazer_cotacao_com_retry` existe em `automacao_cotacao.py` (criado na sessão anterior) ✅
