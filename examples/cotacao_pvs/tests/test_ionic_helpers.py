import asyncio
from unittest.mock import AsyncMock

from cotacao_pvs.ionic_helpers import (
    js_set_input,
    click_ion_button,
    click_ion_item,
    select_ionic,
    select_ionic_by_label,
    fill_input_by_label,
    get_selectable_value,
    get_form_errors,
    dump_visible_form,
    extrair_menor_parcela,
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _fake_page(eval_result=None):
    page = AsyncMock()
    page.evaluate = AsyncMock(return_value=eval_result)
    page.query_selector = AsyncMock(return_value=AsyncMock())
    page.mouse = AsyncMock()
    page.mouse.click = AsyncMock()
    page.keyboard = AsyncMock()
    page.keyboard.type = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    return page


def test_js_set_input_invokes_evaluate():
    page = _fake_page()
    _run(js_set_input(page, "#cnpj", "19.186.569/0001-11"))
    assert page.evaluate.called
    args = page.evaluate.call_args[0]
    assert "HTMLInputElement" in args[0]
    assert args[1] == ["#cnpj", "19.186.569/0001-11"]


def test_click_ion_button_returns_true_when_found():
    page = _fake_page(eval_result=True)
    result = _run(click_ion_button(page, "Entrar"))
    assert result is True


def test_click_ion_button_returns_false_when_missing():
    page = _fake_page(eval_result=False)
    result = _run(click_ion_button(page, "Não existe"))
    assert result is False


def test_click_ion_item():
    page = _fake_page(eval_result=True)
    result = _run(click_ion_item(page, "Nova Cotação"))
    assert result is True


def test_select_ionic_returns_false_when_pos_none():
    page = _fake_page(eval_result=None)
    result = _run(select_ionic(page, "state", "Bahia"))
    assert result is False


def test_select_ionic_returns_true_when_select_found():
    page = _fake_page(eval_result={"x": 100, "y": 100, "w": 200})
    result = _run(select_ionic(page, "state", "Bahia"))
    assert result is True
    page.mouse.click.assert_called_once()


def test_fill_input_by_label_returns_true():
    page = _fake_page(eval_result=True)
    result = _run(fill_input_by_label(page, "Nome", "Teste"))
    assert result is True


def test_get_selectable_value_returns_text():
    page = _fake_page(eval_result="2020")
    result = _run(get_selectable_value(page, "version"))
    assert result == "2020"


def test_get_form_errors_counts():
    page = _fake_page(eval_result="Form: Campo obrigatório e Campo obrigatório")
    assert _run(get_form_errors(page)) == 2


def test_dump_visible_form_returns_dict():
    fake_dict = {"text": "...", "inputs": [], "selects": []}
    page = _fake_page(eval_result=fake_dict)
    result = _run(dump_visible_form(page))
    assert result == fake_dict


def test_extrair_menor_parcela_returns_cheapest():
    body = "Plano A: R$ 100,00\nPlano B: R$ 80,50\nPlano C: R$ 200,00"
    assert extrair_menor_parcela(body) == "R$80.50"


def test_extrair_menor_parcela_returns_none_when_no_prices():
    assert extrair_menor_parcela("nada aqui") is None


def test_extrair_menor_parcela_handles_thousands():
    body = "R$ 1.500,00\nR$ 999,99"
    assert extrair_menor_parcela(body) == "R$999.99"
