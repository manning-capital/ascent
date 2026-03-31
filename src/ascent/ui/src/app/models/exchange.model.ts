export interface ExchangeListItem {
  id: string;
  exchange_type_id: string;
  exchange_type_name: string | null;
  name: string;
  display_name: string;
  description: string | null;
  provider_id: string | null;
  provider_name: string | null;
  implementation_class: string | null;
  config: Record<string, any> | null;
  is_active: boolean;
  created_at: string | null;
}
