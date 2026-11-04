# Panchkruti Facebook Ads Automation

Private workspace for reporting on and managing Panchkruti's Facebook and Instagram ads.

## Team access

1. Grant teammates access to the private GitHub repository through repository settings. Each teammate also needs access to **Panchkruti Ads** in Meta Business Settings.
2. Connect to `https://mcp.facebook.com/ads` using a Meta-compatible MCP client and authorize with your own Meta account. For Codex, adding the endpoint alone was tested and Meta rejected automatic OAuth client registration. Codex needs a compatible, preconfigured Meta OAuth client or another supported authentication setup.
3. Verify access by listing campaigns and reading the last seven days of spend.

## Scheduled automation

If scheduled jobs run on GitHub Actions, configure `META_ACCESS_TOKEN` as an Actions secret and `META_AD_ACCOUNT_ID` as an Actions variable. The workflow uses its own authorized Meta credential. Keep credentials out of Git.

Start with read access. Validate campaign creation in a paused state before enabling delivery or applying budget changes.
