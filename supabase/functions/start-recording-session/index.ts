import "https://deno.land/x/xhr@0.1.0/mod.ts";
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version',
};

interface StartRecordingRequest {
  erpUrl: string;
}

serve(async (req: Request) => {
  // Handle CORS preflight
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    const { erpUrl }: StartRecordingRequest = await req.json();

    if (!erpUrl) {
      return new Response(
        JSON.stringify({ error: 'URL do ERP é obrigatória' }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    console.log(`[start-recording] Starting recording session for URL: ${erpUrl}`);

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
        JSON.stringify({ error: 'URL do Browserless não configurada nas configurações' }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Clean the browserless URL
    const cleanBrowserlessUrl = browserlessUrl
      .replace('https://', '')
      .replace('http://', '')
      .replace('wss://', '')
      .replace('ws://', '');

    // Generate a unique session ID
    const sessionId = crypto.randomUUID();

    // Build the live viewer URL with the initial URL
    // Browserless /live endpoint opens an interactive browser session
    const encodedUrl = encodeURIComponent(erpUrl);
    
    // The live URL format for Browserless - navigates directly to the ERP
    const liveUrl = browserlessToken
      ? `https://${cleanBrowserlessUrl}/live?token=${browserlessToken}&--url=${encodedUrl}`
      : `https://${cleanBrowserlessUrl}/live?--url=${encodedUrl}`;

    // WebSocket endpoint for potential CDP interaction
    const wsEndpoint = browserlessToken
      ? `wss://${cleanBrowserlessUrl}?token=${browserlessToken}`
      : `wss://${cleanBrowserlessUrl}`;

    console.log(`[start-recording] Session ID: ${sessionId}`);
    console.log(`[start-recording] Live URL: ${liveUrl}`);

    // Create a simple function to start capturing network/DOM state
    // We'll use Browserless /function API to set up the browser and return info
    const initScript = `
module.exports = async ({ page, context }) => {
  // Navigate to the ERP URL
  await page.goto('${erpUrl}', { waitUntil: 'domcontentloaded', timeout: 30000 });
  
  // Get initial page info
  const pageInfo = {
    url: page.url(),
    title: await page.title(),
  };
  
  // Take initial screenshot
  const screenshot = await page.screenshot({ encoding: 'base64', type: 'jpeg', quality: 70 });
  
  return {
    data: {
      success: true,
      pageInfo,
      initialScreenshot: screenshot,
    },
    type: 'application/json'
  };
};
`;

    // Start a browser session to get initial state
    const browserlessApiUrl = browserlessToken
      ? `https://${cleanBrowserlessUrl}/function?token=${browserlessToken}`
      : `https://${cleanBrowserlessUrl}/function`;

    console.log(`[start-recording] Initializing browser session...`);

    const initResponse = await fetch(browserlessApiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/javascript',
      },
      body: initScript,
    });

    let initialData = null;
    let initError = null;

    if (initResponse.ok) {
      const result = await initResponse.json();
      initialData = result.data || result;
      console.log(`[start-recording] Initial page loaded: ${initialData?.pageInfo?.title}`);
    } else {
      const errorText = await initResponse.text();
      initError = errorText;
      console.error(`[start-recording] Failed to initialize browser:`, errorText);
    }

    return new Response(
      JSON.stringify({
        success: true,
        sessionId,
        liveUrl,
        wsEndpoint,
        erpUrl,
        initialScreenshot: initialData?.initialScreenshot,
        pageInfo: initialData?.pageInfo,
        initError,
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('[start-recording] Unexpected error:', error);
    return new Response(
      JSON.stringify({ error: errorMessage }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
});
