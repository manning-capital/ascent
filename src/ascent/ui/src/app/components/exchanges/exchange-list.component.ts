import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { ExchangeService } from '../../services/exchange.service';
import { StatCardComponent } from '../shared/stat-card.component';
import { Card } from 'primeng/card';
import { Skeleton } from 'primeng/skeleton';
import { EmptyStateComponent } from '../shared/empty-state.component';

@Component({
  selector: 'app-exchange-list',
  standalone: true,
  imports: [RouterLink, DatePipe, StatCardComponent, Card, Skeleton, EmptyStateComponent],
  templateUrl: './exchange-list.component.html',
})
export class ExchangeListComponent implements OnInit {
  exchangeService = inject(ExchangeService);

  ngOnInit(): void {
    this.exchangeService.loadExchanges();
  }
}
