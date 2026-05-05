"use client";

import { useEffect, useState } from "react";

import type { IntegrationConfig } from "@/types/mission-control";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Github, MessagesSquare, Send, Slack, Trash2 } from "lucide-react";

interface IntegrationsProps {
  integrations: IntegrationConfig[];
  onToggle: (id: string, enabled: boolean) => Promise<void>;
  onSave: (id: string, config: Partial<IntegrationConfig>) => Promise<void>;
  onSaveGithub: (id: string, repository: string, token: string) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
}

const integrationIcons = {
  slack: Slack,
  github: Github,
  telegram: Send,
  discord: MessagesSquare,
};

export function Integrations({ integrations, onToggle, onSave, onSaveGithub, onRemove }: IntegrationsProps) {
  const [webhookUrls, setWebhookUrls] = useState<Record<string, string>>({});
  const [repos, setRepos] = useState<Record<string, string>>({});
  const [tokens, setTokens] = useState<Record<string, string>>({});

  useEffect(() => {
    const w: Record<string, string> = {};
    const r: Record<string, string> = {};
    for (const i of integrations) {
      if (i.webhook_url) w[i.id] = i.webhook_url;
      if (i.type === "github" && i.channel) r[i.id] = i.channel;
    }
    setWebhookUrls((prev) => ({ ...w, ...prev }));
    setRepos((prev) => ({ ...r, ...prev }));
  }, [integrations]);

  const handleSaveWebhook = async (integration: IntegrationConfig) => {
    await onSave(integration.id, {
      webhook_url: webhookUrls[integration.id] ?? integration.webhook_url,
    });
  };

  const handleSaveGithub = async (integration: IntegrationConfig) => {
    await onSaveGithub(integration.id, repos[integration.id] ?? integration.channel ?? "", tokens[integration.id] ?? "");
    setTokens((prev) => ({ ...prev, [integration.id]: "" }));
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-500">
        Channel gateways (Slack Events API, Telegram bot, etc.) are normally configured with server environment variables.
        This panel stores optional webhook URLs and tokens in ui_preferences for UI workflows — not a substitute for
        production secrets management.
      </p>
      {integrations.map((integration) => {
        const Icon = integrationIcons[integration.type];
        return (
          <Card key={integration.id} className="border-zinc-800 bg-zinc-900/40">
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Icon className="h-5 w-5 text-zinc-400" />
                  <CardTitle className="text-zinc-50">{integration.name}</CardTitle>
                </div>
                <div className="flex items-center gap-2">
                  {integration.configured ? (
                    <Badge className="border-transparent bg-emerald-600 text-white">Configured</Badge>
                  ) : (
                    <Badge variant="outline" className="border-zinc-600 text-zinc-400">
                      Not configured
                    </Badge>
                  )}
                  <Switch checked={integration.enabled} onCheckedChange={(checked) => void onToggle(integration.id, checked)} />
                </div>
              </div>
              <CardDescription>Integration id: {integration.id}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {integration.type === "slack" && (
                <div className="space-y-2">
                  <Label className="text-zinc-200">Webhook URL</Label>
                  <div className="flex flex-wrap gap-2">
                    <Input
                      placeholder="https://hooks.slack.com/services/..."
                      className="min-w-[240px] flex-1 border-zinc-800 bg-zinc-950"
                      value={webhookUrls[integration.id] ?? integration.webhook_url ?? ""}
                      onChange={(e) => setWebhookUrls((prev) => ({ ...prev, [integration.id]: e.target.value }))}
                    />
                    <Button type="button" variant="outline" className="border-zinc-700" onClick={() => void handleSaveWebhook(integration)}>
                      Save
                    </Button>
                  </div>
                </div>
              )}

              {integration.type === "github" && (
                <div className="space-y-3">
                  <div className="space-y-2">
                    <Label className="text-zinc-200">Repository</Label>
                    <Input
                      placeholder="owner/repo"
                      className="border-zinc-800 bg-zinc-950"
                      value={repos[integration.id] ?? integration.channel ?? ""}
                      onChange={(e) => setRepos((prev) => ({ ...prev, [integration.id]: e.target.value }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-zinc-200">Personal access token</Label>
                    <Input
                      type="password"
                      autoComplete="off"
                      placeholder={integration.configured ? "Enter new token to rotate" : "ghp_..."}
                      className="border-zinc-800 bg-zinc-950"
                      value={tokens[integration.id] ?? ""}
                      onChange={(e) => setTokens((prev) => ({ ...prev, [integration.id]: e.target.value }))}
                    />
                  </div>
                  <Button type="button" variant="outline" className="border-zinc-700" onClick={() => void handleSaveGithub(integration)}>
                    Save GitHub credentials
                  </Button>
                </div>
              )}

              {(integration.type === "telegram" || integration.type === "discord") && (
                <div className="space-y-2">
                  <Label className="text-zinc-200">Bot token or webhook URL</Label>
                  <div className="flex flex-wrap gap-2">
                    <Input
                      className="min-w-[240px] flex-1 border-zinc-800 bg-zinc-950"
                      placeholder="Stored only in ui_preferences"
                      value={webhookUrls[integration.id] ?? integration.webhook_url ?? ""}
                      onChange={(e) => setWebhookUrls((prev) => ({ ...prev, [integration.id]: e.target.value }))}
                    />
                    <Button type="button" variant="outline" className="border-zinc-700" onClick={() => void handleSaveWebhook(integration)}>
                      Save
                    </Button>
                  </div>
                </div>
              )}

              {integration.last_active ? (
                <p className="text-xs text-zinc-500">Last saved in UI: {new Date(integration.last_active).toLocaleString()}</p>
              ) : null}

              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="text-red-400 hover:bg-red-950/40 hover:text-red-300"
                onClick={() => void onRemove(integration.id)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Clear saved integration data
              </Button>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
