import {
  AfterViewInit,
  Component,
  ElementRef,
  OnDestroy,
  computed,
  effect,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { ChartTokens, ChartTokensService } from './chart-tokens.service';

export interface ChartCanvasFrame {
  width: number;
  height: number;
  tokens: ChartTokens;
}

/**
 * Container for D3-rendered charts. Owns sizing (ResizeObserver-driven
 * width signal), aspect ratio, and token access via ChartTokensService.
 *
 *   <app-chart-canvas [aspectRatio]="2" (frame)="render($event)" />
 *
 * The (frame) output fires whenever width or theme changes — callers do
 * their D3 enter/update/exit inside the handler. The host <svg> is exposed
 * via the `svg` viewChild for direct selection.
 */
@Component({
  selector: 'app-chart-canvas',
  standalone: true,
  host: { class: 'block w-full h-full relative' },
  template: `
    <svg
      #svg
      [attr.width]="width()"
      [attr.height]="height()"
      [attr.viewBox]="'0 0 ' + width() + ' ' + height()"
      class="block w-full h-full overflow-visible"
      preserveAspectRatio="xMidYMid meet"
    ></svg>
  `,
})
export class AppChartCanvasComponent implements AfterViewInit, OnDestroy {
  aspectRatio = input<number | undefined>(undefined);
  minHeight = input<number>(120);
  fixedHeight = input<number | undefined>(undefined);

  readonly frame = output<ChartCanvasFrame>();

  readonly svg = viewChild.required<ElementRef<SVGSVGElement>>('svg');

  readonly width = signal(0);
  readonly height = computed(() => {
    if (this.fixedHeight() != null) return this.fixedHeight()!;
    const ar = this.aspectRatio();
    const w = this.width();
    if (ar && w > 0) return Math.max(this.minHeight(), Math.round(w / ar));
    return this.minHeight();
  });

  private observer?: ResizeObserver;

  constructor(private host: ElementRef<HTMLElement>, private tokens: ChartTokensService) {
    effect(() => {
      const w = this.width();
      const h = this.height();
      const t = this.tokens.tokens();
      if (w > 0 && h > 0) {
        this.frame.emit({ width: w, height: h, tokens: t });
      }
    });
  }

  ngAfterViewInit(): void {
    const el = this.host.nativeElement;
    this.observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const w = Math.round(entry.contentRect.width);
      if (w !== this.width()) this.width.set(w);
    });
    this.observer.observe(el);
    this.width.set(Math.round(el.clientWidth));
  }

  ngOnDestroy(): void {
    this.observer?.disconnect();
  }
}
