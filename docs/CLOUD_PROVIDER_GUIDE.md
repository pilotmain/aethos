# AethOS Cloud Provider Guide

## Overview

AethOS supports **any cloud provider** through a dynamic configuration system. You can deploy to Railway, Vercel, AWS, GCP, Kubernetes, or any custom provider without changing application code—configuration lives in YAML.

## Supported providers (24 built-in)

Built-ins ship in `config/cloud_providers_default.yaml`. Tokens are read from the worker environment (for example `.env` on the machine running the ops agent).

| Provider | CLI / binary (typical) | Token env var (from defaults) |
|----------|------------------------|-------------------------------|
| Railway | `railway` | `RAILWAY_TOKEN` |
| Vercel | `vercel` | `VERCEL_TOKEN` |
| AWS | `aws` | `AWS_ACCESS_KEY_ID` |
| GCP | `gcloud` | `GOOGLE_APPLICATION_CREDENTIALS` |
| Heroku | `git` / Heroku remote | `HEROKU_API_KEY` |
| Fly.io | `fly` | `FLY_API_TOKEN` |
| Netlify | `netlify` | `NETLIFY_AUTH_TOKEN` |
| Cloudflare Workers | `wrangler` | `CLOUDFLARE_API_TOKEN` |
| Azure | `az` | `AZURE_CLIENT_SECRET` |
| DigitalOcean | `doctl` | `DIGITALOCEAN_TOKEN` |
| Kubernetes | `kubectl` | `KUBECONFIG` |
| Terraform | `terraform` | _(none in defaults; project-dependent)_ |
| Pulumi | `pulumi` | `PULUMI_ACCESS_TOKEN` |
| OpenShift | `oc` | `KUBECONFIG` |
| Render | `render` | `RENDER_API_KEY` |
| Koyeb | `koyeb` | `KOYEB_API_KEY` |
| Northflank | `northflank` | `NORTHFLANK_API_KEY` |
| Cycle | `cycle` | `CYCLE_API_KEY` |
| Porter | `porter` | `PORTER_API_KEY` |
| Zeabur | `zeabur` | `ZEABUR_API_KEY` |
| Adaptable | `adaptable` | `ADAPTABLE_API_KEY` |
| Kinsta | `kinsta` | `KINSTA_API_KEY` |
| Platform.sh | `platform` | `PLATFORMSH_CLI_TOKEN` |
| Cleavr | `cleavr` | `CLEAVR_API_KEY` |

Exact argv templates and detection patterns are in the YAML; install hints may be URLs or package names.

## Listing available providers

In Telegram:

```text
/cloud_providers
```

(or `/clouds`)

This reloads configuration from disk and lists all merged providers.

## Deploying to a provider

### Basic deployment

```text
@ops_agent deploy to Railway
```

### With environment variables

```text
@ops_agent deploy to Railway with NODE_ENV=production PORT=8080
```

### Other provider names

```text
@ops_agent deploy to DigitalOcean
@ops_agent deploy to Kubernetes
```

Detection uses provider **detect patterns** and your message text; use names shown in `/cloud_providers` when unsure.

## Adding a custom provider

### Prerequisites

1. CLI installed on the **worker** machine that runs deploy commands.
2. API token or credentials available as environment variables.
3. The generated template assumes `deploy`, `logs`, and `status` subcommands exist on that CLI—adjust the YAML if your tool differs.

### Command format (Telegram)

```text
/add_provider <name> <cli_binary> <TOKEN_ENV_VAR>
```

### Examples

```text
/add_provider scaleway scw SCW_SECRET_KEY
/add_provider linode linode-cli LINODE_TOKEN
/add_provider vultr vultr-cli VULTR_API_KEY
/add_provider ovh ovhai OVH_APPLICATION_KEY
```

### What happens

1. A file is created at `~/.aethos/cloud_providers.d/<name>.yaml` (slugified name).
2. The registry reloads; the provider appears in `/cloud_providers`.
3. You can deploy with `@ops_agent deploy to <name>` once the CLI and token are available on the worker.

You **cannot** reserve a name that already exists in the **built-in** defaults; choose another id or override via `~/.aethos/cloud_providers.yaml`.

### Generated file shape

The bot writes YAML equivalent to:

```yaml
name: scaleway
display_name: Scaleway
cli_package: scw
install_command: Install `scw` and ensure it is on PATH.
token_env_var: SCW_SECRET_KEY
detect_patterns: [scaleway]
capabilities: [deploy, logs, status]
commands:
  deploy: [scw, deploy]
  logs: [scw, logs]
  status: [scw, status]
```

Keys `cli` and `cli_package` are both accepted in hand-written YAML (see schema).

## Removing a provider

```text
/remove_provider scaleway
```

Only removes a **drop-in** file under `~/.aethos/cloud_providers.d/` that matches that name. **Built-in** providers cannot be removed. Overrides in `~/.aethos/cloud_providers.yaml` must be edited manually.

## Environment variables

Set tokens in the worker `.env` (or process environment), for example:

```bash
# Railway
RAILWAY_TOKEN=your_railway_token
RAILWAY_PROJECT_ID=your_project_id

# Vercel
VERCEL_TOKEN=your_vercel_token

# AWS
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# GCP
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# DigitalOcean
DIGITALOCEAN_TOKEN=your_do_token

# Custom provider
SCW_SECRET_KEY=your_scaleway_token
```

## Advanced: manual configuration

You can define or override providers in:

| Location | Role |
|----------|------|
| `config/cloud_providers_default.yaml` | Shipped with the repo (lowest priority among layers; base defaults). |
| `/etc/aethos/cloud_providers.yaml` | System-wide overlay |
| `~/.aethos/cloud_providers.d/*.yaml` | User modular files (sorted); each file can define one or more providers |
| `~/.aethos/cloud_providers.yaml` | User single-file overlay (**highest priority**) |

**Merge rule:** same provider `name` in a later source **replaces** the entry from earlier sources.

### Manual example

```yaml
providers:
  - name: custom
    display_name: My Custom Cloud
    cli_package: mycloud
    install_command: npm install -g mycloud-cli
    token_env_var: MYCLOUD_TOKEN
    detect_patterns: [mycloud, custom]
    capabilities: [deploy, logs, status]
    commands:
      deploy: [mycloud, push]
      logs: [mycloud, logs, --tail]
      status: [mycloud, status]
```

Full field list: `config/cloud_providers_schema.yaml`.

## Troubleshooting

| Symptom | What to check |
|--------|----------------|
| **Provider not found** | Run `/cloud_providers`; use an exact name from the list. For NL detection, include keywords from `detect_patterns`. |
| **CLI not found** | Install the CLI on the worker and ensure it is on `PATH`. |
| **Not authenticated** | Set the token env var from the provider row / YAML; some CLIs also need `login` once. |
| **Deployment failed** | Read stderr from the CLI; confirm project/link steps (e.g. Railway/Vercel project binding). |

## Full workflow example

```bash
# 1. Set token in .env on the worker
echo "SCW_SECRET_KEY=your_token" >> .env

# 2. Add provider (Telegram)
# /add_provider scaleway scw SCW_SECRET_KEY

# 3. Verify
# /cloud_providers

# 4. Deploy (chat)
# @ops_agent deploy to scaleway with NODE_ENV=production
```

## Configuration priority (later wins)

Sources are loaded in this order; **duplicate `name` entries are overridden by later files**:

1. Packaged defaults — `config/cloud_providers_default.yaml` in the app tree  
2. `/etc/aethos/cloud_providers.yaml`  
3. `~/.aethos/cloud_providers.d/*.yaml` (all matching files, sorted)  
4. `~/.aethos/cloud_providers.yaml`  

## Adding a built-in provider (contributors)

1. Edit `config/cloud_providers_default.yaml`.  
2. Follow `config/cloud_providers_schema.yaml`.  
3. Open a pull request.

For help, use your project’s issue tracker or community channels.
