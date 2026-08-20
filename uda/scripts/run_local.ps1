param(
    [Parameter(Mandatory = $false)]
    [string]$RequestFile = "uda/requests/object-access/dev/RITMDEV0001.yaml"
)

$ErrorActionPreference = "Stop"

python -m pip install --upgrade pip
pip install -r uda/scripts/requirements.txt
python uda/scripts/process_request.py --request-file $RequestFile --config-file uda/config/environments.yaml --output-dir generated
terraform -chdir=terraform init
terraform -chdir=terraform validate
terraform -chdir=terraform plan -var-file=../generated/terraform.auto.tfvars.json
