
# Plano: Live Preview - Visualização em Tempo Real

## Resumo

Adicionar botão de "Live Preview" que, ao ser clicado durante uma execução ou ao iniciar uma, abre uma janela/modal exibindo a tela do Browserless em tempo real - mostrando o mouse se movendo, cliques acontecendo, etc.

---

## Como Funciona

O Browserless oferece uma API chamada `Browserless.liveURL` que gera um link temporário para visualizar a sessão do navegador em tempo real. Este link pode ser embutido em um iframe ou aberto em nova janela.

```text
+------------------------------------------+
|  [Executar]  [Executar com Live Preview] |
+------------------------------------------+
         |
         v
+------------------------------------------+
|  Modal: Live Preview                     |
+------------------------------------------+
|  +------------------------------------+  |
|  |                                    |  |
|  |   [iframe com a tela do browser]   |  |
|  |   Mouse se movendo em tempo real   |  |
|  |                                    |  |
|  +------------------------------------+  |
|                                          |
|  Status: Executando passo 3 de 8         |
|  [X] Fechar Preview                      |
+------------------------------------------+
```

---

## Arquitetura

### Fluxo de Execução com Live Preview

1. Usuario clica em "Executar com Live Preview"
2. Frontend chama Edge Function `execute-automation`
3. Edge Function conecta ao Browserless via WebSocket
4. Edge Function solicita `Browserless.liveURL` e retorna a URL para o frontend
5. Frontend abre modal/janela com iframe apontando para a liveURL
6. Enquanto executa, Edge Function envia updates de progresso via resposta streaming ou polling
7. Ao finalizar, Edge Function fecha sessao e frontend fecha o preview

---

## Arquivos a Criar

### 1. supabase/functions/execute-automation/index.ts

Nova Edge Function que:
- Recebe ID da automacao e flag `withLivePreview`
- Busca dados da automacao e configuracoes globais do Browserless
- Conecta ao Browserless via puppeteer-core
- Se `withLivePreview=true`, gera liveURL e retorna imediatamente
- Executa os passos sequencialmente
- Salva log de execucao no banco
- Envia dados para webhook se configurado

Tecnologias:
- puppeteer-core (conectar via WebSocket ao Browserless)
- CDP Session para chamar `Browserless.liveURL`

### 2. src/components/automation/LivePreviewModal.tsx

Modal que:
- Recebe a liveURL e a exibe em um iframe
- Mostra status de execucao (passo atual)
- Botao para fechar o preview
- Indicador visual de que esta ao vivo

### 3. src/services/executionService.ts

Novo service para:
- Chamar a Edge Function de execucao
- Gerenciar estado da execucao (polling ou streaming)
- Retornar liveURL para o componente

---

## Arquivos a Modificar

### 1. src/pages/Dashboard.tsx

- Atualizar `handleExecute` para suportar modo com live preview
- Adicionar estado para controlar o modal de live preview
- Passar liveURL para o modal

### 2. src/components/automation/AutomationCard.tsx

- Adicionar botao "Live Preview" ao lado de "Executar"
- Ou transformar "Executar" em dropdown com opcoes:
  - Executar (background)
  - Executar com Live Preview

### 3. src/types/automation.ts

- Adicionar interface `ExecutionSession` com campos:
  - `liveUrl?: string`
  - `executionId: string`
  - `status: 'starting' | 'running' | 'completed' | 'failed'`
  - `currentStep: number`
  - `totalSteps: number`

---

## Detalhes Tecnicos

### Edge Function: execute-automation

```typescript
// Estrutura basica
import puppeteer from 'puppeteer-core';

// 1. Conectar ao Browserless
const browser = await puppeteer.connect({
  browserWSEndpoint: `wss://${browserlessUrl}?token=${token}`
});

const page = await browser.newPage();
const cdp = await page.createCDPSession();

// 2. Gerar LiveURL (se solicitado)
if (withLivePreview) {
  const { liveURL } = await cdp.send('Browserless.liveURL', {
    timeout: 300000, // 5 minutos
    quality: 70,
  });
  // Retornar liveURL para o frontend
}

// 3. Executar passos
for (const step of steps) {
  // navigate, click, type, wait, screenshot, extractTable
}

// 4. Salvar resultados
await browser.close();
```

### LivePreviewModal Component

```typescript
interface LivePreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  liveUrl: string;
  automationName: string;
  currentStep: number;
  totalSteps: number;
  status: 'starting' | 'running' | 'completed' | 'failed';
}
```

### Fluxo de Estados

```text
[Clique no botao]
       |
       v
[Modal abre com "Iniciando..."]
       |
       v
[Edge Function retorna liveURL]
       |
       v
[iframe carrega a sessao ao vivo]
       |
       v
[Polling verifica progresso a cada 2s]
       |
       v
[Execucao completa]
       |
       v
[Modal mostra "Concluido!" com botao fechar]
```

---

## Consideracoes de Seguranca

- A liveURL e temporaria e expira apos o timeout
- Nao requer autenticacao adicional (ja esta na sessao)
- O iframe tem sandbox para seguranca

---

## Ordem de Implementacao

| Passo | Arquivo | Descricao |
|-------|---------|-----------|
| 1 | `execute-automation/index.ts` | Edge Function de execucao com suporte a liveURL |
| 2 | `executionService.ts` | Service para chamar a Edge Function |
| 3 | `LivePreviewModal.tsx` | Modal com iframe para exibir a sessao |
| 4 | `AutomationCard.tsx` | Adicionar botao "Live Preview" |
| 5 | `Dashboard.tsx` | Integrar modal e gerenciar estado |
| 6 | `automation.ts` | Tipos para sessao de execucao |

---

## Resultado Esperado

- Usuario pode clicar em "Live Preview" em qualquer automacao
- Um modal abre mostrando a tela do navegador em tempo real
- O usuario ve o mouse se movendo, campos sendo preenchidos, botoes sendo clicados
- Ao final, o modal mostra o resultado (sucesso/erro)
- O usuario pode fechar o preview a qualquer momento

