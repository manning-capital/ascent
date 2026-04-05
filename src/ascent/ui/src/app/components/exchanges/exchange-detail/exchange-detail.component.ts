import { Component, computed, inject, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { JsonPipe } from '@angular/common';
import { ExchangeService } from '../../../services/exchange.service';
import { Tag } from 'primeng/tag';
import { Card } from 'primeng/card';
import { Skeleton } from 'primeng/skeleton';
import { FieldPanelComponent, PanelField } from '../../shared/field-panel.component';

@Component({
  selector: 'app-exchange-detail',
  standalone: true,
  imports: [RouterLink, JsonPipe, Tag, Card, Skeleton, FieldPanelComponent],
  templateUrl: './exchange-detail.component.html',
})
export class ExchangeDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  exchangeService = inject(ExchangeService);

  private exchangeId = '';

  generalFields = computed<PanelField[]>(() => {
    const exchange = this.exchangeService.selectedExchange();
    if (!exchange) return [];
    return [
      { type: 'mono', key: 'name', label: 'Name', value: exchange.name },
      { type: 'text', key: 'displayName', label: 'Display Name', value: exchange.display_name },
      { type: 'text', key: 'type', label: 'Type', value: exchange.exchange_type_name, fallback: '--' },
      { type: 'link', key: 'instrumentType', label: 'Instrument Type', value: exchange.instrument_type_name, route: exchange.instrument_type_id ? ['/settings/instrument-types', exchange.instrument_type_id] : [], fallback: 'Any' },
      { type: 'link', key: 'provider', label: 'Provider', value: exchange.provider_name, route: exchange.provider_id ? ['/settings/providers', exchange.provider_id] : [], fallback: 'None' },
      { type: 'active', key: 'isActive', label: 'Active', value: exchange.is_active },
      { type: 'date', key: 'created', label: 'Created', value: exchange.created_at },
      { type: 'text', key: 'description', label: 'Description', value: exchange.description },
    ];
  });

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      const id = params.get('id')!;
      if (id === this.exchangeId) return;
      this.exchangeId = id;
      this.exchangeService.loadExchangeDetail(this.exchangeId);
    });
  }
}
