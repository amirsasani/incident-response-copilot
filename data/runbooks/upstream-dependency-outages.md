# Upstream dependency outages

Runbook ID: runbook-dependency-001

## Symptoms

- Requests to an external dependency time out or fail
- DNS resolution or connection establishment errors increase
- Circuit breakers open after repeated failures
- The dependent service returns HTTP 5xx responses

## Investigation

1. Check dependency error rates, timeouts and circuit-breaker state.
2. Verify DNS resolution and network connectivity from the affected service.
3. Review recent deployments for endpoint, credential or routing changes.
4. Compare the configured endpoint with the last known healthy configuration.
5. Check the provider status page and confirm whether other clients are affected.

## Recommended remediation

Restore the last known healthy dependency endpoint or roll back the responsible deployment.

Keep the circuit breaker enabled while validating recovery to avoid cascading failures.

A human operator must approve endpoint changes, failover and rollbacks.
