import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { IFloatingFilterAngularComp } from 'ag-grid-angular';
import type { IFloatingFilterParams } from 'ag-grid-community';
import { Select } from 'primeng/select';
import { MultiSelect } from 'primeng/multiselect';

// ─── Custom floating filter: PrimeNG Select (single) ────────
@Component({
  selector: 'ag-select-floating-filter',
  standalone: true,
  imports: [FormsModule, Select],
  template: `
    <p-select
      [ngModel]="value"
      (ngModelChange)="onChanged($event)"
      [options]="options"
      [placeholder]="placeholder"
      optionLabel="label"
      optionValue="value"
      [showClear]="true"
      [style]="{ width: '100%' }"
      styleClass="ag-floating-select"
      [appendTo]="'body'"
      size="small"/>
  `,
  styles: [`
    :host { display: flex; align-items: center; width: 100%; height: 100%; }
    :host ::ng-deep .ag-floating-select { width: 100%; }
    :host ::ng-deep .ag-floating-select .p-select {
      border: none; border-radius: 0; background: transparent; box-shadow: none;
      min-height: unset; height: 100%; font-size: 0.8rem;
    }
    :host ::ng-deep .ag-floating-select .p-select-label { font-size: 0.8rem; padding: 0 0.5rem; }
  `],
})
export class SelectFloatingFilter implements IFloatingFilterAngularComp {
  value: any = null;
  options: { label: string; value: any }[] = [];
  placeholder = 'All';
  private params!: IFloatingFilterParams & { filterOptions?: any[]; filterPlaceholder?: string };

  agInit(params: IFloatingFilterParams & { filterOptions?: any[]; filterPlaceholder?: string }): void {
    this.params = params;
    this.options = params.filterOptions ?? [];
    this.placeholder = params.filterPlaceholder ?? 'All';
  }

  onParentModelChanged(parentModel: any): void {
    this.value = parentModel?.filter ?? null;
  }

  onChanged(value: any): void {
    this.params.parentFilterInstance((instance: any) => {
      if (value == null) {
        instance.setModel(null);
      } else {
        instance.setModel({ filterType: 'text', type: 'equals', filter: value });
      }
    });
  }
}

// ─── Custom floating filter: PrimeNG MultiSelect ────────────
@Component({
  selector: 'ag-multiselect-floating-filter',
  standalone: true,
  imports: [FormsModule, MultiSelect],
  template: `
    <p-multiselect
      [ngModel]="value"
      (ngModelChange)="onChanged($event)"
      [options]="options"
      [placeholder]="placeholder"
      [maxSelectedLabels]="1"
      [selectedItemsLabel]="'{0} selected'"
      [showClear]="true"
      [style]="{ width: '100%' }"
      styleClass="ag-floating-multiselect"
      [appendTo]="'body'"
      size="small"/>
  `,
  styles: [`
    :host { display: flex; align-items: center; width: 100%; height: 100%; }
    :host ::ng-deep .ag-floating-multiselect { width: 100%; }
    :host ::ng-deep .ag-floating-multiselect .p-multiselect {
      border: none; border-radius: 0; background: transparent; box-shadow: none;
      min-height: unset; height: 100%; font-size: 0.8rem;
    }
    :host ::ng-deep .ag-floating-multiselect .p-multiselect-label { font-size: 0.8rem; padding: 0 0.5rem; }
  `],
})
export class MultiSelectFloatingFilter implements IFloatingFilterAngularComp {
  value: any[] = [];
  options: string[] = [];
  placeholder = 'All';
  private params!: IFloatingFilterParams & { filterOptions?: any[]; filterPlaceholder?: string };

  agInit(params: IFloatingFilterParams & { filterOptions?: any[]; filterPlaceholder?: string }): void {
    this.params = params;
    this.options = params.filterOptions ?? [];
    this.placeholder = params.filterPlaceholder ?? 'All';
  }

  onParentModelChanged(parentModel: any): void {
    if (!parentModel) {
      this.value = [];
    } else {
      this.value = parentModel.values ?? [];
    }
  }

  onChanged(values: any[]): void {
    this.params.parentFilterInstance((instance: any) => {
      if (!values || values.length === 0) {
        instance.setModel(null);
      } else {
        // Use a custom filter model that the parent text filter interprets
        instance.setModel({ filterType: 'text', type: 'inSet', values });
      }
    });
  }
}
