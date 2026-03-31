export interface OrderListItem {
  id: string;
  timestamp: string;
  order_type: string;
  side: string;
  instrument_id: string;
  instrument_name: string;
  quantity: number;
  price: number;
  filled_quantity: number | null;
  average_fill_price: number | null;
  external_order_id: string | null;
  time_in_force: string | null;
  current_status: string | null;
  exchange_name: string | null;
}

export interface OrderStatus {
  timestamp: string;
  status: string;
  error_message: string | null;
  error_code: string | null;
}

export interface OrderDetail extends OrderListItem {
  statuses: OrderStatus[];
}
