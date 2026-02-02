
# Plano: Resolver Tela em Branco do DevTools - Abordagem VNC ou Mudanca de Estrategia

## Diagnostico Completo

### Problema Identificado

A tela do DevTools retorna **erro 403** para `inspector.js` e `favicon.ico`. Apos investigacao profunda na documentacao do Browserless, identifiquei a causa raiz:

1. **A funcao `Browserless.liveURL` via CDP e feature PAGA** - disponivel apenas nos planos pagos do Browserless Cloud ou versao Enterprise
2. **A versao open source (docker image `browserless/chrome`)** nao inclui o sistema de streaming de video e visualizacao ao vivo que o Browserless Cloud oferece
3. **A discussao #4125 no GitHub** mostra outros usuarios com o MESMO problema - e ficou SEM RESPOSTA, confirmando que nao ha suporte oficial para isso na versao gratuita
4. **O endpoint `/devtools/inspector.html`** existe para debugging local, mas nao funciona bem quando acessado remotamente atraves de proxy reverso (Traefik)

### Por que o erro 403 acontece

O Browserless protege os arquivos estaticos do DevTools (`inspector.js`, `favicon.ico`) com autenticacao. Quando voce acessa via URL, o token esta no parametro da URL principal, mas quando o HTML do DevTools tenta carregar os scripts internos, essas requisicoes NAO incluem o token, resultando em 403.

---

## Opcoes de Solucao

### Opcao 1: Migrar para Abordagem Screenshot-Based (Recomendada)

Em vez de tentar visualizar o navegador em tempo real (que requer versao Enterprise), usar uma abordagem baseada em screenshots periodicos. O sistema ja captura screenshots - podemos expandir isso.

**Vantagens:**
- Funciona 100% com versao open source
- Nao requer configuracao adicional no Traefik
- Mais leve em termos de recursos

**Implementacao:**
```text
+-------------------+     +-----------------+     +------------------+
|   Frontend React  | --> | Edge Function   | --> | Browserless      |
|   (RecordingModal)|     | (polling)       |     | (Puppeteer)      |
+-------------------+     +-----------------+     +------------------+
         |                        |                       |
         v                        v                       v
    Mostra imagem           Captura screenshot      Executa acoes
    atualizada a            a cada 2 segundos       do usuario
    cada 2s
```

**Mudancas necessarias:**

| Arquivo | Mudanca |
|---------|---------|
| `start-recording-session/index.ts` | Retornar `wsEndpoint` para reconexao em vez de `liveUrl` |
| `RecordingModal.tsx` | Mostrar preview baseado em screenshots ao inves de iframe DevTools |
| Novo: `get-screenshot/index.ts` | Edge function para capturar screenshot atual |
| `recordingService.ts` | Adicionar funcao para polling de screenshots |

---

### Opcao 2: Usar Docker com VNC (Alternativa)

Substituir Browserless por solucao Chrome + VNC que permite visualizacao remota via noVNC.

```yaml
# Exemplo com selenium/standalone-chrome-debug que tem VNC
image: selenium/standalone-chrome:latest
ports:
  - "4444:4444"  # Selenium
  - "7900:7900"  # noVNC
```

**Desvantagens:**
- Requer mudanca significativa na infraestrutura
- noVNC tem qualidade inferior ao DevTools
- Precisa substituir todo o codigo que usa Puppeteer

---

### Opcao 3: Upgrade para Browserless Enterprise (Mais Simples)

Adquirir licenca Enterprise do Browserless que inclui:
- `Browserless.liveURL` API funcional
- Streaming de video nativo
- Suporte tecnico

**Custo:** Contato com sales@browserless.io

---

## Recomendacao: Opcao 1

A abordagem Screenshot-Based e a mais viavel porque:
1. Funciona com sua infraestrutura atual
2. Nao tem custo adicional
3. Resolve o problema imediatamente
4. O usuario ve o que esta acontecendo (via imagens atualizadas)

---

## Implementacao Detalhada - Opcao 1

### Passo 1: Criar Edge Function para Capturar Screenshots

```typescript
// supabase/functions/get-recording-screenshot/index.ts
serve(async (req) => {
  const { wsEndpoint } = await req.json();
  
  // Reconectar ao browser existente
  const browser = await puppeteer.connect({ browserWSEndpoint: wsEndpoint });
  const pages = await browser.pages();
  const page = pages[pages.length - 1];
  
  // Capturar screenshot
  const screenshot = await page.screenshot({ 
    encoding: 'base64', 
    type: 'jpeg', 
    quality: 60 
  });
  
  const currentUrl = page.url();
  const title = await page.title();
  
  // NAO fechar o browser - manter sessao ativa
  browser.disconnect();
  
  return { screenshot, url: currentUrl, title };
});
```

### Passo 2: Modificar RecordingModal para Mostrar Screenshots

```typescript
// Em vez de abrir DevTools externo, mostrar preview inline
const [previewImage, setPreviewImage] = useState<string | null>(null);

useEffect(() => {
  if (state === 'recording' && session?.wsEndpoint) {
    const interval = setInterval(async () => {
      const result = await getRecordingScreenshot(session.wsEndpoint);
      setPreviewImage(result.screenshot);
    }, 2000);
    
    return () => clearInterval(interval);
  }
}, [state, session]);

// No render:
<div className="aspect-video bg-black rounded-lg overflow-hidden">
  {previewImage ? (
    <img 
      src={`data:image/jpeg;base64,${previewImage}`}
      alt="Preview do navegador"
      className="w-full h-full object-contain"
    />
  ) : (
    <Loader2 className="animate-spin" />
  )}
</div>
```

### Passo 3: Adicionar Botoes de Acao (Clique Virtual)

Como o usuario nao pode interagir diretamente com a imagem, podemos:
1. Detectar cliques na imagem e enviar coordenadas para o Puppeteer
2. Ou manter o modelo atual de descricao manual das acoes

---

## Arquivos a Modificar

| Arquivo | Tipo | Descricao |
|---------|------|-----------|
| `supabase/functions/get-recording-screenshot/index.ts` | NOVO | Edge function para capturar screenshot periodico |
| `supabase/functions/start-recording-session/index.ts` | MODIFICAR | Remover logica de liveUrl, retornar apenas wsEndpoint |
| `src/components/automation/RecordingModal.tsx` | MODIFICAR | Trocar iframe por preview de imagem com polling |
| `src/services/recordingService.ts` | MODIFICAR | Adicionar funcao getRecordingScreenshot |

---

## Resultado Esperado

1. Usuario clica em "Gravar Automacao"
2. Edge Function inicia navegador no Browserless e navega para URL
3. Modal mostra preview em tempo real (imagem atualizada a cada 2s)
4. Mostramos controles na interface para o usuario descrever as acoes
5. Ao finalizar, a IA gera os passos baseado nas descricoes

---

## Pergunta para o Usuario

Antes de implementar, preciso confirmar:

**Voce prefere qual abordagem?**

A) **Screenshot-Based** - Ver preview da tela atualizado a cada 2 segundos na propria interface do Lovable (recomendado)

B) **Upgrade Browserless** - Obter licenca Enterprise para ter o live streaming nativo

C) **VNC** - Trocar toda infraestrutura para usar Chrome + noVNC
