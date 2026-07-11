terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }

  backend "azurerm" {}
}

provider "azurerm" {
  features {}
}

data "azurerm_client_config" "current" {}

variable "location" {
  type    = string
  default = "eastus"
}

resource "azurerm_resource_group" "urp" {
  name     = "urp-platform-rg"
  location = var.location
}

resource "azurerm_storage_account" "urp" {
  name                            = "urpplatformstore"
  resource_group_name             = azurerm_resource_group.urp.name
  location                        = azurerm_resource_group.urp.location
  account_tier                    = "Standard"
  account_replication_type        = "ZRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false

  blob_properties {
    versioning_enabled = true
    delete_retention_policy {
      days = 30
    }
    container_delete_retention_policy {
      days = 30
    }
  }
}

resource "azurerm_storage_container" "urp" {
  name                  = "urp-chunks"
  storage_account_name  = azurerm_storage_account.urp.name
  container_access_type = "private"
}

resource "azurerm_key_vault" "urp" {
  name                        = "urp-platform-kv"
  location                    = azurerm_resource_group.urp.location
  resource_group_name         = azurerm_resource_group.urp.name
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  sku_name                    = "standard"
  enabled_for_disk_encryption = true
  purge_protection_enabled    = true
  soft_delete_retention_days  = 30
}

resource "azurerm_key_vault_key" "urp" {
  name         = "urp-envelope"
  key_vault_id = azurerm_key_vault.urp.id
  key_type     = "RSA"
  key_size     = 3072
  key_opts     = ["decrypt", "encrypt", "unwrapKey", "wrapKey"]
}

# Platform contract: production deployments wire this to Azure Database for PostgreSQL,
# Azure Blob Storage, Key Vault, and AKS/Container Apps through environment-specific modules.
output "urp_platform_contract" {
  value = {
    object_backend  = azurerm_storage_container.urp.name
    kms_backend     = azurerm_key_vault_key.urp.id
    manifest_store  = "azure-postgresql"
    deployment_mode = "aks-or-container-apps"
  }
}
