import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DatePipe, JsonPipe } from '@angular/common';
import { ExchangeService } from '../../../services/exchange.service';
import { Tag } from 'primeng/tag';
import { Card } from 'primeng/card';
import { Skeleton } from 'primeng/skeleton';

@Component({
  selector: 'app-exchange-detail',
  standalone: true,
  imports: [RouterLink, DatePipe, JsonPipe, Tag, Card, Skeleton],
  templateUrl: './exchange-detail.component.html',
})
export class ExchangeDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  exchangeService = inject(ExchangeService);

  private exchangeId = '';

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      const id = params.get('id')!;
      if (id === this.exchangeId) return;
      this.exchangeId = id;
      this.exchangeService.loadExchangeDetail(this.exchangeId);
    });
  }
}
