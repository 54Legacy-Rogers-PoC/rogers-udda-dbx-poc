# Contributing

## Before Creating a PR

1. Run tests locally:

```powershell
python -m pytest -q
```

2. Keep workflow and script changes synchronized.
3. Avoid committing generated files (`__pycache__`, `.pytest_cache`, `.terraform`, output artifacts).

## Scope

Changes should focus on the active Excel-to-Terraform object-access flow under:

- `.github/workflows/uda-dbx-object-access.yml`
- `uda/scripts/object-access/`
- `terraform/`
