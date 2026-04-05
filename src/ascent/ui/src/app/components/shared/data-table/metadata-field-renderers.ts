import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { ICellRendererAngularComp } from 'ag-grid-angular';
import type { ICellRendererParams } from 'ag-grid-community';
import { Button } from 'primeng/button';

// ─── Required cell renderer (Required / Optional with inherited color) ─
@Component({
  selector: 'ag-metadata-required-cell',
  standalone: true,
  template: `
    @if (isRequired) {
      <span class="text-xs font-medium" [class]="isInherited ? 'text-red-400' : 'text-red-500'">Required</span>
    } @else {
      <span class="text-xs text-surface-400">Optional</span>
    }
  `,
  host: { style: 'display:flex;align-items:center;height:100%' },
})
export class MetadataRequiredRenderer implements ICellRendererAngularComp {
  isRequired = false;
  isInherited = false;

  agInit(params: ICellRendererParams): void {
    this.update(params);
  }

  refresh(params: ICellRendererParams): boolean {
    this.update(params);
    return true;
  }

  private update(params: ICellRendererParams): void {
    this.isRequired = params.data?.is_required ?? false;
    this.isInherited = params.data?.is_inherited ?? false;
  }
}

// ─── Source cell renderer (link to parent type or "This type") ─
@Component({
  selector: 'ag-metadata-source-cell',
  standalone: true,
  imports: [RouterLink],
  template: `
    @if (isInherited && route) {
      <a [routerLink]="route" (click)="$event.stopPropagation()" class="text-primary hover:underline text-xs">{{ sourceName }}</a>
    } @else {
      <span class="text-xs text-surface-400">This type</span>
    }
  `,
  host: { style: 'display:flex;align-items:center;height:100%' },
})
export class MetadataSourceRenderer implements ICellRendererAngularComp {
  isInherited = false;
  sourceName = '';
  route: any[] | null = null;
  private routePrefix = '';

  agInit(params: ICellRendererParams & { routePrefix?: string }): void {
    this.routePrefix = params.routePrefix ?? '';
    this.update(params);
  }

  refresh(params: ICellRendererParams & { routePrefix?: string }): boolean {
    this.update(params);
    return true;
  }

  private update(params: ICellRendererParams): void {
    this.isInherited = params.data?.is_inherited ?? false;
    this.sourceName = params.data?.source_type_name ?? '';
    this.route = this.isInherited && params.data?.source_type_id
      ? [this.routePrefix, params.data.source_type_id]
      : null;
  }
}

// ─── Remove button cell renderer (only for owned fields) ─
@Component({
  selector: 'ag-metadata-remove-cell',
  standalone: true,
  imports: [Button],
  template: `
    @if (!isInherited) {
      <p-button (onClick)="onRemoveClick($event)" severity="danger" [text]="true" size="small" label="Remove"/>
    }
  `,
  host: { style: 'display:flex;align-items:center;height:100%' },
})
export class MetadataRemoveRenderer implements ICellRendererAngularComp {
  isInherited = false;
  private data: any;
  private onRemove?: (data: any) => void;

  agInit(params: ICellRendererParams & { onRemove?: (data: any) => void }): void {
    this.onRemove = params.onRemove;
    this.update(params);
  }

  refresh(params: ICellRendererParams & { onRemove?: (data: any) => void }): boolean {
    this.update(params);
    return true;
  }

  private update(params: ICellRendererParams): void {
    this.data = params.data;
    this.isInherited = params.data?.is_inherited ?? false;
  }

  onRemoveClick(event: Event): void {
    event.stopPropagation();
    if (this.onRemove && this.data) {
      this.onRemove(this.data);
    }
  }
}
