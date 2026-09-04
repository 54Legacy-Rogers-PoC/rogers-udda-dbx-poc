param(
    [ValidateSet("object-access", "service-account")]
    [string]$RequestType = "object-access",

    [string]$RequestFile,

    [switch]$SkipTerraform
)

$ErrorActionPreference = "Stop"

# Default sample request per supported request type.
$defaultRequestByType = @{
    "object-access" = "requests/object-access/dev/RITMDEV0001.yaml"
    "service-account" = "requests/service-account/dev/RITMDEVSA0001.yaml"
}

if ([string]::IsNullOrWhiteSpace($RequestFile)) {
    $RequestFile = $defaultRequestByType[$RequestType]
}

if (-not (Test-Path -Path $RequestFile)) {
    throw "Request file not found: $RequestFile"
}

$processorByType = @{
    "object-access" = "uda/scripts/process_request.py"
    "service-account" = "uda/scripts/process_service_account_request.py"
}

$processor = $processorByType[$RequestType]
if (-not (Test-Path -Path $processor)) {
    throw "Processor script not found: $processor"
}

Write-Host "Running local UDA flow for request type: $RequestType"
Write-Host "Request file: $RequestFile"

python -m pip install --upgrade pip
python -m pip install -r uda/scripts/requirements.txt
python $processor --request-file $RequestFile --config-file uda/config/environments.yaml --output-dir generated

if ($SkipTerraform) {
    Write-Host "SkipTerraform enabled. Stopping after request processing."
    exit 0
}

if ($RequestType -eq "service-account") {
    # Skip Terraform for metadata-only service-account activities.
    $metadata = Get-Content -Path "generated/request_metadata.json" -Raw | ConvertFrom-Json
    if (-not $metadata.requires_terraform) {
        Write-Host "Service-account request is metadata-only. Terraform not required."
        exit 0
    }
}

terraform -chdir=terraform/environments/dev init
terraform -chdir=terraform/environments/dev validate
terraform -chdir=terraform/environments/dev plan -var-file=../../../generated/terraform.auto.tfvars.json
