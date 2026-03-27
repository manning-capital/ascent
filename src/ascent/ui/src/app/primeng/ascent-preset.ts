import { GlobalPassThrough } from 'primeng/config';

/**
 * Ascent PrimeNG Pass-Through preset.
 *
 * Maps PrimeNG component DOM sections to Tailwind classes using the
 * Monokai Pro design tokens defined in styles.css. Applied globally
 * via providePrimeNG() in app.config.ts — individual components can
 * override sections via [pt] input.
 */
export const AscentPreset: GlobalPassThrough = {
  // ── Toast ──────────────────────────────────────────────────────
  toast: {
    root: { class: 'fixed bottom-6 right-6 z-50 flex flex-col gap-2 w-80' },
    message: ({ instance }: any) => {
      const severity = instance?.message?.severity;
      const base = 'flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg border backdrop-blur-sm text-sm';
      const variants: Record<string, string> = {
        success: `${base} bg-positive/90 border-positive/50 text-white`,
        error: `${base} bg-negative/90 border-negative/50 text-white`,
        info: `${base} bg-elevated/90 border-edge text-fg`,
      };
      return { class: variants[severity] ?? variants['info'] };
    },
    messageContent: { class: 'flex items-center gap-3 flex-1' },
    messageIcon: { class: 'shrink-0 text-base' },
    messageText: { class: 'flex-1' },
    summary: { class: 'sr-only' },
    detail: { class: 'text-sm' },
    closeButton: { class: 'shrink-0 text-current opacity-60 hover:opacity-100 transition-opacity bg-transparent border-none cursor-pointer p-1' },
    closeIcon: { class: 'w-3.5 h-3.5' },
  },

  // ── Tabs ───────────────────────────────────────────────────────
  tabs: {
    root: { class: '' },
  },
  tabList: {
    root: { class: 'flex border-b border-edge' },
    content: { class: 'flex' },
    tabList: { class: 'flex' },
    activeBar: { class: 'absolute bottom-0 h-0.5 bg-info transition-all duration-200' },
  },
  tab: {
    root: ({ context }: any) => ({
      class: [
        'px-4 py-2 text-sm transition-colors relative cursor-pointer bg-transparent border-none',
        context?.active ? 'text-fg' : 'text-fg-muted hover:text-fg',
      ].join(' '),
    }),
  },

  // ── Tag ────────────────────────────────────────────────────────
  tag: {
    root: { class: 'inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wider' },
  },

  // ── Button (PT foundation for PrimeNG-rendered buttons) ────────
  button: {
    root: { class: 'inline-flex items-center justify-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors cursor-pointer border-none' },
  },

  // ── Select ─────────────────────────────────────────────────────
  select: {
    root: { class: 'relative w-full' },
    label: { class: 'block w-full px-3 py-2 rounded-lg bg-canvas border border-edge text-fg text-sm cursor-pointer truncate text-left' },
    dropdown: { class: 'absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none text-fg-muted' },
    dropdownIcon: { class: 'w-4 h-4' },
    pcOverlay: {
      root: { class: 'bg-surface border border-edge rounded-lg shadow-lg mt-1 z-50 overflow-hidden' },
    },
    list: { class: 'py-1 max-h-60 overflow-auto' },
    option: ({ context }: any) => ({
      class: [
        'px-3 py-2 text-sm cursor-pointer transition-colors',
        context?.selected ? 'bg-info/15 text-info' : 'text-fg hover:bg-fg/5',
        context?.focused ? 'bg-fg/5' : '',
        context?.disabled ? 'opacity-50 pointer-events-none' : '',
      ].join(' '),
    }),
    optionLabel: { class: '' },
    emptyMessage: { class: 'px-3 py-2 text-sm text-fg-muted' },
  },

  // ── DatePicker ─────────────────────────────────────────────────
  datepicker: {
    root: { class: 'relative w-full' },
    pcInputText: {
      root: { class: 'w-full px-3 py-2 rounded-lg bg-canvas border border-edge text-fg text-sm focus:outline-none focus:ring-1 focus:ring-info transition-colors' },
    },
    panel: { class: 'bg-surface border border-edge rounded-xl shadow-lg p-3 z-50' },
    header: { class: 'flex items-center justify-between mb-2' },
    title: { class: 'flex items-center gap-1' },
    selectMonth: { class: 'text-sm font-medium text-fg bg-transparent border-none cursor-pointer hover:text-info transition-colors' },
    selectYear: { class: 'text-sm font-medium text-fg bg-transparent border-none cursor-pointer hover:text-info transition-colors' },
    pcPrevButton: {
      root: { class: 'p-1 rounded-lg hover:bg-fg/10 text-fg-muted hover:text-fg transition-colors cursor-pointer bg-transparent border-none' },
    },
    pcNextButton: {
      root: { class: 'p-1 rounded-lg hover:bg-fg/10 text-fg-muted hover:text-fg transition-colors cursor-pointer bg-transparent border-none' },
    },
    tableHeaderCell: { class: 'p-1 text-xs text-fg-faint font-normal' },
    day: ({ context }: any) => ({
      class: [
        'w-8 h-8 rounded-lg text-sm flex items-center justify-center cursor-pointer transition-colors border-none',
        context?.selected ? 'bg-info text-white' : '',
        context?.today && !context?.selected ? 'text-info font-bold' : '',
        !context?.selected && !context?.today ? 'text-fg hover:bg-fg/5' : '',
        context?.otherMonth ? 'text-fg-faint' : '',
        context?.disabled ? 'opacity-30 pointer-events-none' : '',
      ].join(' '),
    }),
    timePicker: { class: 'flex items-center justify-center gap-2 border-t border-edge mt-2 pt-2' },
    hourPicker: { class: 'flex flex-col items-center' },
    separatorContainer: { class: 'flex items-center' },
    separator: { class: 'text-fg-muted' },
  },

  // ── Checkbox ───────────────────────────────────────────────────
  checkbox: {
    root: { class: 'relative inline-flex items-center cursor-pointer' },
    box: ({ context }: any) => ({
      class: [
        'w-4 h-4 rounded border flex items-center justify-center transition-colors',
        context?.checked ? 'bg-info border-info' : 'bg-canvas border-edge hover:border-fg-muted',
      ].join(' '),
    }),
    input: { class: 'sr-only' },
    icon: { class: 'w-3 h-3 text-white' },
  },

  // ── ToggleSwitch ───────────────────────────────────────────────
  toggleSwitch: {
    root: { class: 'relative inline-flex items-center cursor-pointer' },
    slider: ({ context }: any) => ({
      class: [
        'w-11 h-6 rounded-full transition-colors relative',
        context?.checked ? 'bg-info' : 'bg-elevated',
      ].join(' '),
    }),
    handle: ({ context }: any) => ({
      class: [
        'absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform',
        context?.checked ? 'translate-x-5.5' : 'translate-x-0.5',
      ].join(' '),
    }),
  },

  // ── InputNumber ────────────────────────────────────────────────
  inputNumber: {
    root: { class: 'relative w-full' },
    pcInputText: {
      root: { class: 'w-full px-3 py-2 rounded-lg bg-canvas border border-edge text-fg text-sm focus:outline-none focus:ring-1 focus:ring-info transition-colors' },
    },
  },

  // ── Splitter ─────────────────────────────────────────────────
  splitter: {
    root: { class: 'flex flex-nowrap h-full w-full' },
    panel: { class: 'overflow-hidden' },
    gutter: { class: 'w-1.5 shrink-0 cursor-col-resize bg-fg/5 hover:bg-info/40 active:bg-info/60 transition-colors relative' },
    gutterHandle: { class: 'hidden' },
  },

  // ── Dialog / ConfirmDialog ────────────────────────────────────
  dialog: {
    mask: { class: 'fixed inset-0 z-50 flex items-center justify-center bg-overlay' },
    root: { class: 'bg-surface border border-edge rounded-xl shadow-2xl w-full max-w-md mx-4' },
    header: { class: 'flex items-center justify-between px-6 pt-6 pb-0' },
    title: { class: 'text-sm font-semibold text-fg' },
    headerActions: { class: 'flex items-center' },
    pcCloseButton: { class: 'p-1.5 rounded-lg hover:bg-fg/10 text-fg-muted hover:text-fg transition-colors cursor-pointer bg-transparent border-none' },
    content: { class: 'px-6 py-4 text-sm text-fg-muted' },
    footer: { class: 'flex items-center justify-end gap-2 px-6 pb-6' },
  },
  confirmdialog: {
    root: { class: '' },
    icon: { class: 'hidden' },
    message: { class: '' },
    pcRejectButton: {
      root: { class: 'px-4 py-2 rounded-lg text-sm font-medium text-fg-muted bg-fg/5 hover:bg-fg/10 transition-colors cursor-pointer border-none' },
    },
    pcAcceptButton: {
      root: { class: 'px-4 py-2 rounded-lg text-sm font-medium text-white bg-negative hover:bg-negative/80 transition-colors cursor-pointer border-none' },
    },
  },

  // ── Tooltip ──────────────────────────────────────────────────
  tooltip: {
    root: { class: 'bg-surface border border-edge text-fg text-xs rounded-lg px-2 py-1 shadow-lg z-50' },
    text: { class: '' },
    arrow: { class: 'hidden' },
  },

  // ── DataTable ────────────────────────────────────────────────
  datatable: {
    root: { class: 'w-full' },
    tableContainer: { class: 'overflow-x-auto' },
    table: { class: 'w-full text-sm' },
    thead: { class: '' },
    headerRow: { class: 'border-b border-edge text-left text-xs font-medium text-fg-muted uppercase tracking-wider' },
    headerCell: { class: 'px-4 py-3' },
    tbody: { class: '' },
    bodyRow: { class: 'border-b border-edge-dim hover:bg-fg/5 transition-colors' },
    bodyCell: { class: 'px-4 py-3' },
    emptyMessage: { class: '' },
    emptyMessageCell: { class: 'px-4 py-12 text-center text-fg-faint' },
    pcPaginator: {
      root: { class: 'flex items-center justify-between px-3 py-2 border-t border-edge text-[11px] text-fg-muted' },
      content: { class: 'flex items-center gap-1.5 ml-auto' },
      prevButton: { class: 'px-2 py-0.5 rounded border border-edge hover:bg-fg/10 disabled:opacity-30 transition-colors cursor-pointer bg-transparent text-fg-muted text-[11px]' },
      nextButton: { class: 'px-2 py-0.5 rounded border border-edge hover:bg-fg/10 disabled:opacity-30 transition-colors cursor-pointer bg-transparent text-fg-muted text-[11px]' },
      firstButton: { class: 'hidden' },
      lastButton: { class: 'hidden' },
      pages: { class: 'flex items-center gap-0.5' },
      page: ({ context }: any) => ({
        class: [
          'w-6 h-6 rounded flex items-center justify-center text-[11px] cursor-pointer border-none transition-colors',
          context?.active ? 'bg-info/15 text-info font-medium' : 'text-fg-muted hover:bg-fg/5',
        ].join(' '),
      }),
    },
  },
};
