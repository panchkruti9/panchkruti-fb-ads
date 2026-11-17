# Meta app setup guide

Last updated: 4 November 2026

This guide covers a client-owned Meta app for ads, social content and business messaging. Screens and requirements can vary by account and use case.

## 1. Prepare access

1. Identify the client's business portfolio and the assets the app will use.
2. Have an authorized client administrator create or select the app under the client's portfolio.
3. Give the developer the appropriate app and business asset roles. Confirm the client retains administrative access.

## 2. Create the app

1. Sign in at [Meta for Developers](https://developers.facebook.com/apps/).
2. Select **Create App** and complete developer registration if prompted.
3. Select the needed use cases. The options can include **Create & manage ads with Marketing API**, **Measure ad performance data with Marketing API**, **Create & manage ads with ads MCP server**, **Manage everything on your Page**, **Manage messaging & content on Instagram**, **Connect with customers through WhatsApp**, and **Engage with customers on Messenger from Meta**.
4. Enter the requested app details and select the client's business portfolio when prompted.
5. Create the app. Record its name and app ID in the client's private project notes, and verify the intended portfolio is associated.

Selecting a use case starts its setup. Check its dashboard for configuration, permissions, verification and review requirements.

## 3. Configure Ads MCP

1. Open the app in the developer dashboard and select **Create & manage ads with ads MCP server**.
2. Open the use case's permissions and features list. Check that `ads_mcp_management` and `ads_read` are listed and note their status. **Ready for testing** indicates a testing stage; the token, asset access and actual connection must still be verified.
3. In Meta Business Settings, open **Integrations → Ads MCP server** and review the actions allowed for the intended ad account.
4. Choose an authentication method supported by the MCP client. Meta documents OAuth, user access tokens and employee-role system-user access tokens. Its server URL is `https://mcp.facebook.com/ads`.
5. For a token connection, Meta specifies `ads_mcp_management` and either `ads_read` or `ads_management` as minimum permissions. Assign the appropriate ad account access to the user or system user.
6. Connect the client and verify the ad account. For performance, review a verified `agi-` campaign and confirm the date range.

An app is not required for every Ads MCP connection. Codex automatic registration previously returned `invalid_client_metadata` in one test. A compatible connection still needs to be verified.

## 4. Configure social content and messaging

1. Open each selected use case in the app dashboard.
2. Follow Meta's setup for the client's Facebook Page, Instagram professional account, Messenger and WhatsApp account as applicable.
3. Review permissions, app roles and asset assignments for each feature.
4. Check the dashboard for business verification, app review or other requirements. These vary with the permissions, access level and use case.
5. Test each feature separately with the intended client-owned account. Record the results and restrictions in private project notes.

WhatsApp contact links and automated WhatsApp messaging have different setup needs. Confirm the intended workflow before configuring messaging.

## 5. Store credentials and set up automation

1. Keep passwords, access tokens and app secrets out of source files, documentation and chat.
2. For GitHub Actions workflows, store required credentials under **Settings → Secrets and variables → Actions** in the relevant repository.
3. Add and test the workflow that consumes the secret. Saving a secret alone does not connect the app or enable automation.
4. Verify read access before testing campaign creation or changes. Review the budget and delivery settings before activating an ad.

See the [runbook credential mapping](docs/meta-ads/runbook.md#scheduled-review) for the separate Marketing API review, operator execution, and manual MCP check.

## Official references

- [Meta Ads MCP overview](https://developers.facebook.com/documentation/ads-commerce/ads-ai-connectors/ads-mcp-server/ads-mcp-server-overview)
- [Meta Ads MCP setup](https://developers.facebook.com/documentation/ads-commerce/ads-ai-connectors/ads-mcp-server/ads-mcp-server-get-started)
- [GitHub Actions secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)
