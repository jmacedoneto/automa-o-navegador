
# Plano: Corrigir Live Preview e Gravacao - Endpoint Correto do Browserless

## Problema Identificado

A tela mostra o erro **"Cannot GET /live"** porque o endpoint `/live` que estamos usando **nao existe no Browserless self-hosted**. Esse endpoint e especifico da versao Cloud/Enterprise do Browserless.

### Como funciona no Browserless Docker (self-hosted):

1. **Endpoint `/sessions`** - Lista sessoes ativas em formato JSON
2. Cada sessao retorna um **`devtoolsFrontendUrl`** - URL do Chrome DevTools para visualizar a sessao
3. A visualizacao e feita pelo **Chrome DevTools Inspector**, nao por um player de video

---

## Arquitetura Correta

```text
+------------------------------------------------+
|  Usuario clica "Gravar Automacao"              |
+------------------------------------------------+
         |
         v
+------------------------------------------------+
|  Edge Function inicia sessao via Puppeteer:    |
|  - Conecta ao Browserless via WebSocket        |
|  - Consulta /sessions para obter sessionId     |
|  - Retorna devtoolsFrontendUrl                 |
+------------------------------------------------+
         |
         v
+------------------------------------------------+
|  Frontend abre o DevTools Inspector:           |
|  - URL: devtoolsFrontendUrl + ?token=XXX       |
|  - Mostra a aba da sessao ativa                |
|  - Usuario pode ver e interagir (se headless   |
|    estiver false)                              |
+------------------------------------------------+
```

---

## Arquivos a Modificar

### 1. supabase/functions/start-recording-session/index.ts

**Mudancas:**
- Conectar ao Browserless via WebSocket usando puppeteer-core
- Manter a sessao aberta (nao fechar o browser)
- Consultar o endpoint `/sessions?token=XXX` para obter o `devtoolsFrontendUrl`
- Retornar a URL correta do DevTools

Logica:
```typescript
// 1. Conectar via puppeteer
const wsEndpoint = `wss://${browserlessUrl}?token=${token}&headless=false`;
const browser = await puppeteer.connect({ browserWSEndpoint: wsEndpoint });
const page = await browser.newPage();
await page.goto(erpUrl);

// 2. Buscar sessions para pegar o devtoolsFrontendUrl
const sessionsResponse = await fetch(
  `https://${browserlessUrl}/sessions?token=${token}`
);
const sessions = await sessionsResponse.json();
const currentSession = sessions[0]; // sessao mais recente

// 3. Construir URL do DevTools
const devtoolsUrl = `https://${browserlessUrl}${currentSession.devtoolsFrontendUrl}?token=${token}`;
```

### 2. supabase/functions/execute-automation/index.ts

**Mudancas:**
- Remover referencia ao endpoint `/live` inexistente
- Usar a mesma logica de `/sessions` para obter `devtoolsFrontendUrl`
- Para live preview, conectar primeiro e depois consultar `/sessions`

### 3. src/components/automation/RecordingModal.tsx

**Mudancas:**
- Atualizar texto explicativo informando que abrira o Chrome DevTools
- O DevTools mostra a aba remota e permite interacao

### 4. src/components/automation/LivePreviewModal.tsx

**Mudancas:**
- Atualizar para usar o DevTools URL em vez do `/live`
- O DevTools pode ser embutido em iframe ou aberto em nova janela

---

## Detalhes Tecnicos

### Novo fluxo do start-recording-session

```typescript
// Imports necessarios
import puppeteer from "npm:puppeteer-core@23.11.0";

// Conectar ao browser (nao fechamos!)
const browser = await puppeteer.connect({
  browserWSEndpoint: `wss://${cleanBrowserlessUrl}?token=${token}&headless=false`
});

const page = await browser.newPage();
await page.goto(erpUrl, { waitUntil: 'domcontentloaded' });

// Buscar a sessao ativa para obter devtoolsFrontendUrl
const sessionsUrl = `https://${cleanBrowserlessUrl}/sessions?token=${token}`;
const sessionsRes = await fetch(sessionsUrl);
const sessions = await sessionsRes.json();

// Encontrar a sessao desta pagina
const session = sessions.find(s => s.url?.includes(new URL(erpUrl).hostname));

// URL do DevTools para visualizacao
const devtoolsUrl = session 
  ? `https://${cleanBrowserlessUrl}${session.devtoolsFrontendUrl}`
  : null;

// Retornar para o frontend
return {
  sessionId: session?.browserId || crypto.randomUUID(),
  liveUrl: devtoolsUrl,
  wsEndpoint: browser.wsEndpoint(),
  erpUrl,
};

// IMPORTANTE: Nao chamar browser.close() - a sessao precisa ficar aberta!
```

### Formato do devtoolsFrontendUrl

O Browserless retorna:
```json
{
  "devtoolsFrontendUrl": "/devtools/inspector.html?wss=browserless.company.com/devtools/page/ABC123"
}
```

A URL completa fica:
```
https://browserless.apvsiguatemi.net/devtools/inspector.html?wss=browserless.apvsiguatemi.net/devtools/page/ABC123&token=SEU_TOKEN
```

---

## Consideracoes sobre Docker

### Variaveis de ambiente recomendadas

Para garantir que o modo interativo funcione corretamente:

```yaml
environment:
  - TOKEN=SuaSenhaForte
  - HEADLESS=false          # Permite ver a interface
  - PREBOOT_CHROME=true     # Chrome ja iniciado
  - KEEP_ALIVE=true         # Mantem sessoes ativas
  - ENABLE_DEBUGGER=true    # Habilita DevTools remoto
  - CONNECTION_TIMEOUT=300000  # 5 min timeout para gravacao
```

---

## Alternativa: Usar VNC

Se o DevTools nao for suficiente para interacao, outra opcao e usar uma imagem com VNC:

```yaml
image: browserless/chrome:latest
environment:
  - ENABLE_VNC=true
  - VNC_PORT=5900
```

Isso expoe uma conexao VNC para controle completo da area de trabalho. Mas isso requer um cliente VNC no frontend (mais complexo).

---

## Ordem de Implementacao

| Passo | Arquivo | Descricao |
|-------|---------|-----------|
| 1 | `start-recording-session/index.ts` | Usar puppeteer-core e /sessions API |
| 2 | `execute-automation/index.ts` | Corrigir live preview para usar /sessions |
| 3 | `RecordingModal.tsx` | Atualizar UI para DevTools |
| 4 | `LivePreviewModal.tsx` | Usar devtoolsFrontendUrl |
| 5 | Testar fluxo completo | Verificar se o DevTools abre corretamente |

---

## Resultado Esperado

1. Usuario clica em "Gravar Automacao"
2. Edge Function inicia sessao no Browserless via Puppeteer
3. Edge Function consulta `/sessions` e retorna a URL do DevTools
4. Frontend abre o Chrome DevTools em nova janela
5. Usuario ve a pagina do ERP e pode navegar
6. Ao finalizar, os passos sao gerados pela IA
