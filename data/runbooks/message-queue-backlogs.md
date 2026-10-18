# Message queue backlogs

Runbook ID: runbook-queue-001

## Symptoms

- Queue depth grows continuously
- The oldest message age exceeds the delivery objective
- Consumer throughput is lower than producer throughput
- Notifications or background jobs are delivered late

## Investigation

1. Compare queue depth, message age and consumer throughput.
2. Check the number of healthy consumer instances and active consumer threads.
3. Review recent deployments and concurrency configuration changes.
4. Confirm that downstream dependencies are healthy and not rate limiting consumers.
5. Check for poison messages that repeatedly fail and block processing.

## Recommended remediation

Restore the last known healthy consumer concurrency or roll back the responsible deployment.

Scale consumers gradually while monitoring downstream error rates and queue drain time.

A human operator must approve scaling, configuration changes and rollbacks.
