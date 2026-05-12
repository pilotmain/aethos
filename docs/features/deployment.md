# Deployment

## Supported platforms (typical)

AethOS integrates with common hosts and CLIs when configured (examples):

- **Vercel**, **Railway**, **Fly.io**, **Netlify**, **Cloudflare**, **Heroku** — see [CLOUD_PROVIDER_GUIDE.md](../CLOUD_PROVIDER_GUIDE.md) and gateway NL flows (`deploy_nl`, `deployment_status_nl`).

## Natural language examples

- “Deploy” / “deploy to vercel” / “deploy to railway”
- “Check Vercel projects” / “what’s running on Railway?”

## Auto-detection

Install the provider CLI and set tokens in `.env`; the product surfaces **only what is configured** on the host.

## Related

- [API.md](../API.md)
- [OPERATIONS.md](../OPERATIONS.md)
