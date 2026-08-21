import argparse
import json
from dataclasses import dataclass
from typing import Any
from urllib import parse, request


AZURE_DATABRICKS_RESOURCE_ID = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d"


class ClusterAccessError(Exception):
    pass


@dataclass
class ClusterAccessRequest:
    host: str
    tenant_id: str
    client_id: str
    client_secret: str
    activity: str
    service_account_name: str
    cluster_id: str
    cluster_name: str
    permission_level: str


def _http_json(url: str, method: str = "GET", headers: dict[str, str] | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    req = request.Request(url=url, method=method, headers=headers or {}, data=body)
    try:
        with request.urlopen(req) as response:
            raw = response.read().decode("utf-8")
    except Exception as exc:
        raise ClusterAccessError(f"HTTP request failed for {method} {url}: {exc}") from exc

    if not raw.strip():
        return {}

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ClusterAccessError(f"Invalid JSON response from {method} {url}") from exc


def get_azure_access_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
    form = parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "resource": AZURE_DATABRICKS_RESOURCE_ID,
        }
    ).encode("utf-8")

    req = request.Request(
        url=token_url,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=form,
    )
    try:
        with request.urlopen(req) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise ClusterAccessError(f"Failed to obtain Azure AD token: {exc}") from exc

    token = str(payload.get("access_token", "")).strip()
    if not token:
        raise ClusterAccessError("Azure AD token response missing access_token")
    return token


def normalize_host(host: str) -> str:
    value = host.strip()
    if not value:
        raise ClusterAccessError("Databricks host is required")
    return value.rstrip("/")


def resolve_cluster_id(host: str, token: str, cluster_id: str, cluster_name: str) -> str:
    if cluster_id.strip():
        return cluster_id.strip()
    if not cluster_name.strip():
        raise ClusterAccessError("Either cluster_id or cluster_name must be provided")

    url = f"{host}/api/2.0/clusters/list"
    response = _http_json(url, headers={"Authorization": f"Bearer {token}"})
    clusters = response.get("clusters", [])

    matches = [c for c in clusters if str(c.get("cluster_name", "")).strip() == cluster_name.strip()]
    if not matches:
        raise ClusterAccessError(f"Cluster not found by name: {cluster_name}")
    if len(matches) > 1:
        raise ClusterAccessError(
            f"Multiple clusters found with name '{cluster_name}'. Provide cluster_id in the request for disambiguation."
        )

    resolved = str(matches[0].get("cluster_id", "")).strip()
    if not resolved:
        raise ClusterAccessError(f"Cluster id not available for cluster '{cluster_name}'")
    return resolved


def build_updated_acl(
    existing_acl: list[dict[str, Any]],
    activity: str,
    service_account_name: str,
    permission_level: str,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = [
        entry for entry in existing_acl if str(entry.get("service_principal_name", "")).strip() != service_account_name
    ]

    if activity == "ADD_TO_CLUSTER":
        filtered.append(
            {
                "service_principal_name": service_account_name,
                "permission_level": permission_level,
            }
        )

    return filtered


def apply_cluster_acl_change(req_data: ClusterAccessRequest) -> dict[str, Any]:
    host = normalize_host(req_data.host)

    token = get_azure_access_token(
        tenant_id=req_data.tenant_id,
        client_id=req_data.client_id,
        client_secret=req_data.client_secret,
    )

    cluster_id = resolve_cluster_id(
        host=host,
        token=token,
        cluster_id=req_data.cluster_id,
        cluster_name=req_data.cluster_name,
    )

    get_url = f"{host}/api/2.0/permissions/clusters/{cluster_id}"
    current = _http_json(get_url, headers={"Authorization": f"Bearer {token}"})
    existing_acl = current.get("access_control_list", [])

    if not isinstance(existing_acl, list):
        raise ClusterAccessError("Unexpected permissions payload: access_control_list must be a list")

    updated_acl = build_updated_acl(
        existing_acl=existing_acl,
        activity=req_data.activity,
        service_account_name=req_data.service_account_name,
        permission_level=req_data.permission_level,
    )

    put_payload = {"access_control_list": updated_acl}
    _http_json(
        get_url,
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        payload=put_payload,
    )

    return {
        "status": "SUCCESS",
        "activity": req_data.activity,
        "service_account_name": req_data.service_account_name,
        "cluster_id": cluster_id,
        "cluster_name": req_data.cluster_name,
        "permission_level": req_data.permission_level,
        "existing_acl_count": len(existing_acl),
        "updated_acl_count": len(updated_acl),
    }


def write_status(path: str, payload: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Databricks cluster permissions for service accounts")
    parser.add_argument("--host", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--client-secret", required=True)
    parser.add_argument("--activity", required=True, choices=["ADD_TO_CLUSTER", "REMOVE_FROM_CLUSTER"])
    parser.add_argument("--service-account-name", required=True)
    parser.add_argument("--cluster-id", required=False, default="")
    parser.add_argument("--cluster-name", required=False, default="")
    parser.add_argument("--permission-level", required=False, default="CAN_ATTACH_TO")
    parser.add_argument("--status-file", required=True)
    args = parser.parse_args()

    request_data = ClusterAccessRequest(
        host=args.host,
        tenant_id=args.tenant_id,
        client_id=args.client_id,
        client_secret=args.client_secret,
        activity=args.activity,
        service_account_name=args.service_account_name,
        cluster_id=args.cluster_id,
        cluster_name=args.cluster_name,
        permission_level=args.permission_level,
    )

    result = apply_cluster_acl_change(request_data)
    write_status(args.status_file, result)
    print(
        f"Cluster access update completed. activity={result['activity']} service_account={result['service_account_name']} cluster_id={result['cluster_id']}"
    )


if __name__ == "__main__":
    try:
        main()
    except ClusterAccessError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
