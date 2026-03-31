import { MetadataEntry, ProviderAssetLink } from './asset.model';

export interface ProviderListItem {
  id: string;
  provider_type_id: string;
  provider_type_name: string | null;
  name: string;
  display_name: string;
  description: string | null;
  provider_external_code: string | null;
  underlying_provider_id: string | null;
  url: string | null;
  image_url: string | null;
  is_active: boolean;
  created_at: string | null;
}

export interface ProviderDetail extends ProviderListItem {
  metadata: MetadataEntry[];
  asset_links: ProviderAssetLink[];
}

export interface ProviderCreate {
  provider_type_id: string;
  name: string;
  display_name: string;
  description?: string | null;
  provider_external_code?: string | null;
  underlying_provider_id?: string | null;
  url?: string | null;
  image_url?: string | null;
  is_active?: boolean;
}

export interface ProviderUpdate {
  name?: string;
  display_name?: string;
  description?: string | null;
  provider_external_code?: string | null;
  url?: string | null;
  image_url?: string | null;
  is_active?: boolean;
}
