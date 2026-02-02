import "https://deno.land/x/xhr@0.1.0/mod.ts";
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import puppeteer from "https://deno.land/x/puppeteer@16.2.0/mod.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version',
};

interface StartRecordingRequest {
  erpUrl: string;
}

interface BrowserlessSession {
  browserId: string;
  devtoolsFrontendUrl: string;
  port?: number;
  url?: string;
}

serve(async (req: Request) => {
  // Handle CORS preflight
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders });
  }

  let browser: any = null;

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

    // Clean the browserless URL (remove protocol)
    const cleanBrowserlessUrl = browserlessUrl
      .replace('https://', '')
      .replace('http://', '')
      .replace('wss://', '')
      .replace('ws://', '');

    console.log(`[start-recording] Connecting to Browserless: ${cleanBrowserlessUrl}`);

    // Build WebSocket URL for puppeteer connection
    // Use headless=false to allow interactive session viewing
    const wsEndpoint = browserlessToken
      ? `wss://${cleanBrowserlessUrl}?token=${browserlessToken}&headless=false`
      : `wss://${cleanBrowserlessUrl}?headless=false`;

    console.log(`[start-recording] WebSocket endpoint: ${wsEndpoint}`);

    // Connect to Browserless via Puppeteer
    browser = await puppeteer.connect({
      browserWSEndpoint: wsEndpoint,
    });

    console.log(`[start-recording] Connected to browser`);

    // Create a new page and navigate to ERP URL
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 720 });

    console.log(`[start-recording] Navigating to: ${erpUrl}`);
    await page.goto(erpUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });

    // Get page info after navigation
    const pageUrl = page.url();
    const pageTitle = await page.title();
    console.log(`[start-recording] Page loaded: ${pageTitle}`);

    // Take initial screenshot
    const screenshot = await page.screenshot({ encoding: 'base64', type: 'jpeg', quality: 70 });
    console.log(`[start-recording] Screenshot taken`);

    // Query /sessions API to get devtoolsFrontendUrl
    const sessionsUrl = browserlessToken
      ? `https://${cleanBrowserlessUrl}/sessions?token=${browserlessToken}`
      : `https://${cleanBrowserlessUrl}/sessions`;

    console.log(`[start-recording] Fetching sessions from: ${sessionsUrl}`);

    const sessionsResponse = await fetch(sessionsUrl);
    
    if (!sessionsResponse.ok) {
      const errorText = await sessionsResponse.text();
      console.error(`[start-recording] Sessions API error:`, errorText);
      throw new Error(`Erro ao buscar sessões: ${sessionsResponse.status}`);
    }

    const sessions: BrowserlessSession[] = await sessionsResponse.json();
    console.log(`[start-recording] Found ${sessions.length} active sessions`);

    // Find the session for our browser
    // Match by URL containing the ERP hostname
    const erpHostname = new URL(erpUrl).hostname;
    let currentSession = sessions.find(s => s.url?.includes(erpHostname));
    
    // If not found by URL, take the most recent session
    if (!currentSession && sessions.length > 0) {
      currentSession = sessions[0];
    }

    if (!currentSession) {
      throw new Error('Sessão do navegador não encontrada');
    }

    console.log(`[start-recording] Found session:`, currentSession.browserId);

    // Build the DevTools URL for live viewing
    // The devtoolsFrontendUrl is like: /devtools/inspector.html?wss=host/devtools/page/PAGE_ID
    const devtoolsPath = currentSession.devtoolsFrontendUrl;
    
    // Construct the full URL
    // Add token if needed
    let liveUrl = `https://${cleanBrowserlessUrl}${devtoolsPath}`;
    if (browserlessToken) {
      // Add token to the URL if not already present
      liveUrl = liveUrl.includes('?') 
        ? `${liveUrl}&token=${browserlessToken}`
        : `${liveUrl}?token=${browserlessToken}`;
    }

    console.log(`[start-recording] Live URL: ${liveUrl}`);

    // IMPORTANT: Do NOT close the browser - the session needs to stay active!
    // The browser will be closed when stop-recording is called
    
    // Store the browser wsEndpoint for later reconnection
    const browserWsEndpoint = browser.wsEndpoint();

    return new Response(
      JSON.stringify({
        success: true,
        sessionId: currentSession.browserId,
        liveUrl,
        wsEndpoint: browserWsEndpoint,
        erpUrl,
        initialScreenshot: screenshot,
        pageInfo: {
          url: pageUrl,
          title: pageTitle,
        },
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('[start-recording] Unexpected error:', error);

    // Close browser on error
    if (browser) {
      try {
        await browser.close();
      } catch (closeError) {
        console.error('[start-recording] Error closing browser:', closeError);
      }
    }

    return new Response(
      JSON.stringify({ error: errorMessage }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
});
