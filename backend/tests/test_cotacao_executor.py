import sys
import unittest
from pathlib import Path
from unittest.mock import patch


COTACAO_PVS_DIR = Path("/root/navegador/cotacao_pvs")
if str(COTACAO_PVS_DIR) not in sys.path:
    sys.path.insert(0, str(COTACAO_PVS_DIR))

import automacao_cotacao
from automacao_cotacao import extrair_menor_parcela, preencher_campos_ano, salvar_supabase


class CotacaoExecutorTests(unittest.TestCase):
    def test_extrai_menor_parcela_entre_tres_planos(self):
        body = """
        Planos
        Ouro
        R$ 219,90
        Prata
        R$ 156,25
        Bronze
        R$ 132,40
        """

        self.assertEqual(extrair_menor_parcela(body), "R$132.40")

    def test_retorna_none_quando_nao_ha_valor(self):
        self.assertIsNone(extrair_menor_parcela("Sem planos disponiveis"))

    def test_preencher_campos_ano_tenta_ano_modelo_antes_do_ano_fabricacao(self):
        chamadas = []

        async def fake_select_ionic(page, formcontrolname, option_text, use_search=False):
            chamadas.append((formcontrolname, option_text, use_search))
            return formcontrolname == "year"

        with patch.object(automacao_cotacao, "select_ionic", side_effect=fake_select_ionic):
            result = automacao_cotacao.asyncio.run(preencher_campos_ano(object(), "1987"))

        self.assertTrue(result)
        self.assertEqual(chamadas, [("year", "1987", False)])

    def test_preencher_campos_ano_faz_fallback_para_manufacture_year(self):
        chamadas = []

        async def fake_select_ionic(page, formcontrolname, option_text, use_search=False):
            chamadas.append((formcontrolname, option_text, use_search))
            return formcontrolname == "manufactureYear"

        with patch.object(automacao_cotacao, "select_ionic", side_effect=fake_select_ionic):
            result = automacao_cotacao.asyncio.run(preencher_campos_ano(object(), "1987"))

        self.assertTrue(result)
        self.assertEqual(
            chamadas,
            [("year", "1987", False), ("manufactureYear", "1987", False)],
        )

    def test_salvar_supabase_atualiza_registro_existente_sem_post(self):
        chamadas = []

        class FakeResponse:
            def __init__(self, status_code):
                self.status_code = status_code

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def patch(self, url, headers=None, json=None):
                chamadas.append(("patch", url, json))
                return FakeResponse(204)

            async def post(self, url, headers=None, json=None):
                chamadas.append(("post", url, json))
                return FakeResponse(201)

        row = {
            "faixa_min": 0,
            "faixa_max": 11000,
            "tipo": "leve",
            "regiao": "capital",
            "cidade": "Salvador",
            "codigo_fipe": "001124-0",
            "modelo": "147 C/ CL",
            "valor_prata": "R$132.40",
            "erro": "",
            "atualizado_em": "2026-04-21T00:00:00+00:00",
        }

        with patch.object(automacao_cotacao.httpx, "AsyncClient", FakeAsyncClient):
            result = automacao_cotacao.asyncio.run(salvar_supabase(row))

        self.assertTrue(result)
        self.assertEqual(len(chamadas), 1)
        metodo, url, payload = chamadas[0]
        self.assertEqual(metodo, "patch")
        self.assertIn("faixa_min=eq.0", url)
        self.assertIn("faixa_max=eq.11000", url)
        self.assertIn("tipo=eq.leve", url)
        self.assertIn("regiao=eq.capital", url)
        self.assertEqual(payload, row)


if __name__ == "__main__":
    unittest.main()
