import {
  Component,
  Input,
  ElementRef,
  ViewChild,
  AfterViewInit,
  OnDestroy,
  signal,
} from '@angular/core';
import * as d3 from 'd3';

export interface GraphBounds {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
}

const ANIM_DURATION = 300;

@Component({
  selector: 'app-graph-canvas',
  standalone: true,
  imports: [],
  template: `
    <div
      #container
      class="w-full h-full overflow-hidden relative select-none rounded-lg border border-edge-dim">
      <svg #svgEl class="absolute top-0 left-0" width="100%" height="100%"
           [style.visibility]="ready ? 'visible' : 'hidden'">
        <g #zoomGroup></g>
      </svg>

      <!-- Controls -->
      <div class="absolute bottom-3 left-3 flex items-center gap-1 bg-surface/80 rounded-lg border border-edge p-1">
        <button (click)="zoomOut()" class="w-7 h-7 flex items-center justify-center text-fg-muted hover:text-fg rounded hover:bg-fg/10 text-sm">-</button>
        <span class="text-xs text-fg-faint w-10 text-center">{{ Math.round(currentScale() * 100) }}%</span>
        <button (click)="zoomIn()" class="w-7 h-7 flex items-center justify-center text-fg-muted hover:text-fg rounded hover:bg-fg/10 text-sm">+</button>
        <button (click)="fitToContainer()" class="w-7 h-7 flex items-center justify-center text-fg-muted hover:text-fg rounded hover:bg-fg/10 text-xs">Fit</button>
        <ng-content select="[graphControls]"/>
      </div>

      <ng-content select="[graphOverlay]"/>
    </div>
  `,
  host: { class: 'block h-full' },
})
export class GraphCanvasComponent implements AfterViewInit, OnDestroy {
  @Input() contentBounds: GraphBounds | null = null;
  @Input() ready = false;
  @Input() padding = 40;
  @Input() maxFitScale = 1.5;

  @ViewChild('container') containerRef!: ElementRef<HTMLElement>;
  @ViewChild('svgEl') svgRef!: ElementRef<SVGSVGElement>;
  @ViewChild('zoomGroup') zoomGroupRef!: ElementRef<SVGGElement>;

  Math = Math;
  currentScale = signal(1);

  private zoomBehavior!: d3.ZoomBehavior<SVGSVGElement, unknown>;
  private initialized = false;

  ngAfterViewInit(): void {
    this.setupZoom();
    this.initialized = true;
  }

  ngOnDestroy(): void {}

  private setupZoom(): void {
    const svg = d3.select(this.svgRef.nativeElement);
    const zoomGroup = d3.select(this.zoomGroupRef.nativeElement);

    this.zoomBehavior = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        zoomGroup.attr('transform', event.transform.toString());
        this.currentScale.set(event.transform.k);
      });

    svg.call(this.zoomBehavior);
    svg.on('dblclick.zoom', null);
  }

  fitToContainer(animate = true): void {
    if (!this.initialized || !this.contentBounds) return;

    const bounds = this.contentBounds;
    const graphWidth = bounds.maxX - bounds.minX;
    const graphHeight = bounds.maxY - bounds.minY;
    if (graphWidth === 0 || graphHeight === 0) return;

    const container = this.containerRef.nativeElement;
    const cw = container.clientWidth;
    const ch = container.clientHeight;

    const scaleX = (cw - this.padding * 2) / graphWidth;
    const scaleY = (ch - this.padding * 2) / graphHeight;
    const scale = Math.min(scaleX, scaleY, this.maxFitScale);

    const centerX = (bounds.minX + bounds.maxX) / 2;
    const centerY = (bounds.minY + bounds.maxY) / 2;

    const svg = d3.select(this.svgRef.nativeElement);
    const transform = d3.zoomIdentity
      .translate(cw / 2, ch / 2)
      .scale(scale)
      .translate(-centerX, -centerY);

    if (animate) {
      svg.transition().duration(ANIM_DURATION).call(this.zoomBehavior.transform, transform);
    } else {
      svg.call(this.zoomBehavior.transform, transform);
    }
  }

  zoomIn(): void {
    if (!this.initialized) return;
    const svg = d3.select(this.svgRef.nativeElement);
    svg.transition().duration(200).call(this.zoomBehavior.scaleBy, 1.3);
  }

  zoomOut(): void {
    if (!this.initialized) return;
    const svg = d3.select(this.svgRef.nativeElement);
    svg.transition().duration(200).call(this.zoomBehavior.scaleBy, 0.7);
  }
}
