# Timeout Diagnosis Guide

## Common Signals

- Read timeout
- HTTP 504 or gateway timeout
- repeated retry attempts for the same trace id

## Common Root Causes

- downstream dependency latency spike
- network jitter between services
- timeout threshold is too low for current traffic

## Recommended Checks

1. compare upstream and downstream latency percentiles
2. inspect error rate changes during the same time window
3. check recent deployment or configuration changes
4. verify retry count and timeout configuration
