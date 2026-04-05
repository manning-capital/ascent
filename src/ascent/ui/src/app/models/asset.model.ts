export interface AssetListItem {
  id: string;
  asset_type_id: string;
  asset_type_name: string | null;
  name: string;
  display_name: string;
  description: string | null;
  underlying_asset_id: string | null;
  is_active: boolean;
  created_at: string | null;
}

export interface AssetCreate {
  asset_type_id: string;
  name: string;
  display_name: string;
  description?: string | null;
  underlying_asset_id?: string | null;
  is_active?: boolean;
}

export interface AssetUpdate {
  name?: string;
  display_name?: string;
  description?: string | null;
  is_active?: boolean;
  asset_type_id?: string;
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

export interface Instrument {
  id: string;
  name: string;
  display_name: string;
  instrument_type_id: string;
  provider_id: string;
  provider_name: string | null;
  from_asset_id: string;
  from_asset_name: string | null;
  to_asset_id: string;
  to_asset_name: string | null;
  description: string | null;
  is_active: boolean;
  created_at: string | null;
}

export interface InstrumentCreate {
  name: string;
  display_name: string;
  instrument_type_id: string;
  provider_id: string;
  from_asset_id: string;
  to_asset_id: string;
  description?: string;
  is_active?: boolean;
}

export interface AssetDetail extends AssetListItem {
  metadata: MetadataEntry[];
  provider_links: ProviderAssetLink[];
}

export interface MetadataEntry {
  metadata_id: string;
  metadata_name: string;
  metadata_display_name: string;
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
  display_name: string;
  description: string | null;
  value_type: string;
  config: Record<string, any> | null;
  is_active: boolean;
}

export interface AssetTypeMetadataField {
  metadata_id: string;
  metadata_name: string;
  metadata_display_name: string;
  metadata_description: string | null;
  value_type: string;
  config: Record<string, any> | null;
  is_required: boolean;
  display_order: number;
  is_inherited: boolean;
  source_type_id: string | null;
  source_type_name: string | null;
}

export interface AssetTypeMetadataCreate {
  metadata_id: string;
  is_required: boolean;
  display_order: number;
}

// Provider-asset metadata field definitions at the asset type level (same shape)
export type AssetTypeProviderAssetMetadataField = AssetTypeMetadataField;
export type AssetTypeProviderAssetMetadataCreate = AssetTypeMetadataCreate;

export interface ProviderTypeMetadataField {
  metadata_id: string;
  metadata_name: string;
  metadata_display_name: string;
  metadata_description: string | null;
  value_type: string;
  config: Record<string, any> | null;
  is_required: boolean;
  display_order: number;
  is_inherited: boolean;
  source_type_id: string | null;
  source_type_name: string | null;
}

export interface ProviderTypeMetadataCreate {
  metadata_id: string;
  is_required: boolean;
  display_order: number;
}

export interface TypeItem {
  id: string;
  name: string;
  display_name: string;
  description: string | null;
  parent_type_id: string | null;
}

export interface TypeHierarchyNode extends TypeItem {
  children: TypeHierarchyNode[];
}

export interface InstrumentTypeItem extends TypeItem {}

export interface InstrumentTypeCreate {
  name: string;
  display_name: string;
  description?: string;
  parent_type_id?: string | null;
}

export interface InstrumentTypeMetadataField {
  metadata_id: string;
  metadata_name: string;
  metadata_display_name: string | null;
  metadata_description: string | null;
  value_type: string;
  config: Record<string, any> | null;
  is_required: boolean;
  display_order: number;
  is_inherited: boolean;
  source_type_id: string | null;
  source_type_name: string | null;
}

export type InstrumentTypeMetadataCreate = AssetTypeMetadataCreate;

export interface MetadataConflict {
  metadata_id: string;
  metadata_name: string;
  metadata_display_name: string;
  value_type: string;
  config: Record<string, any> | null;
  child_is_required: boolean;
  parent_is_required: boolean;
  parent_source_type_name: string;
}

export interface ReparentPreview {
  child_id: string;
  child_name: string;
  new_parent_id: string;
  new_parent_name: string;
  child_own_fields: AssetTypeMetadataField[];
  parent_effective_fields: AssetTypeMetadataField[];
  conflicts: MetadataConflict[];
  child_own_provider_asset_fields?: AssetTypeMetadataField[] | null;
  parent_effective_provider_asset_fields?: AssetTypeMetadataField[] | null;
  provider_asset_conflicts?: MetadataConflict[] | null;
}

export interface BatchMetadataEntry {
  metadata_id: string;
  value: any;
}

export interface BatchMetadataCreate {
  timestamp: string;
  entries: BatchMetadataEntry[];
}

export interface MetadataFieldInfo {
  metadata_id: string;
  metadata_name: string;
  metadata_display_name: string;
  value_type: string;
  config: Record<string, any> | null;
}

export interface MetadataSnapshotRow {
  timestamp: string;
  values: Record<string, any>;
}

export interface MetadataHistoryGrid {
  fields: MetadataFieldInfo[];
  snapshots: MetadataSnapshotRow[];
}

export interface BulkHistoryUpdateEntry {
  old_timestamp: string;
  new_timestamp?: string | null;
  metadata_id: string;
  value: any;
}

export interface BulkHistoryInsertEntry {
  timestamp: string;
  metadata_id: string;
  value: any;
}

export interface BulkHistoryDeleteEntry {
  timestamp: string;
  metadata_id?: string | null;
}

export interface BulkHistoryUpdate {
  updates: BulkHistoryUpdateEntry[];
  inserts: BulkHistoryInsertEntry[];
  deletes: BulkHistoryDeleteEntry[];
}

export interface UniverseItem {
  instrument_id: string;
  instrument_name: string | null;
  instrument_display_name: string | null;
  instrument_type_id: string | null;
  is_active: boolean;
  order: number;
}

export interface UniverseItemCreate {
  instrument_id: string;
  order: number;
}
