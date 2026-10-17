# Database connection errors

Runbook ID: runbook-db-001

## Symptoms

- Database connection acquisition timeouts
- Connection-pool utilization near 100%
- Increased request latency and HTTP 500 responses

## Investigation

1. Check connection-pool utilization.
2. Review recent configuration changes.
3. Compare the configured pool size with normal traffic requirements.
4. Check for long-running or leaked connections.

## Recommended remediation

Restore the last known healthy pool size or roll back the responsible deployment.

A human operator must approve configuration changes or rollbacks.
