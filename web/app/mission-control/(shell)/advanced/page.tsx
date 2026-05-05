"use client";

import { useCallback, useEffect, useState } from "react";

import { DangerZone } from "@/components/mission-control/Advanced/DangerZone";
import { Diagnostics } from "@/components/mission-control/Advanced/Diagnostics";
import { ExportImport } from "@/components/mission-control/Advanced/ExportImport";
import { Integrations } from "@/components/mission-control/Advanced/Integrations";
import { LLMProviders } from "@/components/mission-control/Advanced/LLMProviders";
import { SystemSettings } from "@/components/mission-control/Advanced/SystemSettings";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { downloadBlobToFile, formatMissionControlApiError } from "@/lib/api";
import {
  getIntegrations,
  removeIntegration,
  saveIntegration,
  saveIntegrationFields,
  toggleIntegration,
} from "@/lib/api/integrations";
import type { LLMProviderRow } from "@/lib/api/providers";
import { getLLMProviders, removeLLMProviderKey, saveLLMProvider, testLLMProvider } from "@/lib/api/providers";
import {
  exportSettingsSnapshot,
  getSystemConfig,
  importSettingsSnapshot,
  resetAdvancedUiPreferences,
  saveSystemConfig,
} from "@/lib/api/settings";
import { getDiagnostics } from "@/lib/api/system";
import type { IntegrationConfig, SystemConfig } from "@/types/mission-control";
import Link from "next/link";

export default function MissionControlAdvancedPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [providers, setProviders] = useState<LLMProviderRow[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationConfig[]>([]);
  const [systemConfig, setSystemConfig] = useState<SystemConfig | null>(null);

  const loadAdvancedData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [providersData, integrationsData, configData] = await Promise.all([
        getLLMProviders(),
        getIntegrations(),
        getSystemConfig(),
      ]);
      setProviders(providersData);
      setIntegrations(integrationsData);
      setSystemConfig(configData);
    } catch (e) {
      setError(formatMissionControlApiError(e instanceof Error ? e.message : String(e)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAdvancedData();
  }, [loadAdvancedData]);

  const handleSaveProvider = async (
    providerId: string,
    apiKey: string,
    model?: string,
    ollamaBaseUrl?: string,
  ) => {
    await saveLLMProvider(providerId, apiKey, model, ollamaBaseUrl);
    await loadAdvancedData();
    setBanner(`${providerId} settings saved.`);
  };

  const handleTestProvider = async (providerId: string): Promise<boolean> => {
    const ok = await testLLMProvider(providerId);
    setBanner(
      ok
        ? `${providerId}: heuristic check passed (/health + BYOK where applicable).`
        : `${providerId}: check failed — verify API reachability and keys.`,
    );
    return ok;
  };

  const handleClearKey = async (providerId: "openai" | "anthropic") => {
    await removeLLMProviderKey(providerId);
    await loadAdvancedData();
    setBanner(`${providerId} key removed from BYOK store.`);
  };

  const handleToggleIntegration = async (id: string, enabled: boolean) => {
    await toggleIntegration(id, enabled);
    await loadAdvancedData();
  };

  const handleSaveIntegration = async (id: string, config: Partial<IntegrationConfig>) => {
    await saveIntegration(id, config);
    await loadAdvancedData();
  };

  const handleSaveGithub = async (id: string, repository: string, token: string) => {
    await saveIntegrationFields(id, { repository, token });
    await loadAdvancedData();
    setBanner("GitHub integration row updated (stored in ui_preferences).");
  };

  const handleRemoveIntegration = async (id: string) => {
    await removeIntegration(id);
    await loadAdvancedData();
  };

  const handleSaveSystemConfig = async (config: Partial<SystemConfig>) => {
    const next = await saveSystemConfig(config);
    setSystemConfig(next);
    setBanner("System preferences saved.");
  };

  const handleGetDiagnostics = async () => getDiagnostics();

  const handleExport = async () => {
    const snap = await exportSettingsSnapshot();
    const blob = new Blob([JSON.stringify(snap, null, 2)], { type: "application/json" });
    downloadBlobToFile(blob, `nexa-settings-export-${Date.now()}.json`);
  };

  const handleImport = async (file: File) => {
    const text = await file.text();
    const payload = JSON.parse(text) as Record<string, unknown>;
    await importSettingsSnapshot(payload);
    await loadAdvancedData();
  };

  const handleReset = async () => {
    await resetAdvancedUiPreferences();
    await loadAdvancedData();
  };

  const handleDeleteWorkspace = async () => {
    window.alert(
      "AethOS does not expose a browser API to delete an entire workspace. Remove database files, Docker volumes, or tenant data on the server host.",
    );
  };

  if (loading) {
    return (
      <div className="flex h-64 flex-col items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
          <p className="mt-2 text-sm text-zinc-500">Loading settings…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-50">Advanced</h1>
        <p className="mt-1 max-w-prose text-sm text-zinc-400">
          Provider BYOK via /web/keys, diagnostics via /system/*, and Mission Control preferences via /user/settings. Legacy
          panels remain at{" "}
          <Link href="/mission-control/legacy" className="text-violet-400 underline-offset-2 hover:underline">
            /mission-control/legacy
          </Link>
          .
        </p>
      </div>

      {error ? (
        <div className="rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-200">{error}</div>
      ) : null}
      {banner ? (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-4 py-3 text-sm text-zinc-300">{banner}</div>
      ) : null}

      <Tabs defaultValue="llm" className="space-y-4">
        <TabsList className="flex h-auto flex-wrap gap-1 border border-zinc-800 bg-zinc-900 p-1">
          <TabsTrigger value="llm">LLM providers</TabsTrigger>
          <TabsTrigger value="integrations">Integrations</TabsTrigger>
          <TabsTrigger value="system">System</TabsTrigger>
          <TabsTrigger value="diagnostics">Diagnostics</TabsTrigger>
          <TabsTrigger value="export">Export / import</TabsTrigger>
          <TabsTrigger value="danger" className="text-red-400 data-[state=active]:bg-red-950/50">
            Danger zone
          </TabsTrigger>
        </TabsList>

        <TabsContent value="llm">
          <LLMProviders
            providers={providers}
            onSave={handleSaveProvider}
            onTest={handleTestProvider}
            onClearKey={handleClearKey}
          />
        </TabsContent>

        <TabsContent value="integrations">
          <Integrations
            integrations={integrations}
            onToggle={handleToggleIntegration}
            onSave={handleSaveIntegration}
            onSaveGithub={handleSaveGithub}
            onRemove={handleRemoveIntegration}
          />
        </TabsContent>

        <TabsContent value="system">{systemConfig ? <SystemSettings config={systemConfig} onSave={handleSaveSystemConfig} /> : null}</TabsContent>

        <TabsContent value="diagnostics">
          <Diagnostics onRefresh={handleGetDiagnostics} />
        </TabsContent>

        <TabsContent value="export">
          <ExportImport onExport={handleExport} onImport={handleImport} />
        </TabsContent>

        <TabsContent value="danger">
          <DangerZone onReset={handleReset} onDeleteWorkspace={handleDeleteWorkspace} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
