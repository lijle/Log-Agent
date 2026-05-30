# Null Pointer Diagnosis Guide

## Common Signals

- NullPointerException
- object field access on missing input
- exception happens in service business logic

## Common Root Causes

- missing null validation
- unexpected empty request body or missing fields
- object not initialized in exceptional path

## Recommended Checks

1. inspect the input payload shape
2. add guard clauses around nullable fields
3. confirm upstream contract changes
