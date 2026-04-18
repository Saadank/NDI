#!/usr/bin/env bash
# launch-vm-retry.sh
# Paste into OCI Cloud Shell and run.
# It resolves every OCID it needs by NAME (so it works in any tenancy with the
# same naming), then loops `oci compute instance launch` every 60s until the
# Out-of-capacity error stops. Stops as soon as the instance is accepted.
#
# Configuration you can tweak:
COMPARTMENT_NAME="datasharing-prod"
VCN_NAME="datasharing-vcn"
SUBNET_NAME_PATTERN="public subnet-datasharing-vcn"   # wizard-generated name
VAULT_NAME="datasharing-vault"
KEY_NAME="datasharing-master-key"
INSTANCE_NAME="datasharing-app-01"
OS_NAME="Canonical Ubuntu"
OS_VERSION="22.04"
SHAPE="VM.Standard.A1.Flex"
OCPUS=4
MEMORY_GB=24
BOOT_VOL_GB=100
SSH_PUB_KEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKt0xglo9D2Ck2wTwxVgDw2niKgne9esxDBI+APNupi9 datasharing-ops'
RETRY_SECONDS=60

set -uo pipefail

echo "==> Resolving tenancy + compartment"
TENANCY_OCID=$(oci iam compartment list --all --compartment-id-in-subtree true \
  --query "data[?\"name\"=='root'].\"compartment-id\" | [0]" --raw-output 2>/dev/null \
  || oci iam availability-domain list --query 'data[0]."compartment-id"' --raw-output)

COMP_OCID=$(oci iam compartment list --all \
  --compartment-id-in-subtree true \
  --query "data[?\"name\"=='${COMPARTMENT_NAME}'].id | [0]" --raw-output)
[[ -z "$COMP_OCID" || "$COMP_OCID" == "null" ]] && { echo "Compartment $COMPARTMENT_NAME not found"; exit 1; }

echo "==> Resolving AD (Riyadh has one: AD-1)"
AD_NAME=$(oci iam availability-domain list --compartment-id "$COMP_OCID" \
  --query 'data[0]."name"' --raw-output)

echo "==> Resolving subnet"
SUBNET_OCID=$(oci network subnet list --compartment-id "$COMP_OCID" --all \
  --query "data[?contains(\"display-name\",'${SUBNET_NAME_PATTERN}')].id | [0]" --raw-output)
[[ -z "$SUBNET_OCID" || "$SUBNET_OCID" == "null" ]] && { echo "Subnet not found"; exit 1; }

echo "==> Resolving latest Ubuntu 22.04 aarch64 image"
IMAGE_OCID=$(oci compute image list --compartment-id "$COMP_OCID" --all \
  --operating-system "$OS_NAME" --operating-system-version "$OS_VERSION" \
  --shape "$SHAPE" \
  --sort-by TIMECREATED --sort-order DESC \
  --query 'data[0].id' --raw-output)
[[ -z "$IMAGE_OCID" || "$IMAGE_OCID" == "null" ]] && { echo "Image not found"; exit 1; }

echo "==> Resolving vault key"
VAULT_OCID=$(oci kms management vault list --compartment-id "$COMP_OCID" --all \
  --query "data[?\"display-name\"=='${VAULT_NAME}'].id | [0]" --raw-output)
MGMT_ENDPOINT=$(oci kms management vault get --vault-id "$VAULT_OCID" \
  --query 'data."management-endpoint"' --raw-output)
KEY_OCID=$(oci kms management key list --compartment-id "$COMP_OCID" \
  --endpoint "$MGMT_ENDPOINT" --all \
  --query "data[?\"display-name\"=='${KEY_NAME}'].id | [0]" --raw-output)

echo
echo "Resolved:"
echo "  Compartment : $COMP_OCID"
echo "  AD          : $AD_NAME"
echo "  Subnet      : $SUBNET_OCID"
echo "  Image       : $IMAGE_OCID"
echo "  Key         : $KEY_OCID"
echo

METADATA_FILE=$(mktemp)
printf '{"ssh_authorized_keys":"%s"}' "$SSH_PUB_KEY" > "$METADATA_FILE"

SHAPE_CFG=$(mktemp)
printf '{"ocpus":%d,"memoryInGBs":%d}' "$OCPUS" "$MEMORY_GB" > "$SHAPE_CFG"

SRC_DETAILS=$(mktemp)
cat > "$SRC_DETAILS" <<EOF
{
  "sourceType": "image",
  "imageId": "$IMAGE_OCID",
  "bootVolumeSizeInGBs": $BOOT_VOL_GB,
  "kmsKeyId": "$KEY_OCID"
}
EOF

i=0
while :; do
  i=$((i+1))
  TS=$(date -Iseconds)
  echo "[$TS] Attempt $i — launching..."
  OUT=$(oci compute instance launch \
    --availability-domain "$AD_NAME" \
    --compartment-id "$COMP_OCID" \
    --display-name "$INSTANCE_NAME" \
    --shape "$SHAPE" \
    --shape-config "file://$SHAPE_CFG" \
    --subnet-id "$SUBNET_OCID" \
    --source-details "file://$SRC_DETAILS" \
    --assign-public-ip true \
    --metadata "file://$METADATA_FILE" \
    --is-pv-encryption-in-transit-enabled true \
    --wait-for-state RUNNING \
    --wait-interval-seconds 15 \
    2>&1) && {
      echo "[$TS] SUCCESS"
      echo "$OUT" | tail -30
      rm -f "$METADATA_FILE" "$SHAPE_CFG" "$SRC_DETAILS"
      exit 0
    }

  # Print first useful line and keep looping on capacity errors
  echo "$OUT" | grep -Ei 'out of capacity|out of host capacity|host capacity|ServiceErr' | head -1
  echo "[$TS] Attempt $i failed. Sleeping ${RETRY_SECONDS}s..."
  sleep "$RETRY_SECONDS"
done
