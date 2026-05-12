export interface FilterOption {
  id: string;
  display_name: string;
}

export interface DataExplorerFilterOptions {
  entities: FilterOption[];
  descriptors: FilterOption[];
  periods: FilterOption[] | null;
}

export interface DataSourceInfo {
  table: string;
  label: string;
  entity_type: string;
  descriptor_type: string;
  has_period: boolean;
}

export interface DataSeriesPoint {
  timestamp: string;
  value: number | null;
}

export interface DataSeriesResponse {
  points: DataSeriesPoint[];
  entity_label: string;
  descriptor_label: string;
}
