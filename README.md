# Panchkruti Facebook Ads Automation

Private workspace for reporting on and managing Panchkruti's Facebook and Instagram ads.

## Connection setup

1. Authorize Meta Ads MCP in the MCP client using the Panchkruti ad account.
2. Verify access by listing campaigns and reading the last seven days of spend.
3. For scheduled jobs that run on GitHub Actions, configure `META_ACCESS_TOKEN` as an Actions secret and `META_AD_ACCOUNT_ID` as an Actions variable. Keep credentials out of Git.

Start with read access. Validate campaign creation in a paused state before enabling delivery or applying budget changes.
