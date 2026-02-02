import { supabase } from "@/integrations/supabase/client";

export interface Setting {
  id: string;
  key: string;
  value: string | null;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface BrowserlessSettings {
  url: string;
  token: string;
}

export async function fetchSettings(): Promise<Setting[]> {
  const { data, error } = await supabase
    .from("settings")
    .select("*");

  if (error) throw error;
  return data || [];
}

export async function getSetting(key: string): Promise<string | null> {
  const { data, error } = await supabase
    .from("settings")
    .select("value")
    .eq("key", key)
    .single();

  if (error) {
    if (error.code === "PGRST116") return null; // Not found
    throw error;
  }
  return data?.value || null;
}

export async function updateSetting(key: string, value: string): Promise<void> {
  const { error } = await supabase
    .from("settings")
    .update({ value, updated_at: new Date().toISOString() })
    .eq("key", key);

  if (error) throw error;
}

export async function getBrowserlessSettings(): Promise<BrowserlessSettings> {
  const settings = await fetchSettings();
  
  const urlSetting = settings.find(s => s.key === "browserless_url");
  const tokenSetting = settings.find(s => s.key === "browserless_token");

  return {
    url: urlSetting?.value || "",
    token: tokenSetting?.value || "",
  };
}

export async function saveBrowserlessSettings(settings: BrowserlessSettings): Promise<void> {
  await Promise.all([
    updateSetting("browserless_url", settings.url),
    updateSetting("browserless_token", settings.token),
  ]);
}

export async function testBrowserlessConnection(url: string, token: string): Promise<boolean> {
  try {
    // Test connection by calling the /json/version endpoint
    const testUrl = url.replace(/\/$/, "") + "/json/version";
    const headers: HeadersInit = {};
    
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(testUrl, {
      method: "GET",
      headers,
      signal: AbortSignal.timeout(5000),
    });

    return response.ok;
  } catch {
    return false;
  }
}
