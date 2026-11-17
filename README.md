# Panchkruti Facebook Ads Automation

Private workspace for reporting on and managing Panchkruti's Facebook and Instagram ads.

## Team access

1. Grant teammates access to the private GitHub repository through repository settings. Each teammate also needs access to **Panchkruti Ads** in Meta Business Settings.
2. Connect to `https://mcp.facebook.com/ads` using a Meta-compatible MCP client and authorize with your own Meta account. For Codex, adding the endpoint alone was tested and Meta rejected automatic OAuth client registration. Codex needs a compatible, preconfigured Meta OAuth client or another supported authentication setup.
3. Verify account access first. Read campaign performance for verified `agi-` campaigns through the runbook.

## Meta Ads workflow

| Folder | What belongs there |
|---|---|
| `.agents/skills/` | Project skills and their imported references |
| `docs/meta-ads/` | Brand rules, strategy, templates, and the operating runbook |
| `docs/meta-ads/campaigns/` | Campaign plans, creative briefs, and review notes |
| `docs/meta-ads/evidence/` | Aggregate campaign evidence |
| `assets/` | Original media, creative exports, and previews |
| `automation/` and `.github/workflows/` | Local commands, tests, and scheduled jobs |

Use the [creative workflow](docs/meta-ads/creative.md) to turn a campaign brief and approved Drive asset into deliverable ad files.

Start with the [Meta Ads skill](.agents/skills/meta-ads/SKILL.md). Use the [strategy playbook](docs/meta-ads/strategy.md) to plan the campaign, the [decision playbook](docs/meta-ads/optimize.md) to review results, and the [runbook](docs/meta-ads/runbook.md) for account operations. The [project instructions](AGENTS.md#meta-ads) define permissions and account scope.

Use the credential mapping in the runbook. The scheduled Marketing API review and the manual MCP connection check use separate credentials.
