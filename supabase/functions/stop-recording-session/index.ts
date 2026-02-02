import "https://deno.land/x/xhr@0.1.0/mod.ts";
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version',
};

interface StopRecordingRequest {
  sessionId: string;
  erpUrl: string;
  capturedActions: CapturedAction[];
}

interface CapturedAction {
  type: 'click' | 'type' | 'navigate' | 'scroll';
  timestamp: number;
  selector?: string;
  value?: string;
  url?: string;
  description?: string;
  x?: number;
  y?: number;
}

interface AutomationStep {
  order: number;
  action: 'navigate' | 'click' | 'type' | 'wait' | 'waitForSelector' | 'screenshot' | 'extractTable';
  selector?: string;
  value?: string;
  description: string;
  waitTime?: number;
}

serve(async (req: Request) => {
  // Handle CORS preflight
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const lovableApiKey = Deno.env.get('LOVABLE_API_KEY');
    const supabase = createClient(supabaseUrl, supabaseKey);

    const { sessionId, erpUrl, capturedActions }: StopRecordingRequest = await req.json();

    console.log(`[stop-recording] Stopping session: ${sessionId}`);
    console.log(`[stop-recording] ERP URL: ${erpUrl}`);
    console.log(`[stop-recording] Captured actions: ${capturedActions?.length || 0}`);

    // Fetch global Browserless settings
    const { data: settings } = await supabase
      .from('settings')
      .select('key, value')
      .in('key', ['browserless_url', 'browserless_token']);

    const settingsMap = Object.fromEntries(
      (settings || []).map(s => [s.key, s.value])
    );

    const browserlessUrl = settingsMap['browserless_url'];
    const browserlessToken = settingsMap['browserless_token'] || '';

    if (!browserlessUrl) {
      return new Response(
        JSON.stringify({ error: 'URL do Browserless não configurada' }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Clean the browserless URL
    const cleanBrowserlessUrl = browserlessUrl
      .replace('https://', '')
      .replace('http://', '')
      .replace('wss://', '')
      .replace('ws://', '');

    // Take a final screenshot and get the current page state
    const captureScript = `
module.exports = async ({ page }) => {
  await page.goto('${erpUrl}', { waitUntil: 'domcontentloaded', timeout: 30000 });
  
  // Get page HTML for AI analysis
  const html = await page.content();
  
  // Take screenshot
  const screenshot = await page.screenshot({ encoding: 'base64', type: 'jpeg', quality: 70 });
  
  // Get all interactive elements for AI to analyze
  const interactiveElements = await page.evaluate(() => {
    const elements: Array<{
      tag: string;
      id: string;
      className: string;
      text: string;
      type: string;
      name: string;
      placeholder: string;
      selector: string;
    }> = [];
    
    const selectors = 'a, button, input, select, textarea, [onclick], [role="button"]';
    const els = document.querySelectorAll(selectors);
    
    els.forEach((el, index) => {
      const tag = el.tagName.toLowerCase();
      const id = el.id || '';
      const className = el.className || '';
      const text = (el.textContent || '').trim().substring(0, 50);
      const type = el.getAttribute('type') || '';
      const name = el.getAttribute('name') || '';
      const placeholder = el.getAttribute('placeholder') || '';
      
      // Generate a selector
      let selector = tag;
      if (id) {
        selector = '#' + id;
      } else if (name) {
        selector = tag + '[name="' + name + '"]';
      } else if (className && typeof className === 'string') {
        const firstClass = className.split(' ')[0];
        if (firstClass) {
          selector = tag + '.' + firstClass;
        }
      }
      
      elements.push({
        tag,
        id,
        className: typeof className === 'string' ? className : '',
        text,
        type,
        name,
        placeholder,
        selector,
      });
    });
    
    return elements;
  });
  
  return {
    data: {
      success: true,
      screenshot,
      interactiveElements: interactiveElements.slice(0, 100), // Limit to 100 elements
      pageUrl: page.url(),
      pageTitle: await page.title(),
    },
    type: 'application/json'
  };
};
`;

    const browserlessApiUrl = browserlessToken
      ? `https://${cleanBrowserlessUrl}/function?token=${browserlessToken}`
      : `https://${cleanBrowserlessUrl}/function`;

    console.log(`[stop-recording] Capturing final page state...`);

    let pageData = null;
    try {
      const captureResponse = await fetch(browserlessApiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/javascript',
        },
        body: captureScript,
      });

      if (captureResponse.ok) {
        const result = await captureResponse.json();
        pageData = result.data || result;
        console.log(`[stop-recording] Page captured: ${pageData?.pageTitle}`);
      } else {
        console.error(`[stop-recording] Failed to capture page:`, await captureResponse.text());
      }
    } catch (captureError) {
      console.error(`[stop-recording] Capture error:`, captureError);
    }

    // Now use AI to generate automation steps
    if (!lovableApiKey) {
      console.error('[stop-recording] LOVABLE_API_KEY not configured');
      return new Response(
        JSON.stringify({ 
          error: 'AI API key not configured',
          pageData,
        }),
        { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    console.log(`[stop-recording] Generating steps with AI...`);

    // Build the prompt for AI
    const actionsDescription = capturedActions?.map((a, i) => {
      switch (a.type) {
        case 'click':
          return `${i + 1}. Clicou em: ${a.selector || a.description || `posição (${a.x}, ${a.y})`}`;
        case 'type':
          return `${i + 1}. Digitou "${a.value}" em: ${a.selector || a.description}`;
        case 'navigate':
          return `${i + 1}. Navegou para: ${a.url}`;
        case 'scroll':
          return `${i + 1}. Fez scroll na página`;
        default:
          return `${i + 1}. Ação: ${a.type}`;
      }
    }).join('\n') || 'Nenhuma ação capturada - gere passos básicos de navegação';

    const elementsInfo = pageData?.interactiveElements?.slice(0, 30).map((el: any) => 
      `- ${el.tag}${el.id ? '#' + el.id : ''}${el.name ? '[name=' + el.name + ']' : ''}: "${el.text || el.placeholder}"`
    ).join('\n') || '';

    const aiPayload = {
      model: 'google/gemini-3-flash-preview',
      messages: [
        {
          role: 'system',
          content: `Você é um especialista em automação web com Puppeteer/Browserless.
Sua tarefa é analisar as ações do usuário e os elementos da página para gerar passos de automação estruturados.

REGRAS IMPORTANTES:
1. Cada passo deve ter um seletor CSS válido e preciso
2. Priorize seletores por ID (#id) ou name ([name="valor"])
3. Use classes apenas se não houver ID ou name
4. Para campos de login, use {{username}} e {{password}} como placeholders
5. Adicione waits entre ações de navegação
6. Mantenha os passos simples e robustos
7. A primeira ação deve ser navigate para a URL do ERP
8. Adicione waitForSelector antes de cliques em elementos dinâmicos`
        },
        {
          role: 'user',
          content: `URL do ERP: ${erpUrl}
URL atual da página: ${pageData?.pageUrl || erpUrl}
Título da página: ${pageData?.pageTitle || 'Desconhecido'}

AÇÕES GRAVADAS PELO USUÁRIO:
${actionsDescription}

ELEMENTOS INTERATIVOS DISPONÍVEIS NA PÁGINA:
${elementsInfo}

Com base nas ações do usuário e nos elementos da página, gere os passos de automação estruturados.
Se não houver ações, gere pelo menos o passo de navegação inicial.`
        }
      ],
      tools: [
        {
          type: 'function',
          function: {
            name: 'generate_automation_steps',
            description: 'Gera os passos estruturados da automação',
            parameters: {
              type: 'object',
              properties: {
                steps: {
                  type: 'array',
                  items: {
                    type: 'object',
                    properties: {
                      order: { type: 'number', description: 'Ordem do passo (começando em 1)' },
                      action: { 
                        type: 'string', 
                        enum: ['navigate', 'click', 'type', 'wait', 'waitForSelector', 'screenshot', 'extractTable'],
                        description: 'Tipo da ação'
                      },
                      selector: { type: 'string', description: 'Seletor CSS do elemento (se aplicável)' },
                      value: { type: 'string', description: 'Valor para digitar ou URL para navegar' },
                      description: { type: 'string', description: 'Descrição amigável do passo' },
                      waitTime: { type: 'number', description: 'Tempo de espera em ms (para wait/waitForSelector)' }
                    },
                    required: ['order', 'action', 'description']
                  }
                },
                notes: {
                  type: 'string',
                  description: 'Observações ou recomendações sobre a automação gerada'
                }
              },
              required: ['steps']
            }
          }
        }
      ],
      tool_choice: { type: 'function', function: { name: 'generate_automation_steps' } }
    };

    const aiResponse = await fetch('https://ai.gateway.lovable.dev/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${lovableApiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(aiPayload),
    });

    if (!aiResponse.ok) {
      const errorText = await aiResponse.text();
      console.error('[stop-recording] AI error:', errorText);
      
      // Return basic steps if AI fails
      const basicSteps: AutomationStep[] = [
        {
          order: 1,
          action: 'navigate',
          value: erpUrl,
          description: 'Navegar para o ERP',
        }
      ];

      return new Response(
        JSON.stringify({
          success: true,
          steps: basicSteps,
          notes: 'Não foi possível gerar passos com IA. Adicione os passos manualmente.',
          screenshot: pageData?.screenshot,
        }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    const aiResult = await aiResponse.json();
    console.log('[stop-recording] AI response received');

    // Extract the tool call result
    let generatedSteps: AutomationStep[] = [];
    let notes = '';

    const toolCalls = aiResult.choices?.[0]?.message?.tool_calls;
    if (toolCalls && toolCalls.length > 0) {
      const functionCall = toolCalls[0];
      if (functionCall.function?.arguments) {
        try {
          const args = JSON.parse(functionCall.function.arguments);
          generatedSteps = args.steps || [];
          notes = args.notes || '';
          console.log(`[stop-recording] Generated ${generatedSteps.length} steps`);
        } catch (parseError) {
          console.error('[stop-recording] Failed to parse AI response:', parseError);
        }
      }
    }

    // Ensure we have at least a navigate step
    if (generatedSteps.length === 0) {
      generatedSteps = [
        {
          order: 1,
          action: 'navigate',
          value: erpUrl,
          description: 'Navegar para o ERP',
        }
      ];
      notes = 'Passos básicos gerados. Adicione mais passos manualmente.';
    }

    return new Response(
      JSON.stringify({
        success: true,
        sessionId,
        steps: generatedSteps,
        notes,
        screenshot: pageData?.screenshot,
        pageUrl: pageData?.pageUrl,
        pageTitle: pageData?.pageTitle,
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('[stop-recording] Unexpected error:', error);
    return new Response(
      JSON.stringify({ error: errorMessage }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
});
