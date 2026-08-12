# Cotação PVS — NavRunner implementation

Migrated from the legacy imperative `cotacao_pvs/automacao_cotacao.py` (544 lines)
to a NavRunner DSL workflow. The legacy script is preserved at `/root/navegador/cotacao_pvs/automacao_cotacao.py`
(mounted read-only into the worker) for reference.

## Files

- `ionic_helpers.py` — Python wrappers for Ionic/Angular JS interactions. The
  only piece that needs `page.evaluate(...)` since Ionic components don't
  expose stable CSS selectors.
- `steps.json` — the DSL flow. Auth block + Ionic-step `run_python` blocks
  + `for_each` over combos.
- `automacao.py` — outer loop driver. Loads `veiculos_referencia.json`,
  builds the cartesian product (vehicle × region), dispatches one Celery
  task per combo.
- `tests/` — unit tests for helpers and the driver.

## Run

```python
from cotacao_pvs.automacao import executar_cotacao_pvs
import asyncio
result = asyncio.run(executar_cotacao_pvs())
print(result)  # {'total_combos': 60, 'dispatched': 60}
```

Or via Celery:

```bash
docker exec $(docker ps -q --filter name=autopilot_worker | head -1) \
  celery -A app.workers.celery_app call app.workers.tasks.executar_cotacao_pvs
```

## Required credentials

In Supabase `settings` table (or env vars):
- `apvs_login.user` / `apvs_login.pass` — CNPJ + senha do app.apvs.vc
- `supabase_key` — service key para PATCH em `cotacoes_fipe` (or `SUPABASE_KEY` env var)

## Output

The DSL writes to Supabase `cotacoes_fipe` — updates `valor_prata` (cheapest plan) or
`erro` (when no plans found) per (faixa_min, faixa_max, tipo, regiao) row.

## Failure modes

- FIPE code rejected → toast detected, returns False, run fails with clear error
- Model not loaded within 120s → raises, run fails
- "Campo obrigatório" errors → captured by `get_form_errors`, step fails
- ForEach limit (max_iterations=100) cuts off if more combos than expected
