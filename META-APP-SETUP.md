# Panchkruti Meta app setup

Last updated: 4 November 2026

## Project

Panchkruti will use this integration for its own Facebook and Instagram ads, social media content, and WhatsApp. The app is intended to belong to Panchkruti's business portfolio. The developer will help set it up for the client.

The private GitHub repository is https://github.com/panchkruti9/panchkruti-fb-ads.

## Meta assets

- Business portfolio shown in Meta settings: **panchkruti**.
- Ad account shown: **Panchkruti Ads**, ID `210757768577022`.
- The Ads MCP server settings showed **7 of 7 actions allowed** for this account. This setting alone does not establish a connection.

## App creation

The user is on the use-case selection screen. The following selections were visible in the screenshot:

- Create & manage ads with Marketing API
- Measure ad performance data with Marketing API
- Create & manage ads with ads MCP server
- Engage with customers on Messenger from Meta
- Manage messaging & content on Instagram
- Manage everything on your Page
- Connect with customers through WhatsApp

Messenger is included in the current selection. Confirm its intended use as the setup progresses.

**Current step:** Continue from the use-case selection screen. If prompted, select Panchkruti's business portfolio. App creation, app ID, ownership and permissions have not yet been verified.

## Ads MCP connection

Meta hosts the Ads MCP server at `https://mcp.facebook.com/ads`. Codex's automatic OAuth registration was attempted and failed with `invalid_client_metadata`. No working connection has been verified.

Meta's setup guide says owning an app is not a prerequisite for all MCP connections. For a connection using an app's token, Meta documents the **Create & manage ads with ads MCP server** use case and requires `ads_mcp_management` plus `ads_read` or `ads_management`. Only employee-role system-user tokens are supported for Ads MCP. The exact connection method and permissions for this project remain to be tested.

First connection test: list ad accounts and read campaign performance. Campaign changes and budget automation remain to be defined and tested.

## Verification and WhatsApp

Business verification and app review requirements depend on the features, permissions, access level and account setup. They have not been confirmed for this project. Check the app dashboard and WhatsApp setup for actual requirements before treating any review as complete.

The intended WhatsApp workflow, including whether to automate customer messages, has not yet been specified.

## Credentials

Keep access tokens, app secrets and passwords out of this document and Git. If a GitHub Actions workflow is added, configure its credential as a GitHub Actions secret.

## References

- [Meta Ads MCP overview](https://developers.facebook.com/documentation/ads-commerce/ads-ai-connectors/ads-mcp-server/ads-mcp-server-overview)
- [Meta Ads MCP setup](https://developers.facebook.com/documentation/ads-commerce/ads-ai-connectors/ads-mcp-server/ads-mcp-server-get-started)
