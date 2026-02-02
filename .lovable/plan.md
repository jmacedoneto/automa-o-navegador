
# Plano: Modo de Gravacao - Aprendizado por Observacao

## Resumo

Criar um modo "Gravar Automacao" onde o usuario assume o controle do navegador remotamente, faz as acoes manualmente (cliques, digitacao, navegacao), e a IA observa todas as interacoes para gerar automaticamente os passos de automacao.

---

## Como Funciona

```text
+------------------------------------------+
|  [Criar Nova Automacao]                  |
|  [Gravar Nova Automacao]  <-- NOVO       |
+------------------------------------------+
         |
         v
+------------------------------------------+
|  Modal: Gravar Automacao                 |
+------------------------------------------+
|  URL inicial do ERP: [_____________]     |
|  [Iniciar Gravacao]                      |
+------------------------------------------+
         |
         v
+------------------------------------------+
|  Modal: Gravacao em Andamento            |
+------------------------------------------+
|  +------------------------------------+  |
|  |                                    |  |
|  |  [iframe/janela com liveURL]       |  |
|  |  Usuario interage diretamente      |  |
|  |                                    |  |
|  +------------------------------------+  |
|                                          |
|  Status: Gravando...                     |
|  Acoes capturadas: 12                    |
|                                          |
|  [Finalizar Gravacao]                    |
+------------------------------------------+
         |
         v
+------------------------------------------+
|  Modal: Gerando Passos                   |
+------------------------------------------+
|  A IA esta analisando suas acoes...      |
|  [Barra de progresso]                    |
+------------------------------------------+
         |
         v
+------------------------------------------+
|  Editor de Automacao                     |
+------------------------------------------+
|  Passos gerados automaticamente!         |
|  1. Navegar para URL                     |
|  2. Clicar em #login-button              |
|  3. Digitar em #username                 |
|  ...                                     |
+------------------------------------------+
```

---

## Arquitetura Tecnica

### Fluxo de Gravacao

1. Usuario clica em "Gravar Nova Automacao"
2. Frontend chama Edge Function `start-recording-session`
3. Edge Function conecta ao Browserless via Puppeteer:
   - Ativa `replay=true` para capturar eventos DOM/RRWeb
   - Gera `liveURL` para o usuario interagir
   - Configura listeners CDP para capturar eventos de input
4. Usuario interage com a pagina via liveURL
5. Backend captura todas as interacoes:
   - Cliques (Input.dispatchMouseEvent)
   - Digitacao (Input.dispatchKeyEvent)
   - Navegacao (Page.navigate)
   - Scrolls, hovers, etc.
6. Usuario clica "Finalizar"
7. Frontend chama Edge Function `stop-recording-session`
8. Edge Function:
   - Para a gravacao
   - Coleta todos os eventos capturados
   - Envia para IA analisar
   - IA gera passos estruturados
9. Frontend recebe os passos e abre o Editor

---

## Arquivos a Criar

### 1. supabase/functions/start-recording-session/index.ts

Edge Function que:
- Recebe a URL inicial do ERP
- Conecta ao Browserless com `replay=true` e `headless=false`
- Cria sessao CDP e configura listeners de eventos
- Gera liveURL interativo
- Cria registro de sessao de gravacao no banco
- Retorna:
  - `sessionId`: ID da sessao de gravacao
  - `liveUrl`: URL para o usuario interagir
  - `wsEndpoint`: Para reconexao (se necessario)

### 2. supabase/functions/stop-recording-session/index.ts

Edge Function que:
- Recebe o `sessionId`
- Para a gravacao via CDP
- Coleta todos os eventos capturados (cliques, digitacao, navegacao)
- Envia eventos + screenshots para IA (Gemini Vision)
- IA analisa e gera passos estruturados
- Fecha o navegador
- Retorna os passos gerados

### 3. src/components/automation/RecordingModal.tsx

Modal de gravacao que:
- Campo para URL inicial do ERP
- Botao "Iniciar Gravacao"
- Exibe iframe/link para liveURL
- Contador de acoes capturadas
- Botao "Finalizar Gravacao"
- Indicador de processamento da IA

### 4. src/services/recordingService.ts

Service para:
- Iniciar sessao de gravacao
- Parar sessao e obter passos
- Gerenciar estado da gravacao

---

## Arquivos a Modificar

### 1. src/pages/Dashboard.tsx

- Adicionar botao "Gravar Nova Automacao"
- Estado para controlar o modal de gravacao
- Handler para receber passos gerados e criar automacao

### 2. src/pages/AutomationEditor.tsx

- Receber passos pre-populados via state do router
- Permitir que o usuario edite os passos gerados

---

## Detalhes Tecnicos

### Edge Function: start-recording-session

```typescript
// Estrutura basica
const browser = await puppeteer.connect({
  browserWSEndpoint: `wss://${url}?token=${token}&replay=true&headless=false`
});

const page = await browser.newPage();
const cdp = await page.createCDPSession();

// Navegar para URL inicial
await page.goto(erpUrl, { waitUntil: 'networkidle2' });

// Gerar liveURL interativo
const { liveURL } = await cdp.send('Browserless.liveURL', {
  timeout: 600000, // 10 minutos
  interactable: true,
  quality: 70,
});

// Configurar captura de eventos via Page
// Os eventos serao coletados pelo RRWeb automaticamente
// Quando o usuario fechar, teremos o replay completo
```

### Edge Function: stop-recording-session

```typescript
// Parar gravacao e coletar dados
const recording = await cdp.send('Browserless.stopSessionRecording');

// Capturar screenshot final
const screenshot = await page.screenshot({ encoding: 'base64' });

// Coletar dados da pagina atual
const pageContent = await page.content();
const pageUrl = page.url();

// Enviar para IA analisar
const aiResponse = await fetch('https://ai.gateway.lovable.dev/v1/chat/completions', {
  body: JSON.stringify({
    model: 'google/gemini-3-flash-preview',
    messages: [{
      role: 'system',
      content: `Voce e um especialista em automacao web.
        Analise a gravacao de sessao e o HTML da pagina.
        Gere passos de automacao estruturados.`
    }, {
      role: 'user',
      content: [{
        type: 'text',
        text: `Eventos gravados: ${JSON.stringify(events)}
               URL final: ${pageUrl}
               Gere os passos de automacao.`
      }, {
        type: 'image_url',
        image_url: { url: `data:image/png;base64,${screenshot}` }
      }]
    }],
    tools: [{
      type: 'function',
      function: {
        name: 'generate_automation_steps',
        parameters: {
          type: 'object',
          properties: {
            steps: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  order: { type: 'number' },
                  action: { type: 'string', enum: ['navigate', 'click', 'type', 'wait', 'waitForSelector', 'screenshot', 'extractTable'] },
                  selector: { type: 'string' },
                  value: { type: 'string' },
                  description: { type: 'string' }
                }
              }
            }
          }
        }
      }
    }],
    tool_choice: { type: 'function', function: { name: 'generate_automation_steps' } }
  })
});
```

### RecordingModal Component

```typescript
interface RecordingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStepsGenerated: (steps: AutomationStep[], erpUrl: string) => void;
}

// Estados:
// 'idle' -> Aguardando URL inicial
// 'starting' -> Iniciando sessao
// 'recording' -> Gravando (mostra liveURL)
// 'processing' -> IA analisando
// 'complete' -> Passos gerados
```

---

## Fluxo de Estados

```text
[Dashboard]
    |
    | Clica "Gravar Nova Automacao"
    v
[RecordingModal: idle]
    |
    | Insere URL e clica "Iniciar"
    v
[RecordingModal: starting]
    |
    | Edge Function retorna liveURL
    v
[RecordingModal: recording]
    |
    | Usuario interage, clica "Finalizar"
    v
[RecordingModal: processing]
    |
    | IA gera passos
    v
[RecordingModal: complete]
    |
    | onStepsGenerated(steps)
    v
[AutomationEditor com passos pre-populados]
```

---

## Consideracoes Importantes

### Captura de Eventos

O Browserless com `replay=true` grava automaticamente:
- Movimentos do mouse
- Cliques
- Digitacao
- Scrolls
- Navegacoes
- Mutacoes DOM

Esses dados sao armazenados no dashboard do Browserless e podem ser acessados via API para analise.

### Alternativa: Captura via CDP

Se a captura via replay nao for suficiente, podemos usar o Chrome DevTools Protocol diretamente:

```javascript
// Escutar eventos de input
cdp.on('Input.dispatchMouseEvent', (event) => {
  capturedEvents.push({ type: 'mouse', ...event });
});

cdp.on('Input.dispatchKeyEvent', (event) => {
  capturedEvents.push({ type: 'key', ...event });
});
```

### Geracao de Seletores

A IA analisara:
1. O HTML da pagina
2. Os eventos capturados
3. Os screenshots

Para gerar seletores robustos:
- Priorizar IDs quando disponiveis
- Usar data-attributes
- Fallback para classes CSS
- XPath como ultimo recurso

---

## Analise da Stack Atual

Sua configuracao do Browserless esta **quase completa**. O que voce tem:

| Funcionalidade | Status |
|----------------|--------|
| TOKEN de autenticacao | OK |
| MAX_CONCURRENT_SESSIONS | OK |
| PREBOOT_CHROME | OK |
| KEEP_ALIVE | OK |
| SSL via Traefik | OK |

### O que falta para gravacao

Voce precisa adicionar estas variaveis de ambiente:

```yaml
environment:
  # ... configuracoes existentes ...
  
  # Habilitar modo headful para gravacao interativa
  - HEADLESS=false
  
  # Permitir sessoes mais longas para gravacao
  - DEFAULT_BLOCK_ADS=true
  - DEFAULT_STEALTH=true
  
  # Importante: permitir replay
  - ENABLE_API_GET=true
```

### Observacao sobre Session Replay

O **Session Replay** (com replay=true) requer um plano pago do Browserless Cloud. Como voce esta usando self-hosted, a captura de eventos sera feita via:
1. CDP listeners para eventos de input
2. Puppeteer page events
3. Screenshots periodicos

---

## Ordem de Implementacao

| Passo | Arquivo | Descricao |
|-------|---------|-----------|
| 1 | `start-recording-session/index.ts` | Edge Function para iniciar gravacao |
| 2 | `stop-recording-session/index.ts` | Edge Function para parar e gerar passos |
| 3 | `recordingService.ts` | Service frontend |
| 4 | `RecordingModal.tsx` | Modal de gravacao |
| 5 | `Dashboard.tsx` | Adicionar botao e integracao |
| 6 | `AutomationEditor.tsx` | Receber passos pre-populados |

---

## Resultado Esperado

- Botao "Gravar Nova Automacao" no Dashboard
- Usuario abre o browser remoto e faz as acoes manualmente
- Ao finalizar, a IA analisa e gera os passos automaticamente
- Usuario revisa e edita os passos no Editor
- Automacao pronta para uso!
