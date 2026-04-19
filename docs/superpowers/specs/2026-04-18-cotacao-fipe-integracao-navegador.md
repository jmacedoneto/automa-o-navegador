# Design: Integração Cotação FIPE no Framework /navegador

**Data:** 2026-04-18  
**Status:** Aprovado  

---

## Contexto

O projeto `cotacao_pvs` é um script Python standalone que usa Playwright para acessar `app.apvs.vc`, navegar pelo formulário de cotação e extrair o preço do plano Prata para cada veículo da tabela FIPE por faixa de valor. Ele salva os resultados na tabela `cotacoes_fipe` no Supabase.

O objetivo é integrar essa automação ao framework /navegador (AutoPilot) para que apareça e se comporte exatamente como qualquer outra automação: visível na UI, com progresso em tempo real, screenshots por veículo, histórico de execuções e agendamento.

---

## Arquitetura

```
UI /navegador (https://navegador.apvsiguatemi.net)
    └── Automação "Cotação FIPE - APVS"
            ├── Step 1: navigate → https://app.apvs.vc/home  (login)
            └── Step 2: cotacao_pvs_loop
                    ├── Veículo 1/94 → screenshot → salva Supabase
                    ├── Veículo 2/94 → screenshot → salva Supabase
                    └── ...N/N
```

### Componentes modificados

| Arquivo | Mudança |
|---|---|
| `backend/app/services/browser_executor.py` | +~60 linhas: `elif action == "cotacao_pvs_loop"` |
| `backend/app/workers/tasks.py` | `time_limit` 900 → 9000, `soft_time_limit` 870 → 8970 |
| `cotacao_pvs/automacao_cotacao.py` | Remove `main()`, exporta funções reutilizáveis |
| `cotacao_pvs/cotacao_executor.py` | Novo arquivo: lógica do loop isolada |

---

## Step `cotacao_pvs_loop`

### Formato no JSON da automação

```json
{
  "action": "cotacao_pvs_loop",
  "veiculos_file": "/root/navegador/cotacao_pvs/veiculos_referencia.json",
  "regioes": {
    "capital": "Salvador",
    "interior": "Santo Antônio de Jesus"
  },
  "tentativas": 3
}
```

### Fluxo interno

```
Inicialização (uma vez):
  1. do_login(page) → preenche CNPJ/senha, clica Entrar, aguarda /dashboard

Para cada (veículo, região) com código FIPE:
  1. voltar_dashboard(page)
  2. fazer_cotacao(page, fipe, cidade) com retry até N tentativas
     ├── do_step1_fipe → digita código, avança para /2/
     ├── do_step2_dados → selects Ionic (estado, cidade), dados pessoais fictícios
     ├── do_step3_detalhes → blindado=Não, importado=Não, uso=Particular
     └── capturar_planos → regex extrai "Prata R$XXX"
  3. salvar_supabase(row) → upsert em cotacoes_fipe
  4. _on_screenshot(img) → UI recebe foto em tempo real
  5. _on_step(n) → UI atualiza barra de progresso
```

### Retry por tipo de erro

| Erro | Comportamento |
|---|---|
| Step 2/3 timeout (Ionic lento) | Retry automático, aguarda 5s entre tentativas |
| Step 1 código FIPE rejeitado | Retry 1x; se persistir salva `erro="código inválido"` |
| Exceção inesperada | Retry até N tentativas, loga erro no Supabase |

---

## Registro da automação no banco

```json
{
  "name": "Cotação FIPE - APVS",
  "description": "Cotação automática de todos os veículos FIPE por faixa de valor (leve/pesado × capital/interior)",
  "erp_url": "https://app.apvs.vc",
  "credentials": {
    "login_cnpj": "19.186.569/0001-11",
    "login_senha": "Macedo020589#"
  },
  "steps": [
    { "action": "navigate", "url": "https://app.apvs.vc/home", "waitTime": 8000, "description": "Abrir app APVS" },
    { "action": "cotacao_pvs_loop", "tentativas": 3, "description": "Cotar todos os veículos FIPE" }
  ],
  "outputs": []
}
```

---

## Experiência na UI

- **Lista de automações:** aparece como "Cotação FIPE - APVS" com status e última execução
- **Progresso em tempo real:** barra "Step 23 de 94" + screenshot do planos atual
- **Histórico:** cada execução mostra total OK/erro em `extracted_data`
- **Agendamento:** disponível via painel de schedules (ex: toda segunda 6h)
- **Cancelamento:** UI pode setar `status=cancelled` no `execution_logs`; o loop verifica entre veículos

---

## Dados salvos

### Tabela `cotacoes_fipe` (Supabase)
| Coluna | Tipo | Descrição |
|---|---|---|
| faixa_min | integer | Início da faixa de valor FIPE |
| faixa_max | integer | Fim da faixa de valor FIPE |
| tipo | text | `leve` ou `pesado` |
| regiao | text | `capital` ou `interior` |
| cidade | text | Nome da cidade |
| codigo_fipe | text | Código FIPE do veículo de referência |
| modelo | text | Nome do modelo |
| valor_prata | text | Preço do plano Prata (ex: `R$156.25`) |
| erro | text | Mensagem de erro se falhou |
| atualizado_em | timestamptz | Timestamp da última atualização |

### `execution_logs.extracted_data`
```json
{
  "total_ok": 87,
  "total_erro": 7,
  "total_sem_fipe": 13
}
```

---

## Volume e tempo

| Item | Valor |
|---|---|
| Veículos com FIPE (atual) | 94 |
| Veículos com FIPE (após completar leves) | ~120 |
| Regiões | 2 (capital + interior) |
| Total de cotações | ~188-240 |
| Tempo médio por cotação | ~45s |
| Tempo total estimado | ~140-180 min |
| Timeout do Celery worker | 9000s (aumentado de 900s) |

---

## Fora do escopo

- Suporte a mais regiões além de capital/interior (pode ser adicionado via JSON do step)
- Interface para editar `veiculos_referencia.json` pela UI
- Notificação WhatsApp ao terminar (pode ser adicionado via `outputs` da automação)
