import { TypeItem } from './asset.model';

export interface CompositeMember {
  composite_id: string;
  instrument_id: string;
  instrument_name: string | null;
  instrument_display_name: string | null;
  order: number;
}

export interface Composite {
  id: string;
  name: string;
  display_name: string;
  composite_type_id: string;
  description: string | null;
  is_active: boolean;
  members: CompositeMember[];
  created_at: string | null;
}

export interface CompositeCreate {
  name: string;
  display_name: string;
  composite_type_id: string;
  description?: string;
  is_active?: boolean;
  members?: CompositeMemberCreate[];
}

export interface CompositeMemberCreate {
  instrument_id: string;
  order: number;
}

export interface CompositeTypeItem extends TypeItem {
  min_members: number;
  max_members: number;
}

export interface CompositeTypeCreate {
  name: string;
  display_name: string;
  description?: string;
  parent_type_id?: string | null;
  min_members?: number;
  max_members?: number;
}

export type CompositeTypeMetadataField = {
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
};

export type CompositeTypeMetadataCreate = {
  metadata_id: string;
  is_required: boolean;
  display_order: number;
};

export interface CompositeUniverseItem {
  composite_id: string;
  composite_name: string | null;
  composite_display_name: string | null;
  composite_type_id: string | null;
  is_active: boolean;
  order: number;
}
