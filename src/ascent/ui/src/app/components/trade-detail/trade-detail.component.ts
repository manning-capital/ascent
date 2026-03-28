import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { TableModule } from 'primeng/table';
import { Card } from 'primeng/card';
import { TradeService } from '../../services/trade.service';
import { BadgeComponent } from '../shared/badge.component';
import { StatCardComponent } from '../shared/stat-card.component';
import { DatePipe, JsonPipe } from '@angular/common';
import { Skeleton } from 'primeng/skeleton';

@Component({
  selector: 'app-trade-detail',
  standalone: true,
  imports: [RouterLink, BadgeComponent, StatCardComponent, DatePipe, JsonPipe, TableModule, Card, Skeleton],
  templateUrl: './trade-detail.component.html',
})
export class TradeDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  tradeService = inject(TradeService);

  String = String;

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      this.tradeService.loadTradeDetail(params.get('tradeId')!);
    });
  }
}
