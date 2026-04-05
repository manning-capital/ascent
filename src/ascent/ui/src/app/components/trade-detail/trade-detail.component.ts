import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Card } from 'primeng/card';
import { TradeService } from '../../services/trade.service';
import { BadgeComponent } from '../shared/badge.component';
import { StatCardComponent } from '../shared/stat-card.component';
import { DataTableComponent } from '../shared/data-table/data-table.component';
import type { DataTableColumn } from '../shared/data-table/data-table.model';
import { DatePipe, JsonPipe } from '@angular/common';
import { Skeleton } from 'primeng/skeleton';

const directionSeverity: Record<string, string> = {
  LONG: 'success',
  SHORT: 'danger',
};

const sideSeverity: Record<string, string> = {
  BUY: 'success',
  SELL: 'danger',
};

const orderStatusSeverity: Record<string, string> = {
  FILLED: 'success',
  PARTIALLY_FILLED: 'warn',
  CANCELLED: 'secondary',
  REJECTED: 'danger',
  PENDING: 'info',
  NEW: 'info',
};

@Component({
  selector: 'app-trade-detail',
  standalone: true,
  imports: [RouterLink, BadgeComponent, StatCardComponent, DatePipe, JsonPipe, Card, Skeleton, DataTableComponent],
  templateUrl: './trade-detail.component.html',
})
export class TradeDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  tradeService = inject(TradeService);

  String = String;

  legColumns: DataTableColumn[] = [
    { field: 'instrument_name', header: 'Instrument' },
    {
      field: 'direction',
      header: 'Direction',
      cellType: 'tag',
      tagMapper: (v: string) => ({
        label: v,
        severity: directionSeverity[v] ?? 'secondary',
      }),
    },
    { field: 'quantity', header: 'Quantity' },
    {
      field: 'entry_price',
      header: 'Entry Price',
      cellType: 'currency',
    },
    {
      field: 'exit_price',
      header: 'Exit Price',
      cellType: 'currency',
    },
    {
      field: 'realized_pnl',
      header: 'P&L',
      cellType: 'currency',
    },
  ];

  orderColumns: DataTableColumn[] = [
    { field: 'timestamp', header: 'Time', cellType: 'date' },
    {
      field: 'side',
      header: 'Side',
      cellType: 'tag',
      tagMapper: (v: string) => ({
        label: v,
        severity: sideSeverity[v] ?? 'secondary',
      }),
    },
    { field: 'order_type', header: 'Type' },
    { field: 'quantity', header: 'Qty' },
    { field: 'price', header: 'Price', cellType: 'currency' },
    {
      field: 'filled_quantity',
      header: 'Filled',
      valueGetter: (params: any) => {
        const d = params.data;
        if (d?.filled_quantity !== null && d?.filled_quantity !== undefined) {
          return `${d.filled_quantity} / ${d.quantity}`;
        }
        return '--';
      },
    },
    { field: 'average_fill_price', header: 'Avg Fill', cellType: 'currency' },
    { field: 'exchange_name', header: 'Exchange', valueFormatter: (p: any) => p.value || '--' },
    {
      field: 'current_status',
      header: 'Status',
      cellType: 'tag',
      tagMapper: (v: string) => ({
        label: v,
        severity: orderStatusSeverity[v] ?? 'secondary',
      }),
    },
  ];

  snapshotColumns: DataTableColumn[] = [
    {
      field: 'snapshot_type',
      header: 'Type',
      cellType: 'tag',
      tagMapper: (v: string) => ({
        label: v,
        severity: 'secondary',
      }),
    },
    { field: 'attribute_name', header: 'Attribute' },
    { field: 'attribute_value', header: 'Value', cellType: 'monospace' },
    { field: 'timestamp', header: 'Timestamp', cellType: 'date' },
  ];

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      this.tradeService.loadTradeDetail(params.get('tradeId')!);
    });
  }
}
