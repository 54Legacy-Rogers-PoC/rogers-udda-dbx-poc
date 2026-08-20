# Databricks Object Access Request YAML Specification

## 1. Purpose
This specification defines the Request-as-Code YAML contract for Databricks object access requests in the UDA framework.

Each request YAML contains request metadata and a reference to an attached object access template file.

## 2. File Location and Naming
- Location: `uda/requests/object-access/`
- File name pattern: `RITM<digits>.yaml`
- Example: `RITM123456.yaml`

## 3. Required Fields

| Field | Type | Required | Allowed Values / Format | Notes |
|---|---|---|---|---|
| request_id | string | Yes | `RITM` followed by digits | Must match file name stem |
| platform | string | Yes | `databricks` | Lowercase fixed value |
| request_type | string | Yes | `object_access` | Lowercase fixed value |
| environment | string | Yes | `DEV`, `QA`, `PRD` | ESMT values are mapped before YAML creation |
| activity_type | string | Yes | `ADD`, `REMOVE` | Request-level default activity |
| access_for | string | Yes | `ad_group`, `service_account` | Principal type |
| template_file | string | Yes | `.xlsx` filename | Must exist in attachment location |
| justification | string | Yes | 1 to 1000 chars | Non-empty business justification |

## 4. Conditional Fields

| Field | Required When | Notes |
|---|---|---|
| ad_group_name | `access_for=ad_group` | AD group principal name |
| service_account_name | `access_for=service_account` | Service account principal name |

## 5. Optional Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| additional_information | string | No | Free text for context |
| ad_group_description | string | No | Can be auto-populated from source form |
| ad_group_owner_name | string | No | Can be auto-populated from source form |
| ad_group_owner_email | string | No | Can be auto-populated from source form |
| service_account_owner_name | string | No | Can be auto-populated from source form |
| service_account_owner_email | string | No | Can be auto-populated from source form |

## 6. Validation Rules
1. YAML must be valid and parse successfully.
2. All required fields must be present and non-empty.
3. `request_id` must match regex: `^RITM[0-9]+$`.
4. YAML file name must equal `<request_id>.yaml`.
5. `platform` must be `databricks`.
6. `request_type` must be `object_access`.
7. `environment` must be one of `DEV`, `QA`, `PRD`.
8. `activity_type` must be one of `ADD`, `REMOVE`.
9. `access_for` must be one of `ad_group`, `service_account`.
10. If `access_for=ad_group`, then `ad_group_name` is mandatory and `service_account_name` should be empty or omitted.
11. If `access_for=service_account`, then `service_account_name` is mandatory and `ad_group_name` should be empty or omitted.
12. `template_file` must end with `.xlsx` and resolve to a real file in `uda/attachments/object-access/`.
13. `justification` must not be blank after trimming whitespace.
14. Unknown fields are allowed but should be logged as warnings for forward compatibility.

## 7. Processing Semantics
1. The YAML stores request-level metadata only.
2. Object-level entitlements are sourced from the referenced Excel template.
3. If the template includes an Activity column, row-level activity overrides request-level `activity_type`.
4. If the template does not include row-level activity, all rows inherit request-level `activity_type`.

## 8. Example YAML (AD Group, ADD)

```yaml
request_id: RITM123456
platform: databricks
request_type: object_access
environment: PRD
activity_type: ADD
access_for: ad_group
ad_group_name: DTB_FINANCE_ANALYTICS
ad_group_description: Finance Analytics access group
ad_group_owner_name: Jane Smith
ad_group_owner_email: jane.smith@rogers.com
service_account_name: ""
service_account_owner_name: ""
service_account_owner_email: ""
template_file: ObjectAccessTemplate.xlsx
justification: Finance analytics reporting access for quarterly close
additional_information: Approved ESMT request with object access template attached
```

## 9. Example YAML (Service Account, REMOVE)

```yaml
request_id: RITM123457
platform: databricks
request_type: object_access
environment: QA
activity_type: REMOVE
access_for: service_account
ad_group_name: ""
service_account_name: svc_fin_loader
service_account_owner_name: Data Platform Team
service_account_owner_email: dataplatform@rogers.com
template_file: ObjectAccessTemplate.xlsx
justification: Remove deprecated QA access
additional_information: Decommission cleanup request
```

## 10. Standard Error Codes

| Code | Meaning |
|---|---|
| YML-001 | YAML parsing failed |
| YML-002 | Missing required field |
| YML-003 | Invalid enum value |
| YML-004 | Invalid request_id format |
| YML-005 | request_id and filename mismatch |
| YML-006 | Conditional field validation failed |
| YML-007 | template_file missing or invalid extension |
| YML-008 | Referenced template file not found |
| YML-009 | justification is blank |
| YML-010 | Unsupported platform or request_type |

## 11. Security Notes
1. Do not include secrets, tokens, passwords, or credentials in YAML.
2. PII should be minimized to business-required metadata only.
3. Validation logs must never echo sensitive values.
