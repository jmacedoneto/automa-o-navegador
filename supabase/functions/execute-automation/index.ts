import "https://deno.land/x/xhr@0.1.0/mod.ts";
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";

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

    // Build the Browserless API request
    // For live preview, we use the /live endpoint which returns a viewer URL
    // For regular execution, we use the /function endpoint

    let liveUrl: string | null = null;
    
    // Clean the browserless URL (remove protocol if present)
    const cleanBrowserlessUrl = browserlessUrl
      .replace('https://', '')
      .replace('http://', '')
      .replace('wss://', '')
      .replace('ws://', '');

    if (withLivePreview) {
      // For live preview, we need to use the Browserless /live API
      // This returns a URL that can be embedded in an iframe
      
      // Build the websocket URL for puppeteer connection
      const wsEndpoint = browserlessToken 
        ? `wss://${cleanBrowserlessUrl}?token=${browserlessToken}`
        : `wss://${cleanBrowserlessUrl}`;
      
      // The live viewer URL format for Browserless v2
      const viewerUrl = browserlessToken
        ? `https://${cleanBrowserlessUrl}/live?token=${browserlessToken}`
        : `https://${cleanBrowserlessUrl}/live`;
      
      liveUrl = viewerUrl;
      
      console.log(`[execute-automation] Live preview URL: ${liveUrl}`);
    }

    // Build the script to execute on Browserless
    const puppeteerScript = buildPuppeteerScript(steps, automation.erp_url, credentials);

    // Use Browserless /function API to execute the script
    const browserlessApiUrl = browserlessToken
      ? `https://${cleanBrowserlessUrl}/function?token=${browserlessToken}`
      : `https://${cleanBrowserlessUrl}/function`;

    console.log(`[execute-automation] Calling Browserless API: ${browserlessApiUrl}`);

    // If live preview, return immediately with the live URL
    // The execution will continue in background
    if (withLivePreview && liveUrl) {
      // Start execution in background (fire and forget)
      executeBrowserless(
        browserlessApiUrl,
        puppeteerScript,
        supabase,
        executionId,
        automationId,
        steps.length,
        automation.webhook_url,
        automation.webhook_secret
      ).catch(err => {
        console.error('[execute-automation] Background execution error:', err);
      });

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

    // Regular execution (blocking)
    const result = await executeBrowserless(
      browserlessApiUrl,
      puppeteerScript,
      supabase,
      executionId,
      automationId,
      steps.length,
      automation.webhook_url,
      automation.webhook_secret
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

function buildPuppeteerScript(
  steps: AutomationStep[], 
  erpUrl: string, 
  credentials: { username?: string; password?: string } | null
): string {
  // Build a Browserless-compatible function script
  const stepsJson = JSON.stringify(steps);
  const credentialsJson = JSON.stringify(credentials);
  
  return `
module.exports = async ({ page }) => {
  const steps = ${stepsJson};
  const credentials = ${credentialsJson};
  const results = {
    stepsCompleted: 0,
    screenshots: [],
    extractedData: {},
    errors: []
  };

  try {
    // Navigate to ERP URL first
    await page.goto('${erpUrl}', { waitUntil: 'networkidle2', timeout: 30000 });
    console.log('Navigated to ERP URL');

    for (const step of steps) {
      try {
        console.log('Executing step:', step.order, step.action, step.description);
        
        switch (step.action) {
          case 'navigate':
            await page.goto(step.value, { waitUntil: 'networkidle2', timeout: 30000 });
            break;
            
          case 'click':
            await page.waitForSelector(step.selector, { timeout: 10000 });
            await page.click(step.selector);
            break;
            
          case 'type':
            await page.waitForSelector(step.selector, { timeout: 10000 });
            let valueToType = step.value;
            // Replace credential placeholders
            if (credentials) {
              if (valueToType === '{{username}}') valueToType = credentials.username || '';
              if (valueToType === '{{password}}') valueToType = credentials.password || '';
            }
            await page.type(step.selector, valueToType, { delay: 50 });
            break;
            
          case 'wait':
            await new Promise(r => setTimeout(r, step.waitTime || 1000));
            break;
            
          case 'waitForSelector':
            await page.waitForSelector(step.selector, { timeout: step.waitTime || 10000 });
            break;
            
          case 'screenshot':
            const screenshot = await page.screenshot({ encoding: 'base64' });
            results.screenshots.push(screenshot);
            break;
            
          case 'extractTable':
            const tableData = await page.evaluate((selector) => {
              const table = document.querySelector(selector);
              if (!table) return null;
              
              const rows = Array.from(table.querySelectorAll('tr'));
              return rows.map(row => {
                const cells = Array.from(row.querySelectorAll('td, th'));
                return cells.map(cell => cell.textContent?.trim() || '');
              });
            }, step.selector);
            results.extractedData[step.description || 'table_' + step.order] = tableData;
            break;
        }
        
        results.stepsCompleted++;
        console.log('Step completed:', step.order);
        
        // Small delay between steps for stability
        await new Promise(r => setTimeout(r, 300));
        
      } catch (stepError) {
        console.error('Step error:', step.order, stepError.message);
        results.errors.push({ step: step.order, error: stepError.message });
        // Continue with next step even if one fails
      }
    }
  } catch (error) {
    console.error('Execution error:', error.message);
    results.errors.push({ step: 0, error: error.message });
  }

  return { data: results, type: 'application/json' };
};
`;
}

async function executeBrowserless(
  apiUrl: string,
  script: string,
  supabase: any,
  executionId: string | undefined,
  automationId: string,
  totalSteps: number,
  webhookUrl?: string | null,
  webhookSecret?: string | null
): Promise<{
  success: boolean;
  stepsCompleted: number;
  extractedData: Record<string, unknown>;
  screenshots: string[];
  error?: string;
}> {
  try {
    console.log('[execute-automation] Sending request to Browserless...');
    
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/javascript',
      },
      body: script,
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[execute-automation] Browserless API error:', errorText);
      throw new Error(`Browserless error: ${response.status} - ${errorText}`);
    }

    const result = await response.json();
    console.log('[execute-automation] Browserless response:', JSON.stringify(result).substring(0, 500));

    const data = result.data || result;
    const stepsCompleted = data.stepsCompleted || 0;
    const extractedData = data.extractedData || {};
    const screenshots = data.screenshots || [];
    const errors = data.errors || [];

    const success = errors.length === 0 || stepsCompleted === totalSteps;
    const errorMessage = errors.length > 0 ? errors.map((e: any) => e.error).join('; ') : undefined;

    // Update execution log
    if (executionId) {
      await supabase
        .from('execution_logs')
        .update({
          finished_at: new Date().toISOString(),
          status: success ? 'success' : 'failed',
          steps_completed: stepsCompleted,
          screenshots,
          extracted_data: extractedData,
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
          stepsCompleted,
          totalSteps,
          extractedData,
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
      stepsCompleted,
      extractedData,
      screenshots,
      error: errorMessage,
    };

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('[execute-automation] Execution failed:', error);

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
