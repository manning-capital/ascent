import { Component, inject, OnInit } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { ExchangeService } from '../../services/exchange.service';
import { TableModule } from 'primeng/table';
import { Card } from 'primeng/card';
import { Tag } from 'primeng/tag';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Skeleton } from 'primeng/skeleton';

@Component({
  selector: 'app-exchange-list',
  standalone: true,
  imports: [DatePipe, RouterLink, TableModule, Card, Tag, InputText, Select, Skeleton],
  templateUrl: './exchange-list.component.html',
})
export class ExchangeListComponent implements OnInit {
  private router = inject(Router);
  exchangeService = inject(ExchangeService);

  statusOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

  ngOnInit(): void {
    this.exchangeService.loadExchanges();
  }

  navigateToExchange(id: string): void {
    this.router.navigate(['/exchanges', id]);
  }
}
