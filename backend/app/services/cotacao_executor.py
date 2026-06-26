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

VEICULOS_FILE_DEFAULT = "/app/cotacao_pvs/veiculos_referencia.json"
REGIOES_DEFAULT = {
    "capital": "Salvador",
    "interior": "Santo Antônio de Jesus",
}

_PAGE_CLOSED_SIGNALS = (
    "target page, context or browser has been closed",
    "target closed",
    "browser has been closed",
    "connection closed",
)


def _is_page_closed(err: str) -> bool:
    low = err.lower()
    return any(s in low for s in _PAGE_CLOSED_SIGNALS)


async def run_cotacao_loop(
    page,
    step: dict,
    credentials: dict,
    on_step: Callable[[int], None] | None = None,
    on_screenshot: Callable[[str], None] | None = None,
    browser=None,
) -> dict:
    """
    Roda o loop de cotação FIPE completo.
    Retorna dict com total_ok, total_erro, total_sem_fipe.
    Se a página fechar durante o loop, recria e refaz login automaticamente.
    """
    cotacao_path = "/app/cotacao_pvs"
    if cotacao_path not in sys.path:
        sys.path.insert(0, cotacao_path)

    from automacao_cotacao import (
        do_login,
        fazer_cotacao_com_retry,
        limpar_resultados_supabase,
        salvar_supabase,
    )
    import automacao_cotacao as _mod

    veiculos_file = step.get("veiculos_file", VEICULOS_FILE_DEFAULT)
    regioes = step.get("regioes", REGIOES_DEFAULT)
    tentativas = step.get("tentativas", 3)
    clear_existing_results = step.get("clear_existing_results", True)

    _mod.LOGIN_CNPJ = credentials.get("login_cnpj", "")
    _mod.LOGIN_SENHA = credentials.get("login_senha", "")

    with open(veiculos_file, "r") as f:
        veiculos = json.load(f)

    async def _reconectar():
        """Cria nova página e refaz login. Retorna a nova page."""
        nonlocal page
        if browser is None:
            raise RuntimeError("Browser fechado e sem referência para recriar página")
        print("[cotacao_loop] Página fechada — recriando e fazendo login novamente...", flush=True)
        try:
            await page.close()
        except Exception:
            pass
        page = await browser.new_page()
        ok = await do_login(page)
        if not ok:
            raise RuntimeError("Falha no re-login após página fechada")
        print("[cotacao_loop] Re-login OK", flush=True)
        return page

    # Login inicial
    print("[cotacao_loop] Fazendo login...", flush=True)
    logged_in = await do_login(page)
    if not logged_in:
        raise RuntimeError("Falha no login em app.apvs.vc")
    print("[cotacao_loop] Login OK", flush=True)

    if clear_existing_results:
        print("[cotacao_loop] Limpando valores anteriores da tabela cotacoes_fipe...", flush=True)
        cleared = await limpar_resultados_supabase()
        if not cleared:
            raise RuntimeError("Falha ao limpar resultados anteriores em cotacoes_fipe")
        print("[cotacao_loop] Limpeza inicial OK", flush=True)

    total_ok = 0
    total_erro = 0
    total_sem_fipe = 0

    veiculos_com_fipe = [v for v in veiculos if v.get("codigo_fipe")]
    total = len(veiculos_com_fipe) * len(regioes)
    n = 0

    for regiao_nome, cidade in regioes.items():
        print(f"\n[cotacao_loop] === Região: {regiao_nome.upper()} ({cidade}) ===", flush=True)

        for veiculo in veiculos:
            fipe = veiculo.get("codigo_fipe")
            tipo = veiculo["tipo"]

            if not fipe:
                total_sem_fipe += 1
                continue

            n += 1
            faixa = f"{veiculo['faixa_min']:,}-{veiculo['faixa_max']:,}"
            print(f"[cotacao_loop] [{n}/{total}] {tipo} | {faixa} | {fipe} | {regiao_nome}", flush=True)

            try:
                valor, erro = await fazer_cotacao_com_retry(page, fipe, cidade, tentativas=tentativas)

                # Se todos retries falharam por página fechada, tenta reconectar e retentar
                if erro and _is_page_closed(erro):
                    page = await _reconectar()
                    valor, erro = await fazer_cotacao_com_retry(page, fipe, cidade, tentativas=tentativas)

            except Exception as e:
                err_str = str(e)
                if _is_page_closed(err_str):
                    try:
                        page = await _reconectar()
                        valor, erro = await fazer_cotacao_com_retry(page, fipe, cidade, tentativas=tentativas)
                    except Exception as e2:
                        valor, erro = None, str(e2)
                else:
                    valor, erro = None, err_str

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

            try:
                await salvar_supabase(row)
            except Exception as e:
                print(f"  ⚠️ Erro ao salvar Supabase: {e}", flush=True)

            if valor:
                total_ok += 1
                print(f"  ✅ Prata={valor}", flush=True)
            else:
                total_erro += 1
                print(f"  ❌ {erro}", flush=True)

            # Screenshot após cada cotação
            if on_screenshot:
                try:
                    img = await page.screenshot(full_page=False, type="jpeg", quality=70)
                    on_screenshot(base64.b64encode(img).decode())
                except Exception:
                    pass

            if on_step:
                on_step(n)

    print(f"\n[cotacao_loop] Concluído: {total_ok} OK, {total_erro} erros, {total_sem_fipe} sem FIPE", flush=True)

    return {
        "total_ok": total_ok,
        "total_erro": total_erro,
        "total_sem_fipe": total_sem_fipe,
        "total": total,
    }
