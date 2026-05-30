# Database Connection Diagnosis Guide

## Common Signals

- SQLTransientConnectionException
- connection pool timeout
- database not reachable or overloaded

## Common Root Causes

- connection pool exhausted
- database CPU or connection count too high
- wrong credentials, endpoint, or network route

## Recommended Checks

1. inspect pool usage and wait time
2. verify database health and max connections
3. confirm application configuration values
