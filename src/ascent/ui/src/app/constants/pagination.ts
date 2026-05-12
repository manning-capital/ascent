/** Default rows-per-page across every list and embedded table.
 *  Set with the compact-density redesign in mind: rows are ~28px, so 50
 *  fits comfortably above the fold on a typical laptop. */
export const DEFAULT_PAGE_SIZE = 50;

/** Selectable rows-per-page options surfaced by the paginator dropdown. */
export const PAGE_SIZE_OPTIONS: number[] = [25, 50, 100, 200];
