
# Plano: Corrigir URL do DevTools - Substituir 0.0.0.0:3000 pelo Hostname Publico

## Problema

A URL do DevTools retornada pelo Browserless contem o endereco interno do container Docker:
```
ws=0.0.0.0:3000/devtools/page/...
```

Isso nao funciona porque o navegador do usuario nao consegue acessar `0.0.0.0:3000` (endereco interno do Docker).

## Solucao

Substituir o endereco interno pelo hostname publico do Browserless:
```
ws=browserless.apvsiguatemi.net/devtools/page/...
```

---

## Arquivo a Modificar

### supabase/functions/start-recording-session/index.ts

Adicionar logica para corrigir a URL do DevTools antes de retornar ao frontend.

```typescript
// Linha ~142-152 - Apos obter o devtoolsFrontendUrl

const devtoolsPath = currentSession.devtoolsFrontendUrl;

// Corrigir a URL do WebSocket para usar o hostname publico
// O Browserless retorna algo como: /devtools/inspector.html?ws=0.0.0.0:3000/devtools/page/XXX
// Precisamos substituir 0.0.0.0:3000 pelo hostname publico

let correctedDevtoolsPath = devtoolsPath;

// Substituir enderecos internos pelo hostname publico
correctedDevtoolsPath = correctedDevtoolsPath
  .replace(/ws=0\.0\.0\.0:\d+/g, `ws=${cleanBrowserlessUrl}`)
  .replace(/ws=localhost:\d+/g, `ws=${cleanBrowserlessUrl}`)
  .replace(/wss=0\.0\.0\.0:\d+/g, `wss=${cleanBrowserlessUrl}`)
  .replace(/wss=localhost:\d+/g, `wss=${cleanBrowserlessUrl}`);

// Construir URL completa
let liveUrl = `https://${cleanBrowserlessUrl}${correctedDevtoolsPath}`;
```

---

## Exemplo de Correcao

Antes:
```
/devtools/inspector.html?ws=0.0.0.0:3000/devtools/page/6C5F189340285A26A12F92B0F45F6CB2
```

Depois:
```
/devtools/inspector.html?ws=browserless.apvsiguatemi.net/devtools/page/6C5F189340285A26A12F92B0F45F6CB2
```

URL final:
```
https://browserless.apvsiguatemi.net/devtools/inspector.html?ws=browserless.apvsiguatemi.net/devtools/page/6C5F189340285A26A12F92B0F45F6CB2&token=DefinaUmaSenhaForteAqui123
```

---

## Tambem Corrigir em execute-automation

O mesmo problema existe na Edge Function `execute-automation/index.ts` para o Live Preview. Aplicar a mesma correcao la.

---

## Ordem de Implementacao

| Passo | Arquivo | Descricao |
|-------|---------|-----------|
| 1 | `start-recording-session/index.ts` | Corrigir URL do DevTools |
| 2 | `execute-automation/index.ts` | Aplicar mesma correcao no Live Preview |
| 3 | Deploy das Edge Functions | Testar o fluxo completo |

---

## Resultado Esperado

1. Usuario clica em "Gravar Automacao"
2. Edge Function inicia sessao e corrige a URL do DevTools
3. Frontend recebe URL com hostname publico correto
4. DevTools abre e mostra a pagina do ERP (sem tela em branco!)
5. Usuario pode interagir com a pagina
