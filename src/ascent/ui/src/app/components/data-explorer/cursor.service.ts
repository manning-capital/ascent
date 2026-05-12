import { Injectable, signal } from '@angular/core';

/** Synchronizes the hover cursor (a timestamp on the time axis) across all
 *  time-axis chart cells in the Data Explorer notebook. Each cell publishes
 *  its hovered timestamp here on mousemove and subscribes to render a vertical
 *  guideline at the published timestamp when it falls within its own x-range.
 *
 *  Provided at the workspace component level (not root) so two notebooks in
 *  separate routes don't share state. */
@Injectable()
export class DataExplorerCursorService {
  /** Hovered timestamp in epoch milliseconds, or ``null`` when no cell is
   *  being hovered. */
  readonly cursor = signal<number | null>(null);

  set(timestamp: number | null): void {
    this.cursor.set(timestamp);
  }

  clear(): void {
    this.cursor.set(null);
  }
}
