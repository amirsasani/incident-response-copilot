# Application memory leaks

Runbook ID: runbook-memory-001

## Symptoms

- Process or heap memory grows continuously under stable traffic
- Memory remains high after full garbage collection
- Garbage-collection pauses and request latency increase
- Containers restart after exceeding their memory limit

## Investigation

1. Check process memory, heap utilization and garbage-collection metrics.
2. Review recent deployments for new caches, retained objects or unbounded collections.
3. Compare memory growth before and after the latest deployment.
4. Capture a heap dump before restarting an affected instance when operationally safe.
5. Confirm that caches have explicit size and expiration limits.

## Recommended remediation

Disable or bound the suspected cache, or roll back the responsible deployment.

Restarting containers can temporarily restore service but does not remove the underlying leak.

A human operator must approve rollbacks, configuration changes and production restarts.
