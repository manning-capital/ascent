import { Component, inject, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { StrategyService } from '../../services/strategy.service';
import { TableModule } from 'primeng/table';
import { Card } from 'primeng/card';
import { Tag } from 'primeng/tag';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Skeleton } from 'primeng/skeleton';

@Component({
  selector: 'app-strategy-list',
  standalone: true,
  imports: [TableModule, Card, Tag, InputText, Select, Skeleton],
  templateUrl: './strategy-list.component.html',
})
export class StrategyListComponent implements OnInit {
  private router = inject(Router);
  strategyService = inject(StrategyService);

  statusOptions = [
    { label: 'Active', value: true },
    { label: 'Inactive', value: false },
  ];

  ngOnInit(): void {
    this.strategyService.loadStrategies();
  }

  navigateToStrategy(id: string): void {
    this.router.navigate(['/strategies', id]);
  }

  formatCurrency(value: number): string {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', signDisplay: 'always' }).format(value);
  }

  pnlClass(value: number): string {
    if (value === 0) return '';
    return value > 0 ? 'text-green-500' : 'text-red-500';
  }
}
