param(
    [ValidateSet("object-access", "service-account")]
    [string]$RequestType = "object-access",

    [string]$RequestFile,

    [switch]$SkipTerraform
)

$ErrorActionPreference = "Stop"

$defaultRequestByType = @{
    "object-access" = "uda/requests/object-access/dev/RITMDEV0001.yaml"
    "service-account" = "uda/requests/service-account/dev/RITMDEVSA0001.yaml"
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
    Write-Host "Service-account Terraform resources are not implemented in this repo yet."
    Write-Host "Generated metadata artifacts are available under ./generated."
    exit 0
}

terraform -chdir=terraform init
terraform -chdir=terraform validate
terraform -chdir=terraform plan -var-file=../generated/terraform.auto.tfvars.json
