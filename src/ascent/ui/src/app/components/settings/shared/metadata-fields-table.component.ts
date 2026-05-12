import { Component, computed, input, output, viewChild, TemplateRef } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Button } from 'primeng/button';
import { Tag } from 'primeng/tag';
import { AppDataTableComponent } from '../../ui/data-table/app-data-table.component';
import type { AppColumn } from '../../ui/data-table/app-column.model';

export interface MetadataFieldRow {
  metadata_id: string;
  metadata_name: string;
  metadata_description: string | null;
  value_type: string;
  is_required: boolean;
  is_inherited: boolean;
  source_type_id: string | null;
  source_type_name: string | null;
}

const VALUE_TYPE_LABELS: Record<string, string> = {
  string: 'Text', integer: 'Integer', float: 'Float', boolean: 'Boolean',
  date: 'Date', time: 'Time', datetime: 'DateTime', enum: 'Enum', reference: 'Reference',
};

@Component({
  selector: 'app-metadata-fields-table',
  standalone: true,
  imports: [AppDataTableComponent, RouterLink, Button, Tag],
  template: `
    <ng-template #requiredTpl let-row>
      @if (row.is_required) {
        <span class="text-xs font-medium text-negative" [class.opacity-70]="row.is_inherited">Required</span>
      } @else {
        <span class="text-xs text-fg-faint">Optional</span>
      }
    </ng-template>

    <ng-template #sourceTpl let-row>
      @if (row.is_inherited && row.source_type_id) {
        <a [routerLink]="[routePrefix(), row.source_type_id]"
           (click)="$event.stopPropagation()"
           class="text-primary hover:underline text-xs">{{ row.source_type_name }}</a>
      } @else {
        <span class="text-xs text-fg-faint">This type</span>
      }
    </ng-template>

    <ng-template #valueTypeTpl let-row>
      <p-tag [value]="valueTypeLabel(row.value_type)" severity="secondary" />
    </ng-template>

    <ng-template #actionsTpl let-row>
      @if (!row.is_inherited) {
        <p-button (onClick)="onRemoveClick($event, row)"
                  severity="danger" [text]="true" size="small" label="Remove" />
      }
    </ng-template>

    <app-data-table
      [columns]="columns()"
      [value]="fields()"
      [emptyMessage]="emptyMessage()"
      [showPaginator]="false" />
  `,
})
export class MetadataFieldsTableComponent {
  fields = input.required<MetadataFieldRow[]>();
  routePrefix = input.required<string>();
  emptyMessage = input('No metadata fields defined.');

  removeField = output<string>();

  private requiredTpl = viewChild<TemplateRef<{ $implicit: MetadataFieldRow }>>('requiredTpl');
  private sourceTpl = viewChild<TemplateRef<{ $implicit: MetadataFieldRow }>>('sourceTpl');
  private valueTypeTpl = viewChild<TemplateRef<{ $implicit: MetadataFieldRow }>>('valueTypeTpl');
  private actionsTpl = viewChild<TemplateRef<{ $implicit: MetadataFieldRow }>>('actionsTpl');

  columns = computed<AppColumn<MetadataFieldRow>[]>(() => {
    const reqTpl = this.requiredTpl();
    const srcTpl = this.sourceTpl();
    const vtTpl = this.valueTypeTpl();
    const actTpl = this.actionsTpl();
    if (!reqTpl || !srcTpl || !vtTpl || !actTpl) return [];

    return [
      {
        field: 'metadata_name',
        header: 'Field Name',
        cellClass: (row) => row.is_inherited ? 'font-medium text-fg-muted' : 'font-medium',
        sortable: false,
      },
      {
        field: 'value_type',
        header: 'Value Type',
        cellTemplate: vtTpl,
        sortable: false,
      },
      {
        field: 'is_required',
        header: 'Required',
        cellTemplate: reqTpl,
        sortable: false,
        width: 110,
      },
      {
        field: 'source_type_name',
        header: 'Source',
        cellTemplate: srcTpl,
        sortable: false,
      },
      {
        field: 'metadata_description',
        header: 'Description',
        cellClass: 'text-xs text-fg-muted',
        format: (v) => v || '-',
        sortable: false,
      },
      {
        field: '__actions',
        header: '',
        cellTemplate: actTpl,
        sortable: false,
        width: 100,
      },
    ];
  });

  valueTypeLabel(vt: string): string {
    return VALUE_TYPE_LABELS[vt] ?? vt;
  }

  onRemoveClick(event: Event, row: MetadataFieldRow): void {
    event.stopPropagation();
    this.removeField.emit(row.metadata_id);
  }
}
