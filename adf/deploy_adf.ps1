# Deploy all ADF artifacts for the Libstar cleaning pipeline.
# Run from anywhere; paths resolve relative to this script.

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$rg = "rg-pargoparcels"
$adf = "adf-pargoparcels-za"

az datafactory linked-service create -g $rg --factory-name $adf `
    --linked-service-name ls_adls --properties "@$here\linkedService_ls_adls.json" -o none
Write-Host "linked service ls_adls deployed"

foreach ($ds in "ds_raw_products", "ds_ref_brandmap", "ds_curated_products", "ds_quarantine") {
    az datafactory dataset create -g $rg --factory-name $adf `
        --dataset-name $ds --properties "@$here\dataset_$ds.json" -o none
    Write-Host "dataset $ds deployed"
}

az datafactory data-flow create -g $rg --factory-name $adf `
    --data-flow-name df_clean_products --flow-type "MappingDataFlow" `
    --properties "@$here\dataflow_df_clean_products.json" -o none
Write-Host "data flow df_clean_products deployed"

az datafactory pipeline create -g $rg --factory-name $adf `
    --pipeline-name pl_clean_products --pipeline "@$here\pipeline_pl_clean_products.json" -o none
Write-Host "pipeline pl_clean_products deployed"
