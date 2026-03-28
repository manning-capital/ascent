import { Component, inject, OnInit, signal, effect } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { Select } from 'primeng/select';
import { DatePicker } from 'primeng/datepicker';
import { InputText } from 'primeng/inputtext';
import { Card } from 'primeng/card';
import { Button } from 'primeng/button';
import { SelectButton } from 'primeng/selectbutton';
import { TradeService } from '../../services/trade.service';
import { StrategyService } from '../../services/strategy.service';
import { TradeTableComponent } from '../trade-table/trade-table.component';

@Component({
  selector: 'app-trade-list',
  standalone: true,
  imports: [FormsModule, Select, DatePicker, InputText, Card, Button, SelectButton, TradeTableComponent],
  templateUrl: './trade-list.component.html',
})
export class TradeListComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  tradeService = inject(TradeService);
  strategyService = inject(StrategyService);

  search = signal('');
  status = signal('');
  selectedStrategyId = signal<number | null>(null);
  selectedTags = signal<string[]>([]);
  startDate = signal<Date | null>(null);
  endDate = signal<Date | null>(null);
  page = signal(1);

  availableTags = ['LONG', 'SHORT', 'COMPOUND', 'PAPER'];
  statusOptions = [
    { label: 'Pending', value: 'PENDING' },
    { label: 'Opening', value: 'OPENING' },
    { label: 'Open', value: 'OPEN' },
    { label: 'Closing', value: 'CLOSING' },
    { label: 'Closed', value: 'CLOSED' },
    { label: 'Cancelled', value: 'CANCELLED' },
    { label: 'Error', value: 'ERROR' },
  ];
  private isSyncingFromUrl = false;

  constructor() {
    effect(() => {
      if (this.isSyncingFromUrl) return;
      this.loadTrades();
    });
  }

  ngOnInit(): void {
    this.strategyService.loadStrategies();
    this.route.queryParams.subscribe(params => {
      this.isSyncingFromUrl = true;
      if (params['search']) this.search.set(params['search']);
      if (params['status']) this.status.set(params['status']);
      if (params['strategy_id']) this.selectedStrategyId.set(Number(params['strategy_id']));
      if (params['tags']) this.selectedTags.set(Array.isArray(params['tags']) ? params['tags'] : [params['tags']]);
      if (params['start_date']) this.startDate.set(new Date(params['start_date'] + 'T00:00:00'));
      if (params['end_date']) this.endDate.set(new Date(params['end_date'] + 'T00:00:00'));
      if (params['page']) this.page.set(Number(params['page']));
      this.isSyncingFromUrl = false;
      this.loadTrades();
    });
  }

  loadTrades(): void {
    const params: Record<string, any> = {
      page: this.page(),
      page_size: 10,
    };
    if (this.search()) params['search'] = this.search();
    if (this.status()) params['status'] = this.status();
    if (this.selectedStrategyId()) params['strategy_id'] = this.selectedStrategyId();
    if (this.selectedTags().length) params['tags'] = this.selectedTags();
    if (this.startDate()) params['start_date'] = this.startDate()!.toISOString().split('T')[0];
    if (this.endDate()) params['end_date'] = this.endDate()!.toISOString().split('T')[0];

    this.tradeService.loadTrades(params);
    this.updateUrl(params);
  }

  private updateUrl(params: Record<string, any>): void {
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: params,
      queryParamsHandling: 'replace',
    });
  }

  toggleTag(tag: string): void {
    this.selectedTags.update(tags =>
      tags.includes(tag) ? tags.filter(t => t !== tag) : [...tags, tag]
    );
    this.page.set(1);
  }

  onSearch(value: string): void {
    this.search.set(value);
    this.page.set(1);
  }

  onStatusChange(value: string | null): void {
    this.status.set(value ?? '');
    this.page.set(1);
  }

  onStrategyChange(value: number | null): void {
    this.selectedStrategyId.set(value);
    this.page.set(1);
  }

  onPageChange(newPage: number): void {
    this.page.set(newPage);
    this.loadTrades();
  }

  clearFilters(): void {
    this.search.set('');
    this.status.set('');
    this.selectedStrategyId.set(null);
    this.selectedTags.set([]);
    this.startDate.set(null);
    this.endDate.set(null);
    this.page.set(1);
  }
}
