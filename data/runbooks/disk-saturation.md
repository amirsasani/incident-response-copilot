# Disk saturation

Runbook ID: runbook-disk-001

## Symptoms

- Filesystem utilization approaches 100%
- Applications report no space left on device
- File writes become slow or fail
- Temporary files or logs grow without being removed

## Investigation

1. Check filesystem utilization and available disk space.
2. Identify the directories and files consuming the most space.
3. Review recent deployments for retention or cleanup configuration changes.
4. Confirm whether temporary-file, log or index-segment cleanup is running.
5. Check inode usage when capacity appears available but writes still fail.

## Recommended remediation

Restore automatic cleanup or roll back the responsible deployment.

Remove only confirmed temporary files, then verify application recovery and available capacity.

A human operator must approve file deletion, storage expansion, configuration changes and rollbacks.
