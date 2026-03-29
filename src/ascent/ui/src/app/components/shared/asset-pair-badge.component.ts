import { Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';

export interface AssetPair {
  providerName: string;
  providerId: string;
  fromAssetSymbol: string;
  fromAssetId: string;
  toAssetSymbol: string;
  toAssetId: string;
}

@Component({
  selector: 'app-asset-pair-badge',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="flex flex-wrap gap-1.5 items-center">
      @for (pair of visiblePairs; track $index) {
        <span class="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-canvas/50 border border-surface">
          <a [routerLink]="['/settings/providers', pair.providerId]" class="text-muted-color hover:underline">{{ pair.providerName }}</a>
          <span class="text-surface-400">:</span>
          <a [routerLink]="['/settings/assets', pair.fromAssetId]" class="font-medium text-primary hover:underline">{{ pair.fromAssetSymbol }}</a>
          <span class="text-surface-400">&rarr;</span>
          <a [routerLink]="['/settings/assets', pair.toAssetId]" class="font-medium text-primary hover:underline">{{ pair.toAssetSymbol }}</a>
        </span>
      }
      @if (overflowCount > 0) {
        <span class="text-xs text-surface-400">+{{ overflowCount }} more</span>
      }
    </div>
  `,
})
export class AssetPairBadgeComponent {
  @Input() pairs: AssetPair[] = [];
  /** Max pairs to show before truncating. 0 = show all. */
  @Input() maxVisible = 0;

  get visiblePairs(): AssetPair[] {
    if (this.maxVisible > 0 && this.pairs.length > this.maxVisible) {
      return this.pairs.slice(0, this.maxVisible);
    }
    return this.pairs;
  }

  get overflowCount(): number {
    if (this.maxVisible > 0 && this.pairs.length > this.maxVisible) {
      return this.pairs.length - this.maxVisible;
    }
    return 0;
  }
}
