# Hooks Usage

This directory stores generic hooks only.

## Layout
- `runtime/`: runtime behavior hooks
- `governance/`: governance and promotion related hooks

## Selection Rules
- Keep only low-coupling infrastructure hooks with broad reuse value.
- Remove workflow-strategy hooks (for example: thinking-chain, search-tracker, phase-reminder, preflight-enforce, project-structure-enforce).
- Remove platform-specific or tool-specific hooks.
- New hooks should be reviewed before entering this directory.

## Naming
- Use kebab-case filenames ending with `.py`.
- Place governance hooks under `governance/`, others under `runtime/`.

## Current Generic Runtime Hooks
- `context-guard.py`
- `contract_utils.py`
- `pre-compress-guard.py`
