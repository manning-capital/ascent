import { Component, input, output, signal, effect, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Observable } from 'rxjs';
import { AutoComplete } from 'primeng/autocomplete';

export interface SearchOption {
  label: string;
  value: any;
}

@Component({
  selector: 'app-search-select',
  standalone: true,
  imports: [FormsModule, AutoComplete],
  host: { class: 'block' },
  template: `
    @if (multiple()) {
      <p-autoComplete
        [(ngModel)]="selectedItems"
        [suggestions]="suggestions()"
        (completeMethod)="onSearch($event)"
        (ngModelChange)="onMultiChange($event)"
        optionLabel="label"
        [multiple]="true"
        [forceSelection]="true"
        [dropdown]="true"
        [placeholder]="placeholder()"
        styleClass="w-full"
      />
    } @else {
      <p-autoComplete
        [(ngModel)]="selectedItem"
        [suggestions]="suggestions()"
        (completeMethod)="onSearch($event)"
        (onSelect)="onItemSelect($event)"
        (onClear)="onItemClear()"
        optionLabel="label"
        [forceSelection]="true"
        [dropdown]="true"
        [placeholder]="placeholder()"
        styleClass="w-full"
      />
    }
  `,
})
export class SearchSelectComponent implements OnInit {
  searchFn = input.required<(query: string) => Observable<SearchOption[]>>();
  value = input<any>();
  displayValue = input<string | null>();
  placeholder = input('Search...');
  multiple = input(false);
  valueChange = output<any>();

  suggestions = signal<SearchOption[]>([]);
  selectedItem: SearchOption | null = null;
  selectedItems: SearchOption[] = [];

  private initialized = false;

  ngOnInit(): void {
    if (!this.multiple()) {
      const v = this.value();
      const dv = this.displayValue();
      if (v && dv) {
        this.selectedItem = { label: dv, value: v };
      }
    }
    this.initialized = true;
  }

  constructor() {
    effect(() => {
      const v = this.value();
      const dv = this.displayValue();
      if (!this.initialized) return;
      if (!this.multiple()) {
        if (v && dv) {
          if (this.selectedItem?.value !== v) {
            this.selectedItem = { label: dv, value: v };
          }
        } else if (!v) {
          this.selectedItem = null;
        }
      }
    });
  }

  onSearch(event: any): void {
    this.searchFn()(event.query).subscribe(results => {
      this.suggestions.set(results);
    });
  }

  onItemSelect(event: any): void {
    this.valueChange.emit(event.value.value);
  }

  onItemClear(): void {
    this.valueChange.emit(null);
  }

  onMultiChange(items: SearchOption[]): void {
    this.valueChange.emit(items);
  }
}
