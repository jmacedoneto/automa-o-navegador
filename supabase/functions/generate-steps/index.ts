import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version',
};

serve(async (req) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders });
  }

  try {
    const { instructions, erpUrl } = await req.json();

    if (!instructions) {
      return new Response(
        JSON.stringify({ error: 'Instructions are required' }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");
    if (!LOVABLE_API_KEY) {
      throw new Error("LOVABLE_API_KEY is not configured");
    }

    console.log("Generating steps for instructions:", instructions);

    const systemPrompt = `Você é um especialista em automação web. O usuário vai descrever o que ele quer fazer em um sistema ERP e você deve converter isso em uma lista estruturada de passos para automação com Puppeteer/Browserless.

Cada passo deve ter:
- order: número sequencial do passo
- action: tipo de ação (navigate, click, type, wait, waitForSelector, screenshot, extractTable)
- selector: seletor CSS ou XPath do elemento (se aplicável)
- value: valor a ser digitado (se action for "type")
- description: descrição do que o passo faz em português
- waitTime: tempo de espera em ms após a ação (opcional, default 1000)

Ações disponíveis:
- navigate: navegar para uma URL
- click: clicar em um elemento
- type: digitar texto em um campo
- wait: aguardar um tempo específico
- waitForSelector: aguardar um elemento aparecer
- screenshot: tirar screenshot da página
- extractTable: extrair dados de uma tabela

IMPORTANTE:
- Use seletores genéricos quando não souber o seletor exato (ex: 'input[type="text"]', 'button:contains("Entrar")')
- Sempre inclua esperas adequadas entre ações
- Para login, use placeholders como {{username}} e {{password}}
- Seja específico nas descrições para que o usuário possa ajustar depois

Retorne APENAS um JSON válido com a estrutura:
{
  "steps": [
    { "order": 1, "action": "...", "selector": "...", "value": "...", "description": "...", "waitTime": 1000 }
  ],
  "notes": "Observações importantes sobre a automação"
}`;

    const response = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${LOVABLE_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "google/gemini-3-flash-preview",
        messages: [
          { role: "system", content: systemPrompt },
          { 
            role: "user", 
            content: `URL do ERP: ${erpUrl || 'não informada'}\n\nInstruções do usuário:\n${instructions}` 
          },
        ],
      }),
    });

    if (!response.ok) {
      if (response.status === 429) {
        return new Response(
          JSON.stringify({ error: "Rate limit exceeded. Please try again later." }),
          { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      if (response.status === 402) {
        return new Response(
          JSON.stringify({ error: "Payment required. Please add credits to your workspace." }),
          { status: 402, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      const errorText = await response.text();
      console.error("AI gateway error:", response.status, errorText);
      throw new Error(`AI gateway error: ${response.status}`);
    }

    const aiResponse = await response.json();
    console.log("AI response received");

    const content = aiResponse.choices?.[0]?.message?.content;
    if (!content) {
      throw new Error("No content in AI response");
    }

    // Parse the JSON from the AI response
    let parsedContent;
    try {
      // Try to extract JSON from the response
      const jsonMatch = content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        parsedContent = JSON.parse(jsonMatch[0]);
      } else {
        throw new Error("No JSON found in response");
      }
    } catch (parseError) {
      console.error("Failed to parse AI response:", content);
      throw new Error("Failed to parse AI response as JSON");
    }

    return new Response(
      JSON.stringify(parsedContent),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );

  } catch (error) {
    console.error("Error in generate-steps:", error);
    return new Response(
      JSON.stringify({ error: error instanceof Error ? error.message : "Unknown error" }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
});
