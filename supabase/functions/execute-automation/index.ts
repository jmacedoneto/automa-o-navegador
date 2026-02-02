import "https://deno.land/x/xhr@0.1.0/mod.ts";
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import puppeteer from "https://deno.land/x/puppeteer@16.2.0/mod.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

interface AutomationStep {
  order: number;
  action: 'navigate' | 'click' | 'type' | 'wait' | 'waitForSelector' | 'screenshot' | 'extractTable';
  selector?: string;
  value?: string;
  description: string;
  waitTime?: number;
}

interface ExecuteRequest {
  automationId: string;
  withLivePreview?: boolean;
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

  try {
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    const { automationId, withLivePreview = false }: ExecuteRequest = await req.json();

    console.log(`[execute-automation] Starting execution for automation: ${automationId}, livePreview: ${withLivePreview}`);

    // Fetch automation data
    const { data: automation, error: automationError } = await supabase
      .from('automations')
      .select('*')
      .eq('id', automationId)
      .single();

    if (automationError || !automation) {
      console.error('[execute-automation] Automation not found:', automationError);
      return new Response(
        JSON.stringify({ error: 'Automação não encontrada' }),
        { status: 404, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Fetch global Browserless settings
    const { data: settings } = await supabase
      .from('settings')
      .select('key, value')
      .in('key', ['browserless_url', 'browserless_token']);

    const settingsMap = Object.fromEntries(
      (settings || []).map(s => [s.key, s.value])
    );

    const browserlessUrl = settingsMap['browserless_url'] || automation.browserless_url;
    const browserlessToken = settingsMap['browserless_token'] || '';

    if (!browserlessUrl) {
      return new Response(
        JSON.stringify({ error: 'URL do Browserless não configurada' }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    console.log(`[execute-automation] Using Browserless URL: ${browserlessUrl}`);

    const steps: AutomationStep[] = automation.steps || [];
    const credentials = automation.credentials as { username?: string; password?: string } | null;

    // Create execution log
    const { data: executionLog, error: logError } = await supabase
      .from('execution_logs')
      .insert({
        automation_id: automationId,
        started_at: new Date().toISOString(),
        status: 'running',
        steps_completed: 0,
        total_steps: steps.length,
        screenshots: [],
        extracted_data: {},
      })
      .select()
      .single();

    if (logError) {
      console.error('[execute-automation] Failed to create execution log:', logError);
    }

    const executionId = executionLog?.id;

    // Clean the browserless URL (remove protocol if present)
    const cleanBrowserlessUrl = browserlessUrl
      .replace('https://', '')
      .replace('http://', '')
      .replace('wss://', '')
      .replace('ws://', '');

    let liveUrl: string | null = null;

    if (withLivePreview) {
      // For live preview, we'll connect via puppeteer and then fetch the DevTools URL
      console.log(`[execute-automation] Setting up live preview...`);

      // Build WebSocket URL for puppeteer connection
      const wsEndpoint = browserlessToken
        ? `wss://${cleanBrowserlessUrl}?token=${browserlessToken}&headless=false`
        : `wss://${cleanBrowserlessUrl}?headless=false`;

      // We'll start execution and return the live URL
      // The execution happens in background
      executeBrowserlessWithPuppeteer(
        cleanBrowserlessUrl,
        browserlessToken,
        steps,
        automation.erp_url,
        credentials,
        supabase,
        executionId,
        automationId,
        automation.webhook_url,
        automation.webhook_secret,
        true // withLivePreview
      ).then(async (result) => {
        console.log(`[execute-automation] Background execution completed:`, result.success);
      }).catch(err => {
        console.error('[execute-automation] Background execution error:', err);
      });

      // Query sessions to get devtoolsFrontendUrl for the live preview
      // First, wait a bit for the browser to start
      await new Promise(r => setTimeout(r, 2000));

      const sessionsUrl = browserlessToken
        ? `https://${cleanBrowserlessUrl}/sessions?token=${browserlessToken}`
        : `https://${cleanBrowserlessUrl}/sessions`;

      try {
        const sessionsResponse = await fetch(sessionsUrl);
        if (sessionsResponse.ok) {
          const sessions: BrowserlessSession[] = await sessionsResponse.json();
          if (sessions.length > 0) {
            const session = sessions[0];
            // Replace internal Docker addresses with public hostname
            let devtoolsPath = session.devtoolsFrontendUrl
              .replace(/ws=0\.0\.0\.0:\d+/g, `ws=${cleanBrowserlessUrl}`)
              .replace(/ws=localhost:\d+/g, `ws=${cleanBrowserlessUrl}`)
              .replace(/wss=0\.0\.0\.0:\d+/g, `wss=${cleanBrowserlessUrl}`)
              .replace(/wss=localhost:\d+/g, `wss=${cleanBrowserlessUrl}`);
            
            liveUrl = `https://${cleanBrowserlessUrl}${devtoolsPath}`;
            if (browserlessToken) {
              liveUrl = liveUrl.includes('?')
                ? `${liveUrl}&token=${browserlessToken}`
                : `${liveUrl}?token=${browserlessToken}`;
            }
          }
        }
      } catch (e) {
        console.error('[execute-automation] Failed to get live URL:', e);
      }

      console.log(`[execute-automation] Live preview URL: ${liveUrl}`);

      return new Response(
        JSON.stringify({
          success: true,
          executionId,
          liveUrl,
          totalSteps: steps.length,
        }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Regular execution (blocking) using Puppeteer
    const result = await executeBrowserlessWithPuppeteer(
      cleanBrowserlessUrl,
      browserlessToken,
      steps,
      automation.erp_url,
      credentials,
      supabase,
      executionId,
      automationId,
      automation.webhook_url,
      automation.webhook_secret,
      false
    );

    return new Response(
      JSON.stringify({
        success: result.success,
        executionId,
        stepsCompleted: result.stepsCompleted,
        extractedData: result.extractedData,
        screenshots: result.screenshots,
        error: result.error,
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('[execute-automation] Unexpected error:', error);
    return new Response(
      JSON.stringify({ error: errorMessage }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
});

async function executeBrowserlessWithPuppeteer(
  cleanBrowserlessUrl: string,
  browserlessToken: string,
  steps: AutomationStep[],
  erpUrl: string,
  credentials: { username?: string; password?: string } | null,
  supabase: any,
  executionId: string | undefined,
  automationId: string,
  webhookUrl?: string | null,
  webhookSecret?: string | null,
  withLivePreview: boolean = false
): Promise<{
  success: boolean;
  stepsCompleted: number;
  extractedData: Record<string, unknown>;
  screenshots: string[];
  error?: string;
}> {
  let browser: any = null;

  try {
    console.log('[execute-automation] Connecting to Browserless via Puppeteer...');

    // Build WebSocket URL
    const wsEndpoint = browserlessToken
      ? `wss://${cleanBrowserlessUrl}?token=${browserlessToken}${withLivePreview ? '&headless=false' : ''}`
      : `wss://${cleanBrowserlessUrl}${withLivePreview ? '?headless=false' : ''}`;

    browser = await puppeteer.connect({
      browserWSEndpoint: wsEndpoint,
    });

    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 720 });

    const results = {
      stepsCompleted: 0,
      screenshots: [] as string[],
      extractedData: {} as Record<string, unknown>,
      errors: [] as { step: number; error: string }[],
    };

    // Navigate to ERP URL first
    console.log(`[execute-automation] Navigating to: ${erpUrl}`);
    await page.goto(erpUrl, { waitUntil: 'networkidle2', timeout: 30000 });

    // Execute each step
    for (const step of steps) {
      try {
        console.log(`[execute-automation] Executing step ${step.order}: ${step.action} - ${step.description}`);

        switch (step.action) {
          case 'navigate':
            await page.goto(step.value!, { waitUntil: 'networkidle2', timeout: 30000 });
            break;

          case 'click':
            await page.waitForSelector(step.selector!, { timeout: 10000 });
            await page.click(step.selector!);
            break;

          case 'type':
            await page.waitForSelector(step.selector!, { timeout: 10000 });
            let valueToType = step.value || '';
            // Replace credential placeholders
            if (credentials) {
              if (valueToType === '{{username}}') valueToType = credentials.username || '';
              if (valueToType === '{{password}}') valueToType = credentials.password || '';
            }
            await page.type(step.selector!, valueToType, { delay: 50 });
            break;

          case 'wait':
            await new Promise(r => setTimeout(r, step.waitTime || 1000));
            break;

          case 'waitForSelector':
            await page.waitForSelector(step.selector!, { timeout: step.waitTime || 10000 });
            break;

          case 'screenshot':
            const screenshot = await page.screenshot({ encoding: 'base64' });
            results.screenshots.push(screenshot);
            break;

          case 'extractTable':
            const tableData = await page.evaluate((selector: string) => {
              const table = (globalThis as any).document.querySelector(selector);
              if (!table) return null;

              const rows = Array.from(table.querySelectorAll('tr'));
              return rows.map((row: any) => {
                const cells = Array.from(row.querySelectorAll('td, th'));
                return cells.map((cell: any) => cell.textContent?.trim() || '');
              });
            }, step.selector!);
            results.extractedData[step.description || 'table_' + step.order] = tableData;
            break;
        }

        results.stepsCompleted++;
        console.log(`[execute-automation] Step ${step.order} completed`);

        // Small delay between steps for stability
        await new Promise(r => setTimeout(r, 300));

      } catch (stepError) {
        const errorMsg = stepError instanceof Error ? stepError.message : 'Unknown error';
        console.error(`[execute-automation] Step ${step.order} error:`, errorMsg);
        results.errors.push({ step: step.order, error: errorMsg });
        // Continue with next step even if one fails
      }
    }

    // Close browser
    await browser.close();
    browser = null;

    const success = results.errors.length === 0 || results.stepsCompleted === steps.length;
    const errorMessage = results.errors.length > 0 ? results.errors.map(e => e.error).join('; ') : undefined;

    // Update execution log
    if (executionId) {
      await supabase
        .from('execution_logs')
        .update({
          finished_at: new Date().toISOString(),
          status: success ? 'success' : 'failed',
          steps_completed: results.stepsCompleted,
          screenshots: results.screenshots,
          extracted_data: results.extractedData,
          error_message: errorMessage,
        })
        .eq('id', executionId);
    }

    // Update automation last execution
    await supabase
      .from('automations')
      .update({
        last_execution_at: new Date().toISOString(),
        last_execution_status: success ? 'success' : 'failed',
      })
      .eq('id', automationId);

    // Call webhook if configured
    if (webhookUrl) {
      try {
        const webhookPayload = {
          automationId,
          executionId,
          status: success ? 'success' : 'failed',
          stepsCompleted: results.stepsCompleted,
          totalSteps: steps.length,
          extractedData: results.extractedData,
          timestamp: new Date().toISOString(),
        };

        const webhookHeaders: Record<string, string> = {
          'Content-Type': 'application/json',
        };

        if (webhookSecret) {
          webhookHeaders['X-Webhook-Secret'] = webhookSecret;
        }

        const webhookResponse = await fetch(webhookUrl, {
          method: 'POST',
          headers: webhookHeaders,
          body: JSON.stringify(webhookPayload),
        });

        console.log('[execute-automation] Webhook response:', webhookResponse.status);

        if (executionId) {
          await supabase
            .from('execution_logs')
            .update({
              webhook_response: {
                status: webhookResponse.status,
                ok: webhookResponse.ok,
              },
            })
            .eq('id', executionId);
        }
      } catch (webhookError) {
        console.error('[execute-automation] Webhook error:', webhookError);
      }
    }

    return {
      success,
      stepsCompleted: results.stepsCompleted,
      extractedData: results.extractedData,
      screenshots: results.screenshots,
      error: errorMessage,
    };

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('[execute-automation] Execution failed:', error);

    // Close browser on error
    if (browser) {
      try {
        await browser.close();
      } catch (closeError) {
        console.error('[execute-automation] Error closing browser:', closeError);
      }
    }

    // Update logs on failure
    if (executionId) {
      await supabase
        .from('execution_logs')
        .update({
          finished_at: new Date().toISOString(),
          status: 'failed',
          error_message: errorMessage,
        })
        .eq('id', executionId);
    }

    await supabase
      .from('automations')
      .update({
        last_execution_at: new Date().toISOString(),
        last_execution_status: 'failed',
      })
      .eq('id', automationId);

    return {
      success: false,
      stepsCompleted: 0,
      extractedData: {},
      screenshots: [],
      error: errorMessage,
    };
  }
}
