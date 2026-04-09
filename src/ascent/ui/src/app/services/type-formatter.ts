import { DatePipe } from '@angular/common';
import type { ValueFormatterFunc } from 'ag-grid-community';

const datePipe = new DatePipe('en-US');

/**
 * Returns an ag-grid ValueFormatterFunc for the given type.
 * Extensible with additional types and configurable settings later.
 */
export function typeFormatter(type: string): ValueFormatterFunc {
  switch (type) {
    case 'date':
      return (params) => {
        if (!params.value) return '';
        return datePipe.transform(params.value, 'MMM d, yyyy HH:mm:ss') ?? String(params.value);
      };
    default:
      return (params) => params.value ?? '';
  }
}
