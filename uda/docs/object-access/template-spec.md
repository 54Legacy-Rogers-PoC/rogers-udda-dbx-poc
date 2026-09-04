# Databricks Object Access Template Specification

## 1. Purpose
This document defines the Excel template contract used for Databricks object access requests.
The template is the authoritative source for object-level entitlements used by the workflow.

## 2. File Location
- Request attachment folder: `uda/attachments/object-access/`
- Typical template naming: request-driven file names such as `RITM123456.xlsx`

## 3. Workbook and Worksheet Rules
1. Workbook can be `.xlsx`, `.xlsm`, or `.xls`.
2. Workflow reads worksheet named `Object List`.
3. First row must contain column headers exactly as specified.
4. Data records start at row 2.
5. Empty trailing rows are ignored.

## 4. Required Columns

| Column Name | Type | Required | Allowed Values / Format | Notes |
|---|---|---|---|---|
| Record_ID | string | Optional | Non-empty if provided | Row identifier |
| Activity | string | Yes | `ADD`, `REMOVE`, `REVOKE` | `REVOKE` is normalized to `REMOVE` |
| Environment | string | Yes | `DEV`, `QA`, `PRD` | |
| Access_For | string | Yes | `ad_group`, `service_account` | |
| Principal_Name | string | Yes | Non-empty | Group or service account name |
| Object_Type | string | Yes | `CATALOG`, `SCHEMA`, `VIEW`, `FOLDER` | Determines conditional fields |
| Catalog | string | Conditional | Non-empty text | Required for CATALOG/SCHEMA/VIEW |
| Schema | string | Conditional | Non-empty text | Required for SCHEMA/VIEW |
| Object_Name | string | Conditional | Non-empty text | Required for VIEW |
| Folder_Path | string | Conditional | Absolute path style | Required for FOLDER |
| Privilege | string | Yes | See Section 6 | Must be valid for object type |
| Justification | string | Yes | Non-empty | Business reason |
| Additional_Information | string | No | Free text | Optional notes |

## 5. Conditional Field Rules by Object_Type

| Object_Type | Required Fields | Must Be Empty |
|---|---|---|
| CATALOG | Catalog | Schema, Object_Name, Folder_Path |
| SCHEMA | Catalog, Schema | Object_Name, Folder_Path |
| VIEW | Catalog, Schema, Object_Name | Folder_Path |
| FOLDER | Folder_Path | Catalog, Schema, Object_Name |

## 6. Privilege Rules

Allowed privileges by object type:

| Object_Type | Allowed Privileges |
|---|---|
| CATALOG | `USE_CATALOG` |
| SCHEMA | `USE_SCHEMA`, `CREATE_TABLE`, `CREATE_VIEW` |
| VIEW | `SELECT` |
| FOLDER | `READ`, `WRITE`, `READ_WRITE` |

Validation behavior:
1. Privilege must be uppercase.
2. Privilege must exist in allowed set for the row's `Object_Type`.

## 7. Cross-Field Consistency Rules
1. `Environment`, `Access_For`, and `Principal_Name` must be consistent across rows for the same request context.
2. `Activity` values are normalized by workflow logic:
	- `ADD` stays `ADD`
	- `REMOVE` stays `REMOVE`
	- `REVOKE` is treated as `REMOVE`
3. Mixed activity templates (`ADD` + `REMOVE/REVOKE`) are supported.

## 8. Duplicate Detection
Rows are considered duplicates when all fields below match exactly:
- Activity
- Environment
- Access_For
- Principal_Name
- Object_Type
- Catalog
- Schema
- Object_Name
- Folder_Path
- Privilege

Duplicate rows are not allowed.

## 9. Processing Behavior
1. Template is parsed row-by-row.
2. Each valid row is transformed into one normalized entitlement record.
3. If one or more rows fail validation, the default behavior is to fail the full request.
4. No Terraform plan/apply occurs when template validation fails.

## 10. Maximum Size
1. Current recommended limit: 1000 data rows per template.
2. This limit is provisional pending DD-02 confirmation.
3. Requests exceeding the maximum row count fail validation.

## 11. Error Codes for Template Validation

| Code | Meaning |
|---|---|
| TPL-001 | Workbook file missing/unreadable |
| TPL-002 | Worksheet `Object List` missing |
| TPL-003 | Missing required column(s) |
| TPL-004 | Invalid enum value |
| TPL-005 | Conditional field rule failure |
| TPL-006 | Duplicate row detected |
| TPL-007 | Invalid privilege for object type |
| TPL-008 | Cross-field mismatch with request context |
| TPL-009 | Exceeded maximum row count |
| TPL-010 | Mandatory value blank |

## 12. Example Rows

| Record_ID | Activity | Environment | Access_For | Principal_Name | Object_Type | Catalog | Schema | Object_Name | Folder_Path | Privilege | Justification | Additional_Information |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OA-0001 | ADD | PRD | ad_group | DTB_FINANCE_ANALYTICS | CATALOG | fin_prd |  |  |  | USE_CATALOG | Finance reporting | Quarterly close |
| OA-0002 | ADD | PRD | ad_group | DTB_FINANCE_ANALYTICS | SCHEMA | fin_prd | gl |  |  | USE_SCHEMA | Finance reporting |  |
| OA-0003 | ADD | PRD | service_account | svc_fin_loader | VIEW | fin_prd | gl | v_monthly_close |  | SELECT | ETL read access | Nightly run |
| OA-0004 | REMOVE | QA | ad_group | DTB_TEST_USERS | FOLDER |  |  |  | /Volumes/qa/raw/sales | READ | Cleanup old access | Ticket closure |

## 13. Security and Logging
1. Template must not include secrets, tokens, passwords, or credentials.
2. Validation logs must include row number and error code, but must not expose secrets.
3. Logs should include request_id, principal, environment, activity, and object count.
