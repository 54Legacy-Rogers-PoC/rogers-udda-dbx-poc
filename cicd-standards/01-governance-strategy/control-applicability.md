# CI/CD Control Applicability

## Purpose

This document defines which CI/CD Standardization Framework controls apply to the Databricks Unified Data Access Automation (UDAA) repository.

Control applicability is determined based on the repository classification, workload characteristics, target platform, deployment model, and risk profile.

---

## Repository Classification

| Attribute | Classification |
|---|---|
| Workload | Databricks Unified Data Access Automation |
| Platform | Azure Databricks |
| Repository Type | Data Platform / Access Automation |
| CI/CD Platform | GitHub Actions |
| Infrastructure / Automation | Terraform |
| Deployment Environments | DEV / TEST / PROD |
| Production Deployment | Yes |
| Infrastructure / Platform Changes | Yes |
| Access / Entitlement Changes | Yes |
| Baseline Profile | TBD |
| Workload Profile | TBD |
| Platform Overlay | Azure Databricks |
| Additional Risk Overlay | TBD |

---

## Applicability Decision

Each CI/CD Standardization Framework control must be classified using one of the following statuses:

| Status | Definition |
|---|---|
| Applicable | The control applies and must be implemented for this repository. |
| Not Applicable | The control does not apply because of the repository architecture, workload type, platform, or operating model. A justification is required. |
| Exception | The control applies but cannot currently be fully implemented. An approved exception or waiver is required. |
| Planned | The control applies and implementation is approved but not yet complete. The corresponding backlog item must be referenced. |

---

## Control Applicability Matrix

The table below is the repository-specific record of CI/CD control applicability.

| Control ID | Domain | Control | Applicability | Repository Implementation / Justification | Evidence / Reference |
|---|---|---|---|---|---|
| TBD | Governance & Strategy | Repository / Workload Framework Ownership | Applicable | Repository requires defined workload, repository, platform, and CI/CD governance ownership. | Governance README |
| TBD | Governance & Strategy | Policy and Standard Definition | Applicable | Repository must comply with applicable enterprise and CI/CD standards. | Governance README |
| TBD | Governance & Strategy | Control Expectations by Repository / Workload Type | Applicable | Repository is classified as an Azure Databricks access-automation workload and requires repository-specific control applicability assessment. | This document |
| TBD | Governance & Strategy | Exception and Waiver Process | Applicable | Applicable controls that cannot be implemented require documented exception management. | exceptions-and-waivers.md |
| TBD | Governance & Strategy | Governance Review Cadence | Applicable | Repository compliance and evidence must be periodically reviewed. | Governance README |
| TBD | Governance & Strategy | Continuous Improvement Backlog | Applicable | Deferred controls and CI/CD improvements must be tracked through the approved backlog. | Jira / TBD |

The remaining CI/CD Standardization Framework controls must be added to this matrix as the repository assessment progresses.

---

## Applicability Principles

Controls are assessed against the actual Databricks UDAA implementation rather than marked applicable by default.

Platform-specific controls should consider the Azure Databricks deployment model, Terraform implementation, GitHub Actions workflows, repository protections, security controls, validation requirements, release process, evidence generation, and operational support model.

A control that is technically relevant but not yet implemented must not be classified as **Not Applicable**.

Such a control must instead be recorded as **Planned**, **Exception**, or an identified remediation item.

---

## Review and Maintenance

This applicability assessment must be reviewed when there is a significant change to:

- Repository architecture
- GitHub Actions workflows
- Terraform implementation
- Azure Databricks platform integration
- Deployment environments
- Security requirements
- CI/CD Standardization Framework
- Repository risk classification

Changes to control applicability must include a justification and corresponding evidence or backlog reference where required.