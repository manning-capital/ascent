/**
 * Map structured close-reason codes to friendly UI text.
 *
 * Backend writes ``close_reason`` values like:
 *  - Free-form strings from user strategies (``"MEAN_REVERT"``, ``"STOP_LOSS"``, ``"MANUAL"``)
 *  - Structured rejection codes from the route gate: ``"UNIVERSE_SCOPE:<reason>"``
 *
 * This util leaves free-form strings untouched and maps the structured
 * codes to human-readable labels.
 */

const UNIVERSE_SCOPE_LABELS: Record<string, string> = {
  provider_mismatch: 'Provider / instrument-type mismatch',
  assignment_missing: 'Strategy not linked to this exchange',
  assignment_disabled: 'Strategy-exchange link disabled',
  strategy_paused: 'Strategy paused',
  exchange_missing: 'Exchange configuration missing',
  instrument_missing: 'Instrument configuration missing',
};

export function formatCloseReason(raw: string | null | undefined): string {
  if (!raw) return '';
  if (raw.startsWith('UNIVERSE_SCOPE:')) {
    const code = raw.slice('UNIVERSE_SCOPE:'.length);
    return UNIVERSE_SCOPE_LABELS[code] ?? `Rejected — ${code}`;
  }
  return raw;
}
