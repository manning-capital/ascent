import { Injectable, inject, signal } from '@angular/core';
import { Subject, EMPTY, Observable } from 'rxjs';
import { switchMap, tap, catchError } from 'rxjs/operators';
import { ApiService } from './api.service';
import {
  Composite, CompositeCreate, CompositeMember, CompositeMemberCreate,
  CompositeTypeItem, CompositeTypeCreate, CompositeTypeMetadataField,
  CompositeTypeMetadataCreate, CompositeUniverseItem,
} from '../models/composite.model';
import {
  MetadataEntry, BatchMetadataCreate, MetadataHistoryGrid, BulkHistoryUpdate,
  TypeHierarchyNode,
} from '../models/asset.model';
import { EntityUsage } from '../models/field.model';

@Injectable({ providedIn: 'root' })
export class CompositeService {
  private api = inject(ApiService);

  composites = signal<Composite[]>([]);
  compositeTypes = signal<CompositeTypeItem[]>([]);
  compositeTypeTree = signal<TypeHierarchyNode[]>([]);
  loading = signal(false);

  private loadComposites$ = new Subject<void>();
  private loadCompositeTypes$ = new Subject<void>();

  constructor() {
    this.loadComposites$.pipe(
      tap(() => this.loading.set(true)),
      switchMap(() =>
        this.api.get<Composite[]>('/composites').pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(items => {
      this.composites.set(items);
      this.loading.set(false);
    });

    this.loadCompositeTypes$.pipe(
      switchMap(() =>
        this.api.get<CompositeTypeItem[]>('/types/composite-types').pipe(
          catchError(() => EMPTY)
        )
      ),
    ).subscribe(types => this.compositeTypes.set(types));
  }

  // Composites
  loadComposites(): void { this.loadComposites$.next(); }

  getCompositeDetail(id: string): Observable<Composite> {
    return this.api.get<Composite>(`/composites/${id}`);
  }

  createComposite(data: CompositeCreate): Observable<Composite> {
    return this.api.post<Composite>('/composites', data);
  }

  updateComposite(id: string, data: { is_active?: boolean; composite_type_id?: string }): Observable<Composite> {
    return this.api.put<Composite>(`/composites/${id}`, data);
  }

  deleteComposite(id: string): Observable<any> {
    return this.api.delete(`/composites/${id}`);
  }

  // Members
  addCompositeMember(compositeId: string, data: CompositeMemberCreate): Observable<CompositeMember> {
    return this.api.post<CompositeMember>(`/composites/${compositeId}/members`, data);
  }

  removeCompositeMember(compositeId: string, instrumentId: string): Observable<any> {
    return this.api.delete(`/composites/${compositeId}/members/${instrumentId}`);
  }

  // Metadata
  getCompositeMetadata(compositeId: string): Observable<MetadataEntry[]> {
    return this.api.get<MetadataEntry[]>(`/composites/${compositeId}/metadata`);
  }

  batchSaveCompositeMetadata(compositeId: string, data: BatchMetadataCreate): Observable<MetadataEntry[]> {
    return this.api.post<MetadataEntry[]>(`/composites/${compositeId}/metadata/batch`, data);
  }

  getCompositeMetadataHistoryGrid(compositeId: string): Observable<MetadataHistoryGrid> {
    return this.api.get<MetadataHistoryGrid>(`/composites/${compositeId}/metadata/history`);
  }

  bulkUpdateCompositeMetadataHistory(compositeId: string, data: BulkHistoryUpdate): Observable<any> {
    return this.api.put(`/composites/${compositeId}/metadata/history/bulk`, data);
  }

  // Usage
  getCompositeUsage(id: string): Observable<EntityUsage> {
    return this.api.get<EntityUsage>(`/composites/${id}/usage`);
  }

  // Composite Types
  loadCompositeTypes(): void { this.loadCompositeTypes$.next(); }

  loadCompositeTypeTree(): void {
    this.api.get<TypeHierarchyNode[]>('/types/composite-types/tree').subscribe(tree => {
      this.compositeTypeTree.set(tree);
    });
  }

  createCompositeType(data: CompositeTypeCreate): Observable<CompositeTypeItem> {
    return this.api.post<CompositeTypeItem>('/types/composite-types', data);
  }

  patchCompositeType(id: string, patch: Partial<CompositeTypeCreate>): Observable<CompositeTypeItem> {
    return this.api.patch<CompositeTypeItem>(`/types/composite-types/${id}`, patch);
  }

  getCompositeTypeUsage(id: string): Observable<EntityUsage> {
    return this.api.get<EntityUsage>(`/types/composite-types/${id}/usage`);
  }

  deleteCompositeType(id: string): Observable<any> {
    return this.api.delete(`/types/composite-types/${id}`);
  }

  getCompositeTypeMetadata(typeId: string, includeInherited = true): Observable<CompositeTypeMetadataField[]> {
    return this.api.get<CompositeTypeMetadataField[]>(`/types/composite-types/${typeId}/metadata?include_inherited=${includeInherited}`);
  }

  addCompositeTypeMetadata(typeId: string, data: CompositeTypeMetadataCreate): Observable<CompositeTypeMetadataField> {
    return this.api.post<CompositeTypeMetadataField>(`/types/composite-types/${typeId}/metadata`, data);
  }

  removeCompositeTypeMetadata(typeId: string, metadataId: string): Observable<any> {
    return this.api.delete(`/types/composite-types/${typeId}/metadata/${metadataId}`);
  }
}
