# Authentication Error Diagnosis Guide

## Common Signals

- 401 unauthorized
- invalid token signature
- token expired or missing permission

## Common Root Causes

- expired or malformed bearer token
- permission scope mismatch
- auth service clock skew or verification failure

## Recommended Checks

1. inspect token expiration and issuer
2. validate required scopes and roles
3. compare app server time with auth provider time
