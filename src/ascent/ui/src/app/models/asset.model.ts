export interface AssetListItem {
  id: string;
  asset_type_id: string;
  asset_type_name: string | null;
  name: string;
  symbol: string | null;
  description: string | null;
  underlying_asset_id: string | null;
  is_active: boolean;
  created_at: string | null;
}

export interface AssetCreate {
  asset_type_id: string;
  name: string;
  symbol?: string | null;
  description?: string | null;
  underlying_asset_id?: string | null;
  is_active?: boolean;
}

export interface AssetUpdate {
  name?: string;
  symbol?: string | null;
  description?: string | null;
  is_active?: boolean;
}

export interface ProviderAssetLink {
  provider_id: string;
  provider_name: string | null;
  asset_id: string;
  asset_name: string | null;
  asset_symbol: string | null;
  identifier: string;
  created_at: string | null;
}

export interface ProviderAssetLinkCreate {
  provider_id: string;
  asset_id: string;
  identifier: string;
}

export interface AssetGroupMember {
  provider_asset_group_id: string;
  provider_id: string;
  provider_name: string | null;
  from_asset_id: string;
  from_asset_symbol: string | null;
  to_asset_id: string;
  to_asset_symbol: string | null;
  order: number;
}

export interface AssetGroup {
  id: string;
  is_active: boolean;
  members: AssetGroupMember[];
  created_at: string | null;
}

export interface AssetGroupCreate {
  is_active?: boolean;
  members?: AssetGroupMemberCreate[];
}

export interface AssetGroupMemberCreate {
  provider_id: string;
  from_asset_id: string;
  to_asset_id: string;
  order: number;
}

export interface AssetDetail extends AssetListItem {
  metadata: MetadataEntry[];
  provider_links: ProviderAssetLink[];
}

export interface MetadataEntry {
  metadata_id: string;
  metadata_name: string;
  value: any;
  timestamp: string;
}

export interface MetadataEntryCreate {
  metadata_id: string;
  value: any;
  timestamp?: string;
}

export interface MetadataHistoryEntry {
  timestamp: string;
  value: any;
  created_at: string | null;
}

export interface MetadataHistoryUpdate {
  value?: any;
  timestamp?: string;
}

export interface MetadataType {
  id: string;
  name: string;
  description: string | null;
  value_type: string;
  is_active: boolean;
}

export interface AssetTypeMetadataField {
  metadata_id: string;
  metadata_name: string;
  metadata_description: string | null;
  value_type: string;
  is_required: boolean;
  display_order: number;
}

export interface AssetTypeMetadataCreate {
  metadata_id: string;
  is_required: boolean;
  display_order: number;
}

export interface ProviderTypeMetadataField {
  metadata_id: string;
  metadata_name: string;
  metadata_description: string | null;
  value_type: string;
  is_required: boolean;
  display_order: number;
}

export interface ProviderTypeMetadataCreate {
  metadata_id: string;
  is_required: boolean;
  display_order: number;
}

export interface TypeItem {
  id: string;
  name: string;
  description: string | null;
}

export interface UniverseItem {
  provider_id: string;
  provider_name: string | null;
  from_asset_id: string;
  from_asset_symbol: string | null;
  to_asset_id: string;
  to_asset_symbol: string | null;
  provider_asset_group_id: string;
  order: number;
}

export interface UniverseItemCreate {
  provider_id: string;
  from_asset_id: string;
  to_asset_id: string;
  provider_asset_group_id?: string | null;
  order: number;
}
