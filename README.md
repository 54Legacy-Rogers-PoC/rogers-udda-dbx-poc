# Rogers UDA Databricks Object Access

This repository automates Databricks object-access grants and revokes from Excel templates.

## Current Flow

1. Detect template files under `uda/attachments/object-access/`.
2. Validate and parse `Object List` worksheet rows.
3. Generate Terraform tfvars JSON.
4. Plan and apply Databricks grant changes:
	- `ADD`
	- `REMOVE` / `REVOKE` (targeted destroy with import fallback)
	- `MIXED` (REMOVE phase + ADD phase)

## Main Workflow

- `.github/workflows/uda-dbx-object-access.yml`

## Active Scripts

- `uda/scripts/object-access/collect_template_files.sh`
- `uda/scripts/object-access/validate_template.py`
- `uda/scripts/object-access/parse_template.py`
- `uda/scripts/object-access/generate_tfvars.py`
- `uda/scripts/object-access/determine_request_activity.py`
- `uda/scripts/object-access/build_import_tfvars.py`

## Testing

Run unit tests:

```powershell
python -m pytest -q
```
