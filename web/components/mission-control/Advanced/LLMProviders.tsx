"use client";

import { useEffect, useMemo, useState } from "react";

import type { LLMProviderRow } from "@/lib/api/providers";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CheckCircle, Eye, EyeOff, KeyRound, Loader2 } from "lucide-react";

interface LLMProvidersProps {
  providers: LLMProviderRow[];
  onSave: (providerId: string, apiKey: string, model?: string, ollamaBaseUrl?: string) => Promise<void>;
  onTest: (providerId: string) => Promise<boolean>;
  onClearKey?: (providerId: "openai" | "anthropic") => Promise<void>;
}

export function LLMProviders({ providers, onSave, onTest, onClearKey }: LLMProvidersProps) {
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [models, setModels] = useState<Record<string, string>>({});
  const [baseUrls, setBaseUrls] = useState<Record<string, string>>({});
  const [testing, setTesting] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState<Record<string, boolean>>({});

  const initials = useMemo(() => {
    const m: Record<string, string> = {};
    const b: Record<string, string> = {};
    for (const p of providers) {
      m[p.id] = p.model || "";
      b[p.id] = p.base_url || "";
    }
    return { models: m, baseUrls: b };
  }, [providers]);

  useEffect(() => {
    setModels(initials.models);
    setBaseUrls(initials.baseUrls);
  }, [initials]);

  const toggleShowKey = (id: string) => {
    setShowKeys((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleTest = async (providerId: string) => {
    setTesting((prev) => ({ ...prev, [providerId]: true }));
    try {
      await onTest(providerId);
    } finally {
      setTesting((prev) => ({ ...prev, [providerId]: false }));
    }
  };

  const handleSave = async (providerId: string) => {
    setSaving((prev) => ({ ...prev, [providerId]: true }));
    try {
      const key = apiKeys[providerId] || "";
      const model = models[providerId];
      const base = baseUrls[providerId];
      await onSave(providerId, key, model, providerId === "ollama" ? base : undefined);
      setApiKeys((prev) => ({ ...prev, [providerId]: "" }));
    } finally {
      setSaving((prev) => ({ ...prev, [providerId]: false }));
    }
  };

  const getStatusBadge = (provider: LLMProviderRow) => {
    if (!provider.configured && (provider.name === "deepseek" || provider.name === "ollama")) {
      return (
        <Badge variant="secondary" className="text-[10px] uppercase">
          Env / host
        </Badge>
      );
    }
    if (!provider.configured) {
      return (
        <Badge variant="outline" className="border-zinc-600 text-zinc-400">
          Not configured
        </Badge>
      );
    }
    if (provider.status === "connected") {
      return <Badge className="border-transparent bg-emerald-600 text-white">Connected</Badge>;
    }
    if (provider.status === "unknown") {
      return (
        <Badge variant="secondary" className="bg-amber-900/40 text-amber-100">
          Unknown
        </Badge>
      );
    }
    return <Badge className="border-transparent bg-red-600 text-white">Disconnected</Badge>;
  };

  const canSave = (p: LLMProviderRow) => {
    const key = (apiKeys[p.id] || "").trim();
    const modelNow = models[p.id] ?? "";
    const modelWas = initials.models[p.id] ?? "";
    const baseNow = (baseUrls[p.id] || "").trim();
    const baseWas = (initials.baseUrls[p.id] || "").trim();
    if (p.name === "openai" || p.name === "anthropic") {
      return Boolean(key) || modelNow !== modelWas;
    }
    if (p.name === "ollama") {
      return modelNow !== modelWas || baseNow !== baseWas;
    }
    return modelNow !== modelWas;
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-500">
        OpenAI and Anthropic keys are stored with POST /api/v1/web/keys (BYOK). DeepSeek and Ollama are primarily configured on
        the server host; here you can save default models and an Ollama base URL hint into ui_preferences.
      </p>
      {providers.map((provider) => (
        <Card key={provider.id} className="border-zinc-800 bg-zinc-900/40">
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <KeyRound className="h-4 w-4 text-zinc-500" />
                <CardTitle className="capitalize text-zinc-50">{provider.name}</CardTitle>
              </div>
              {getStatusBadge(provider)}
            </div>
            <CardDescription>
              {provider.last_check
                ? `Last refreshed ${new Date(provider.last_check).toLocaleString()}`
                : "Connection hints from /health + /system/health"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {(provider.name === "openai" || provider.name === "anthropic") && (
              <div className="space-y-2">
                <Label htmlFor={`${provider.id}-api-key`} className="text-zinc-200">
                  API key
                </Label>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Input
                      id={`${provider.id}-api-key`}
                      type={showKeys[provider.id] ? "text" : "password"}
                      autoComplete="off"
                      placeholder={provider.api_key_set ? "Key on file — paste to replace" : "Enter API key"}
                      className="border-zinc-800 bg-zinc-950 pr-10"
                      value={apiKeys[provider.id] || ""}
                      onChange={(e) => setApiKeys((prev) => ({ ...prev, [provider.id]: e.target.value }))}
                    />
                    <button
                      type="button"
                      onClick={() => toggleShowKey(provider.id)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-200"
                    >
                      {showKeys[provider.id] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  {provider.api_key_set ? (
                    <div className="flex items-center text-emerald-400">
                      <CheckCircle className="h-5 w-5" aria-label="Key on file" />
                    </div>
                  ) : null}
                </div>
                {provider.api_key_set && onClearKey ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="border-zinc-700"
                    onClick={() => void onClearKey(provider.name as "openai" | "anthropic")}
                  >
                    Remove stored key
                  </Button>
                ) : null}
              </div>
            )}

            {provider.name !== "ollama" ? (
              <div className="space-y-2">
                <Label htmlFor={`${provider.id}-model`} className="text-zinc-200">
                  Default model (saved to preferences)
                </Label>
                <Input
                  id={`${provider.id}-model`}
                  placeholder={
                    provider.name === "openai"
                      ? "e.g. gpt-4o-mini"
                      : provider.name === "anthropic"
                        ? "e.g. claude-3-5-sonnet-latest"
                        : "e.g. deepseek-chat"
                  }
                  className="border-zinc-800 bg-zinc-950"
                  value={models[provider.id] ?? ""}
                  onChange={(e) => setModels((prev) => ({ ...prev, [provider.id]: e.target.value }))}
                />
              </div>
            ) : null}

            {provider.name === "ollama" && (
              <>
                <div className="space-y-2">
                  <Label htmlFor={`${provider.id}-base-url`} className="text-zinc-200">
                    Base URL (preference hint)
                  </Label>
                  <Input
                    id={`${provider.id}-base-url`}
                    placeholder="http://127.0.0.1:11434"
                    className="border-zinc-800 bg-zinc-950"
                    value={baseUrls[provider.id] ?? ""}
                    onChange={(e) => setBaseUrls((prev) => ({ ...prev, [provider.id]: e.target.value }))}
                  />
                  <p className="text-xs text-zinc-500">Server still uses NEXA_OLLAMA_* env; this is for your notes in the UI.</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor={`${provider.id}-model`} className="text-zinc-200">
                    Default model (preference)
                  </Label>
                  <Input
                    id={`${provider.id}-model`}
                    placeholder="llama3"
                    className="border-zinc-800 bg-zinc-950"
                    value={models[provider.id] ?? ""}
                    onChange={(e) => setModels((prev) => ({ ...prev, [provider.id]: e.target.value }))}
                  />
                </div>
              </>
            )}

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                className="border-zinc-700"
                onClick={() => void handleTest(provider.id)}
                disabled={testing[provider.id]}
              >
                {testing[provider.id] ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Test connection
              </Button>
              <Button type="button" onClick={() => void handleSave(provider.id)} disabled={saving[provider.id] || !canSave(provider)}>
                {saving[provider.id] ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Save
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
