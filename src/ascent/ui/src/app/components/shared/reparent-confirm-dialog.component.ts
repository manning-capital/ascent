import { Component, EventEmitter, Input, Output } from '@angular/core';
import { Dialog } from 'primeng/dialog';
import { Button } from 'primeng/button';
import { Message } from 'primeng/message';
import { Skeleton } from 'primeng/skeleton';
import { Tag } from 'primeng/tag';
import { ReparentPreview, MetadataConflict } from '../../models/asset.model';

export interface ReparentConfirmEvent {
  removeMetadataIds: string[];
  removeProviderAssetMetadataIds: string[];
}

@Component({
  selector: 'app-reparent-confirm-dialog',
  standalone: true,
  imports: [Dialog, Button, Message, Skeleton, Tag],
  template: `
    <p-dialog
      [header]="preview ? 'Reparent ' + preview.child_name + ' under ' + preview.new_parent_name : 'Reparent Type'"
      [(visible)]="visible"
      (visibleChange)="visibleChange.emit($event)"
      [modal]="true"
      [style]="{width: '40rem'}"
      [closable]="true"
      [draggable]="false">

      <div class="flex flex-col gap-4">
        @if (!preview) {
          <div class="flex flex-col gap-2">
            <p-skeleton width="100%" height="1.5rem"/>
            <p-skeleton width="80%" height="1.5rem"/>
            <p-skeleton width="60%" height="1.5rem"/>
          </div>
        } @else {
          @if (hasConflicts) {
            <p-message severity="warn">
              The following metadata fields exist on both <strong>{{ preview.child_name }}</strong> and
              <strong>{{ preview.new_parent_name }}</strong>'s hierarchy. Confirming will remove these
              fields from the child so they inherit from the parent instead.
            </p-message>

            <!-- Asset type metadata conflicts -->
            @if (preview.conflicts.length > 0) {
              <div>
                <p class="text-sm font-semibold mb-2">Metadata Field Conflicts</p>
                <div class="flex flex-col gap-1 text-sm">
                  @for (c of preview.conflicts; track c.metadata_id) {
                    <div class="flex items-center justify-between px-3 py-1.5 rounded bg-yellow-500/5 border border-yellow-500/10">
                      <div class="flex items-center gap-2">
                        <span class="font-medium">{{ c.metadata_display_name || c.metadata_name }}</span>
                        <span class="font-mono text-xs text-surface-400">{{ c.metadata_name }}</span>
                        <p-tag [value]="c.value_type" severity="secondary" [rounded]="true"/>
                      </div>
                      <span class="text-xs text-surface-400">inherited from <span class="font-medium text-surface-500">{{ c.parent_source_type_name }}</span></span>
                    </div>
                  }
                </div>
              </div>
            }

            <!-- Provider-asset metadata conflicts -->
            @if (preview.provider_asset_conflicts && preview.provider_asset_conflicts.length > 0) {
              <div>
                <p class="text-sm font-semibold mb-2">Provider-Asset Field Conflicts</p>
                <div class="flex flex-col gap-1 text-sm">
                  @for (c of preview.provider_asset_conflicts; track c.metadata_id) {
                    <div class="flex items-center justify-between px-3 py-1.5 rounded bg-yellow-500/5 border border-yellow-500/10">
                      <div class="flex items-center gap-2">
                        <span class="font-medium">{{ c.metadata_display_name || c.metadata_name }}</span>
                        <span class="font-mono text-xs text-surface-400">{{ c.metadata_name }}</span>
                        <p-tag [value]="c.value_type" severity="secondary" [rounded]="true"/>
                      </div>
                      <span class="text-xs text-surface-400">inherited from <span class="font-medium text-surface-500">{{ c.parent_source_type_name }}</span></span>
                    </div>
                  }
                </div>
              </div>
            }

            <div class="flex justify-between px-3 py-1.5 rounded bg-emphasis font-semibold border border-surface text-sm">
              <span>Fields to remove from {{ preview.child_name }}</span>
              <span class="font-mono">{{ totalConflicts }}</span>
            </div>
          } @else {
            <p-message severity="info">
              No metadata conflicts detected. <strong>{{ preview.child_name }}</strong> will be moved
              under <strong>{{ preview.new_parent_name }}</strong>.
            </p-message>
          }

          <div class="flex justify-end gap-2">
            <p-button (onClick)="close()" severity="secondary" [outlined]="true" size="small" label="Cancel"/>
            <p-button (onClick)="onConfirm()" severity="info" size="small" [label]="hasConflicts ? 'Confirm Reparent (' + totalConflicts + ' removed)' : 'Confirm Reparent'" [loading]="reparenting"/>
          </div>
        }
      </div>
    </p-dialog>
  `,
})
export class ReparentConfirmDialogComponent {
  @Input() visible = false;
  @Input() preview: ReparentPreview | null = null;
  @Input() reparenting = false;

  @Output() visibleChange = new EventEmitter<boolean>();
  @Output() confirm = new EventEmitter<ReparentConfirmEvent>();

  get hasConflicts(): boolean {
    if (!this.preview) return false;
    return (
      this.preview.conflicts.length > 0 ||
      (this.preview.provider_asset_conflicts?.length ?? 0) > 0
    );
  }

  get totalConflicts(): number {
    if (!this.preview) return 0;
    return (
      this.preview.conflicts.length +
      (this.preview.provider_asset_conflicts?.length ?? 0)
    );
  }

  close(): void {
    this.visible = false;
    this.visibleChange.emit(false);
  }

  onConfirm(): void {
    if (!this.preview) return;
    this.confirm.emit({
      removeMetadataIds: this.preview.conflicts.map(c => c.metadata_id),
      removeProviderAssetMetadataIds: (this.preview.provider_asset_conflicts ?? []).map(c => c.metadata_id),
    });
  }
}
