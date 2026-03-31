// Generic entity usage (used by all safe-delete dialogs)
export interface EntityUsageItem {
  label: string;
  count: number;
  kind: 'cascade' | 'reference';
}

export interface EntityUsage {
  items: EntityUsageItem[];
  total: number;
}

// Metadata Types
export interface MetadataTypeItem {
  id: string;
  name: string;
  display_name: string;
  description: string | null;
  value_type: string;
  is_active: boolean;
}

export interface MetadataTypeCreate {
  name: string;
  display_name: string;
  description?: string | null;
  value_type?: string;
}

export interface MetadataTypeUpdate {
  name?: string;
  display_name?: string;
  description?: string | null;
  value_type?: string;
  is_active?: boolean;
}

// Attributes
export interface AttributeItem {
  id: string;
  name: string;
  display_name: string;
  description: string | null;
  is_active: boolean;
  created_at: string | null;
}

export interface AttributeCreate {
  name: string;
  display_name: string;
  description?: string | null;
  is_active?: boolean;
}

export interface AttributeUpdate {
  name?: string;
  display_name?: string;
  description?: string | null;
  is_active?: boolean;
}
