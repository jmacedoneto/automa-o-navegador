"""Ionic/Angular JS helpers for the cotação DSL.

These wrap page.evaluate(...) JS strings so the steps.json can call them
via `run_python`. The legacy code (cotacao_pvs/automacao_cotacao.py) has these
inline; P1b promotes them to a reusable module so the DSL stays declarative.
"""
import re


_PRICE_RE = re.compile(r"R\$\s*([\d.,]+)")


def _parse_brl_value(raw_value: str) -> float:
    value = raw_value.strip().replace(" ", "")
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        value = value.replace(",", ".")
    return float(value)


# ─── DOM helpers ───────────────────────────────────────────────

async def js_set_input(page, selector: str, value: str) -> None:
    """Set input value via the native setter (Angular reactive forms)."""
    await page.evaluate(
        '''([sel, val]) => {
            const el = document.querySelector(sel);
            if (!el) return;
            const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            set.call(el, val);
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
        }''',
        [selector, value],
    )


async def click_ion_button(page, text: str) -> bool:
    """Click an `ion-button` whose visible text contains `text`."""
    return bool(await page.evaluate(
        '''(text) => {
            for (const b of document.querySelectorAll('ion-button')) {
                if (b.innerText.includes(text) && b.offsetParent !== null) { b.click(); return true; }
            }
            return false;
        }''',
        text,
    ))


async def click_ion_item(page, text: str) -> bool:
    """Click an `ion-item` whose visible text equals `text`."""
    return bool(await page.evaluate(
        '''(text) => {
            for (const i of document.querySelectorAll('ion-item')) {
                if (i.innerText.trim() === text) { i.click(); return true; }
            }
            return false;
        }''',
        text,
    ))


async def get_selectable_value(page, formcontrolname: str):
    """Return the current value of an `ionic-selectable` field."""
    return await page.evaluate(
        '''(fc) => {
            const f = Array.from(document.querySelectorAll('form')).find(f => !f.closest('.ion-page-hidden'));
            for (const s of f?.querySelectorAll('ionic-selectable') || []) {
                if (s.getAttribute('formcontrolname') === fc)
                    return s.querySelector('.ionic-selectable-value-item')?.innerText?.trim() || null;
            }
            return null;
        }''',
        formcontrolname,
    )


async def _pick_modal_option(page, option_text: str, use_search: bool) -> bool:
    """Shared modal interaction: optional searchbar typing, then option click."""
    await page.wait_for_timeout(3000)
    if use_search:
        sb = await page.query_selector("ion-modal ion-searchbar input")
        if sb:
            await sb.click()
            await page.keyboard.type(option_text, delay=50)
            await page.wait_for_timeout(2000)
    selected = await page.evaluate(
        '''(text) => {
            const m = document.querySelector('ion-modal, ion-alert');
            if (!m) return false;
            for (const item of m.querySelectorAll('ion-item, button')) {
                const t = item.innerText.trim();
                if (t === text || t.startsWith(text)) { item.click(); return true; }
            }
            return false;
        }''',
        option_text,
    )
    await page.wait_for_timeout(2000)
    return bool(selected)


async def select_ionic(page, formcontrolname: str, option_text: str, use_search: bool = False) -> bool:
    """Open an ionic-selectable by formcontrolname and pick `option_text`."""
    pos = await page.evaluate(
        '''(fc) => {
            const f = Array.from(document.querySelectorAll('form')).find(f => !f.closest('.ion-page-hidden'));
            for (const s of f?.querySelectorAll('ionic-selectable') || []) {
                if (s.getAttribute('formcontrolname') === fc) {
                    s.scrollIntoView({block: 'center'});
                    const rect = s.getBoundingClientRect();
                    return {x: rect.x + rect.width/2, y: rect.y + rect.height/2, w: rect.width};
                }
            }
            return null;
        }''',
        formcontrolname,
    )
    if not pos or pos.get("w", 0) == 0:
        return False
    await page.mouse.click(pos["x"], pos["y"])
    return await _pick_modal_option(page, option_text, use_search)


async def select_ionic_by_label(page, label_text: str, option_text: str, use_search: bool = False) -> bool:
    """Open a selectable field by its visible label, then pick `option_text`."""
    pos = await page.evaluate(
        '''(labelText) => {
            const forms = Array.from(document.querySelectorAll('form'));
            const form = forms.find(f => !f.closest('.ion-page-hidden')) || document;
            const norm = s => (s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
            const wanted = norm(labelText);
            for (const col of form.querySelectorAll('ion-col, div')) {
                const label = col.querySelector('ion-label');
                if (!label || norm(label.innerText) !== wanted) continue;
                const field = col.querySelector('ionic-selectable, ion-select');
                if (!field) continue;
                field.scrollIntoView({ block: 'center' });
                const rect = field.getBoundingClientRect();
                return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, w: rect.width };
            }
            return null;
        }''',
        label_text,
    )
    if not pos or pos.get("w", 0) == 0:
        return False
    await page.mouse.click(pos["x"], pos["y"])
    return await _pick_modal_option(page, option_text, use_search)


async def fill_input_by_label(page, label_text: str, value: str) -> bool:
    """Fill an input that's grouped with a label (Ionic)."""
    return bool(await page.evaluate(
        '''([labelText, val]) => {
            const forms = Array.from(document.querySelectorAll('form'));
            const form = forms.find(f => !f.closest('.ion-page-hidden')) || document;
            const norm = s => (s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
            const wanted = norm(labelText);
            for (const col of form.querySelectorAll('ion-col, div, label')) {
                const label = col.querySelector('ion-label');
                if (!label || norm(label.innerText) !== wanted) continue;
                const input = col.querySelector('input');
                if (!input) continue;
                const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                set.call(input, val);
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                input.dispatchEvent(new Event('blur', { bubbles: true }));
                return true;
            }
            return false;
        }''',
        [label_text, value],
    ))


async def get_form_errors(page) -> int:
    """Count 'Campo obrigatório' labels in the visible form."""
    text = await page.evaluate(
        '''() => {
            const f = Array.from(document.querySelectorAll('form')).find(f => !f.closest('.ion-page-hidden'));
            return f?.innerText || '';
        }''',
    )
    return text.count("Campo obrigatório") if text else 0


async def dump_visible_form(page) -> dict:
    """Return visible form metadata for selector drift debugging."""
    return await page.evaluate(
        '''() => {
            const visible = el => !!(el && (el.offsetParent !== null || el.getClientRects().length));
            const forms = Array.from(document.querySelectorAll('form')).filter(visible);
            const form = forms[0] || document;
            return {
                text: (form.innerText || '').slice(0, 4000),
                inputs: Array.from(form.querySelectorAll('input')).map(el => ({
                    name: el.name || null,
                    type: el.type || null,
                    placeholder: el.placeholder || null,
                    value: el.value || null,
                })),
                selects: Array.from(form.querySelectorAll('ionic-selectable, ion-select')).map(el => ({
                    tag: el.tagName,
                    formcontrolname: el.getAttribute('formcontrolname'),
                    text: (el.innerText || '').trim(),
                })),
            };
        }''',
    )


# ─── Pure-Python helpers ─────────────────────────────────────

def extrair_menor_parcela(body: str) -> str | None:
    """Return the cheapest R$ value found in `body`, formatted as 'R$X.XX'."""
    prices = []
    for match in _PRICE_RE.finditer(body or ""):
        try:
            prices.append(_parse_brl_value(match.group(1)))
        except ValueError:
            continue
    if not prices:
        return None
    return f"R${min(prices):.2f}"
