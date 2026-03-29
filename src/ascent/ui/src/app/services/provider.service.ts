import { Injectable, inject, signal } from '@angular/core';
import { Subject, EMPTY, Observable } from 'rxjs';
import { switchMap, tap, catchError } from 'rxjs/operators';
import { ApiService } from './api.service';
import { ProviderListItem, ProviderDetail, ProviderCreate, ProviderUpdate } from '../models/provider.model';
import {
  TypeItem, TypeHierarchyNode, MetadataEntry, MetadataEntryCreate,
  MetadataHistoryEntry, MetadataHistoryUpdate,
  ProviderTypeMetadataField, ProviderTypeMetadataCreate,
  BatchMetadataCreate, MetadataHistoryGrid, BulkHistoryUpdate,
} from '../models/asset.model';

@Injectable({ providedIn: 'root' })
export class ProviderService {
  private api = inject(ApiService);

  providers = signal<ProviderListItem[]>([]);
  providerTypes = signal<TypeItem[]>([]);
  selectedProvider = signal<ProviderDetail | null>(null);
  loading = signal(true);
  saving = signal(false);

  private loadProviders$ = new Subject<void>();
  private loadTypes$ = new Subject<void>();
  private loadDetail$ = new Subject<{ providerId: string; silent: boolean }>();

  constructor() {
    this.loadProviders$.pipe(
      tap(() => this.loading.set(true)),
      switchMap(() =>
        this.api.get<ProviderListItem[]>('/providers').pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(providers => {
      this.providers.set(providers);
      this.loading.set(false);
    });

    this.loadTypes$.pipe(
      switchMap(() =>
        this.api.get<TypeItem[]>('/types/provider-types').pipe(
          catchError(() => EMPTY)
        )
      ),
    ).subscribe(types => {
      this.providerTypes.set(types);
    });

    this.loadDetail$.pipe(
      tap(({ silent }) => { if (!silent) this.loading.set(true); }),
      switchMap(({ providerId }) =>
        this.api.get<ProviderDetail>(`/providers/${providerId}`).pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(provider => {
      this.selectedProvider.set(provider);
      this.loading.set(false);
    });
  }

  loadProviders(): void {
    this.loadProviders$.next();
  }

  loadProviderTypes(): void {
    this.loadTypes$.next();
  }

  loadProviderDetail(providerId: string, silent = false): void {
    this.loadDetail$.next({ providerId, silent });
  }

  createProviderType(name: string, description?: string, parentTypeId?: string): Observable<TypeItem> {
    return this.api.post<TypeItem>('/types/provider-types', { name, description, parent_type_id: parentTypeId ?? null });
  }

  loadProviderTypeTree(): Observable<TypeHierarchyNode[]> {
    return this.api.get<TypeHierarchyNode[]>('/types/provider-types/tree');
  }

  createProvider(data: ProviderCreate) {
    this.saving.set(true);
    return this.api.post<ProviderListItem>('/providers', data).pipe(
      tap(() => this.saving.set(false)),
      catchError(err => { this.saving.set(false); throw err; })
    );
  }

  updateProvider(id: string, data: ProviderUpdate) {
    this.saving.set(true);
    return this.api.put<ProviderListItem>(`/providers/${id}`, data).pipe(
      tap(() => this.saving.set(false)),
      catchError(err => { this.saving.set(false); throw err; })
    );
  }

  deleteProvider(id: string) {
    return this.api.delete(`/providers/${id}`);
  }

  // Metadata CRUD
  getProviderMetadata(providerId: string): Observable<MetadataEntry[]> {
    return this.api.get<MetadataEntry[]>(`/providers/${providerId}/metadata`);
  }

  addProviderMetadata(providerId: string, data: MetadataEntryCreate): Observable<MetadataEntry> {
    return this.api.post<MetadataEntry>(`/providers/${providerId}/metadata`, data);
  }

  deleteProviderMetadata(providerId: string, metadataId: string): Observable<any> {
    return this.api.delete(`/providers/${providerId}/metadata/${metadataId}`);
  }

  getProviderMetadataHistory(providerId: string, metadataId: string): Observable<MetadataHistoryEntry[]> {
    return this.api.get<MetadataHistoryEntry[]>(`/providers/${providerId}/metadata/${metadataId}/history`);
  }

  updateProviderMetadataEntry(providerId: string, metadataId: string, timestamp: string, data: MetadataHistoryUpdate): Observable<MetadataHistoryEntry> {
    return this.api.put<MetadataHistoryEntry>(`/providers/${providerId}/metadata/${metadataId}/history`, data, { timestamp });
  }

  deleteProviderMetadataEntry(providerId: string, metadataId: string, timestamp: string): Observable<any> {
    return this.api.deleteWithParams(`/providers/${providerId}/metadata/${metadataId}/history`, { timestamp });
  }

  // Provider Type Metadata Fields
  getProviderTypeMetadata(providerTypeId: string): Observable<ProviderTypeMetadataField[]> {
    return this.api.get<ProviderTypeMetadataField[]>(`/types/provider-types/${providerTypeId}/metadata`);
  }

  addProviderTypeMetadata(providerTypeId: string, data: ProviderTypeMetadataCreate): Observable<ProviderTypeMetadataField> {
    return this.api.post<ProviderTypeMetadataField>(`/types/provider-types/${providerTypeId}/metadata`, data);
  }

  removeProviderTypeMetadata(providerTypeId: string, metadataId: string): Observable<any> {
    return this.api.delete(`/types/provider-types/${providerTypeId}/metadata/${metadataId}`);
  }

  // Batch metadata
  batchSaveProviderMetadata(providerId: string, data: BatchMetadataCreate): Observable<MetadataEntry[]> {
    return this.api.post<MetadataEntry[]>(`/providers/${providerId}/metadata/batch`, data);
  }

  // History grid
  getProviderMetadataHistoryGrid(providerId: string): Observable<MetadataHistoryGrid> {
    return this.api.get<MetadataHistoryGrid>(`/providers/${providerId}/metadata/history`);
  }

  bulkUpdateProviderMetadataHistory(providerId: string, data: BulkHistoryUpdate): Observable<any> {
    return this.api.put(`/providers/${providerId}/metadata/history/bulk`, data);
  }
}
