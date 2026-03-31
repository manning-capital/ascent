import { Injectable, inject, signal } from '@angular/core';
import { Subject, EMPTY, Observable } from 'rxjs';
import { switchMap, tap, catchError } from 'rxjs/operators';
import { ApiService } from './api.service';
import {
  AssetListItem, AssetDetail, AssetCreate, AssetUpdate,
  ProviderAssetLink, ProviderAssetLinkCreate,
  Instrument, InstrumentCreate,
  TypeItem, TypeHierarchyNode, MetadataEntry, MetadataEntryCreate,
  MetadataHistoryEntry, MetadataHistoryUpdate, MetadataType,
  AssetTypeMetadataField, AssetTypeMetadataCreate,
  AssetTypeProviderAssetMetadataField, AssetTypeProviderAssetMetadataCreate,
  BatchMetadataCreate, MetadataHistoryGrid, BulkHistoryUpdate,
  ReparentPreview,
  InstrumentTypeItem, InstrumentTypeCreate,
  InstrumentTypeMetadataField, InstrumentTypeMetadataCreate,
} from '../models/asset.model';

@Injectable({ providedIn: 'root' })
export class AssetService {
  private api = inject(ApiService);

  assets = signal<AssetListItem[]>([]);
  assetTypes = signal<TypeItem[]>([]);
  providerAssetLinks = signal<ProviderAssetLink[]>([]);
  instruments = signal<Instrument[]>([]);
  instrumentTypes = signal<InstrumentTypeItem[]>([]);
  metadataTypes = signal<MetadataType[]>([]);
  selectedAsset = signal<AssetDetail | null>(null);
  loading = signal(true);
  saving = signal(false);

  private loadAssets$ = new Subject<void>();
  private loadTypes$ = new Subject<void>();
  private loadLinks$ = new Subject<Record<string, string> | undefined>();
  private loadInstruments$ = new Subject<Record<string, string> | undefined>();
  private loadInstrumentTypes$ = new Subject<void>();
  private loadDetail$ = new Subject<{ assetId: string; silent: boolean }>();
  private loadMetadataTypes$ = new Subject<void>();

  constructor() {
    this.loadAssets$.pipe(
      tap(() => this.loading.set(true)),
      switchMap(() =>
        this.api.get<AssetListItem[]>('/assets').pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(assets => {
      this.assets.set(assets);
      this.loading.set(false);
    });

    this.loadTypes$.pipe(
      switchMap(() =>
        this.api.get<TypeItem[]>('/types/asset-types').pipe(
          catchError(() => EMPTY)
        )
      ),
    ).subscribe(types => {
      this.assetTypes.set(types);
    });

    this.loadLinks$.pipe(
      switchMap(params =>
        this.api.get<ProviderAssetLink[]>('/provider-assets', params).pipe(
          catchError(() => EMPTY)
        )
      ),
    ).subscribe(links => {
      this.providerAssetLinks.set(links);
    });

    this.loadInstruments$.pipe(
      switchMap(params =>
        this.api.get<Instrument[]>('/instruments', params).pipe(
          catchError(() => EMPTY)
        )
      ),
    ).subscribe(instruments => {
      this.instruments.set(instruments);
    });

    this.loadInstrumentTypes$.pipe(
      switchMap(() =>
        this.api.get<InstrumentTypeItem[]>('/types/instrument-types').pipe(
          catchError(() => EMPTY)
        )
      ),
    ).subscribe(types => {
      this.instrumentTypes.set(types);
    });

    this.loadDetail$.pipe(
      tap(({ silent }) => { if (!silent) this.loading.set(true); }),
      switchMap(({ assetId }) =>
        this.api.get<AssetDetail>(`/assets/${assetId}`).pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(asset => {
      this.selectedAsset.set(asset);
      this.loading.set(false);
    });

    this.loadMetadataTypes$.pipe(
      switchMap(() =>
        this.api.get<MetadataType[]>('/types/metadata-types').pipe(
          catchError(() => EMPTY)
        )
      ),
    ).subscribe(types => {
      this.metadataTypes.set(types);
    });
  }

  loadAssets(): void {
    this.loadAssets$.next();
  }

  loadAssetTypes(): void {
    this.loadTypes$.next();
  }

  loadProviderAssetLinks(params?: Record<string, string>): void {
    this.loadLinks$.next(params);
  }

  loadInstruments(params?: Record<string, string>): void {
    this.loadInstruments$.next(params);
  }

  loadInstrumentTypes(): void {
    this.loadInstrumentTypes$.next();
  }

  createInstrumentType(name: string, displayName: string, description?: string, parentTypeId?: string): Observable<InstrumentTypeItem> {
    return this.api.post<InstrumentTypeItem>('/types/instrument-types', {
      name, display_name: displayName, description,
      parent_type_id: parentTypeId ?? null,
    });
  }

  updateInstrumentType(typeId: string, data: { parent_type_id: string | null; remove_metadata_ids?: string[] }): Observable<InstrumentTypeItem> {
    return this.api.put<InstrumentTypeItem>(`/types/instrument-types/${typeId}`, data);
  }

  patchInstrumentType(typeId: string, data: { name?: string; display_name?: string; description?: string }): Observable<InstrumentTypeItem> {
    return this.api.patch<InstrumentTypeItem>(`/types/instrument-types/${typeId}`, data);
  }

  getInstrumentTypeReparentPreview(childId: string, newParentId: string): Observable<ReparentPreview> {
    return this.api.get<ReparentPreview>(`/types/instrument-types/${childId}/reparent-preview`, { new_parent_id: newParentId });
  }

  loadInstrumentTypeTree(): Observable<TypeHierarchyNode[]> {
    return this.api.get<TypeHierarchyNode[]>('/types/instrument-types/tree');
  }

  getInstrumentTypeMetadata(instrumentTypeId: string): Observable<InstrumentTypeMetadataField[]> {
    return this.api.get<InstrumentTypeMetadataField[]>(`/types/instrument-types/${instrumentTypeId}/metadata`);
  }

  addInstrumentTypeMetadata(instrumentTypeId: string, data: InstrumentTypeMetadataCreate): Observable<InstrumentTypeMetadataField> {
    return this.api.post<InstrumentTypeMetadataField>(`/types/instrument-types/${instrumentTypeId}/metadata`, data);
  }

  removeInstrumentTypeMetadata(instrumentTypeId: string, metadataId: string): Observable<any> {
    return this.api.delete(`/types/instrument-types/${instrumentTypeId}/metadata/${metadataId}`);
  }

  // Instrument Metadata
  getInstrumentMetadata(instrumentId: string): Observable<MetadataEntry[]> {
    return this.api.get<MetadataEntry[]>(`/instruments/${instrumentId}/metadata`);
  }

  batchSaveInstrumentMetadata(instrumentId: string, data: BatchMetadataCreate): Observable<MetadataEntry[]> {
    return this.api.post<MetadataEntry[]>(`/instruments/${instrumentId}/metadata/batch`, data);
  }

  getInstrumentMetadataHistoryGrid(instrumentId: string): Observable<MetadataHistoryGrid> {
    return this.api.get<MetadataHistoryGrid>(`/instruments/${instrumentId}/metadata/history`);
  }

  bulkUpdateInstrumentMetadataHistory(instrumentId: string, data: BulkHistoryUpdate): Observable<any> {
    return this.api.put(`/instruments/${instrumentId}/metadata/history/bulk`, data);
  }

  loadAssetDetail(assetId: string, silent = false): void {
    this.loadDetail$.next({ assetId, silent });
  }

  loadMetadataTypes(): void {
    this.loadMetadataTypes$.next();
  }

  createAssetType(name: string, displayName: string, description?: string, parentTypeId?: string): Observable<TypeItem> {
    return this.api.post<TypeItem>('/types/asset-types', { name, display_name: displayName, description, parent_type_id: parentTypeId ?? null });
  }

  updateAssetType(typeId: string, data: { parent_type_id: string | null; remove_metadata_ids?: string[]; remove_provider_asset_metadata_ids?: string[] }): Observable<TypeItem> {
    return this.api.put<TypeItem>(`/types/asset-types/${typeId}`, data);
  }

  patchAssetType(typeId: string, data: { name?: string; display_name?: string; description?: string }): Observable<TypeItem> {
    return this.api.patch<TypeItem>(`/types/asset-types/${typeId}`, data);
  }

  getReparentPreview(childId: string, newParentId: string): Observable<ReparentPreview> {
    return this.api.get<ReparentPreview>(`/types/asset-types/${childId}/reparent-preview`, { new_parent_id: newParentId });
  }

  loadAssetTypeTree(): Observable<TypeHierarchyNode[]> {
    return this.api.get<TypeHierarchyNode[]>('/types/asset-types/tree');
  }

  createAsset(data: AssetCreate) {
    this.saving.set(true);
    return this.api.post<AssetListItem>('/assets', data).pipe(
      tap(() => this.saving.set(false)),
      catchError(err => { this.saving.set(false); throw err; })
    );
  }

  updateAsset(id: string, data: AssetUpdate) {
    this.saving.set(true);
    return this.api.put<AssetListItem>(`/assets/${id}`, data).pipe(
      tap(() => this.saving.set(false)),
      catchError(err => { this.saving.set(false); throw err; })
    );
  }

  deleteAsset(id: string) {
    return this.api.delete(`/assets/${id}`);
  }

  createProviderAssetLink(data: ProviderAssetLinkCreate) {
    return this.api.post<ProviderAssetLink>('/provider-assets', data);
  }

  deleteProviderAssetLink(providerId: string, assetId: string) {
    return this.api.delete(`/provider-assets/${providerId}/${assetId}`);
  }

  getInstrumentDetail(instrumentId: string): Observable<Instrument> {
    return this.api.get<Instrument>(`/instruments/${instrumentId}`);
  }

  createInstrument(data: InstrumentCreate) {
    return this.api.post<Instrument>('/instruments', data);
  }

  updateInstrument(id: string, data: { is_active?: boolean }) {
    return this.api.put(`/instruments/${id}`, data);
  }

  deleteInstrument(id: string) {
    return this.api.delete(`/instruments/${id}`);
  }

  // Metadata CRUD
  getAssetMetadata(assetId: string): Observable<MetadataEntry[]> {
    return this.api.get<MetadataEntry[]>(`/assets/${assetId}/metadata`);
  }

  addAssetMetadata(assetId: string, data: MetadataEntryCreate): Observable<MetadataEntry> {
    return this.api.post<MetadataEntry>(`/assets/${assetId}/metadata`, data);
  }

  deleteAssetMetadata(assetId: string, metadataId: string): Observable<any> {
    return this.api.delete(`/assets/${assetId}/metadata/${metadataId}`);
  }

  getAssetMetadataHistory(assetId: string, metadataId: string): Observable<MetadataHistoryEntry[]> {
    return this.api.get<MetadataHistoryEntry[]>(`/assets/${assetId}/metadata/${metadataId}/history`);
  }

  updateAssetMetadataEntry(assetId: string, metadataId: string, timestamp: string, data: MetadataHistoryUpdate): Observable<MetadataHistoryEntry> {
    return this.api.put<MetadataHistoryEntry>(`/assets/${assetId}/metadata/${metadataId}/history`, data, { timestamp });
  }

  deleteAssetMetadataEntry(assetId: string, metadataId: string, timestamp: string): Observable<any> {
    return this.api.deleteWithParams(`/assets/${assetId}/metadata/${metadataId}/history`, { timestamp });
  }

  // Provider-Asset Metadata
  getProviderAssetMetadata(providerId: string, assetId: string): Observable<MetadataEntry[]> {
    return this.api.get<MetadataEntry[]>(`/provider-assets/${providerId}/${assetId}/metadata`);
  }

  addProviderAssetMetadata(providerId: string, assetId: string, data: MetadataEntryCreate): Observable<MetadataEntry> {
    return this.api.post<MetadataEntry>(`/provider-assets/${providerId}/${assetId}/metadata`, data);
  }

  batchSaveProviderAssetMetadata(providerId: string, assetId: string, data: BatchMetadataCreate): Observable<MetadataEntry[]> {
    return this.api.post<MetadataEntry[]>(`/provider-assets/${providerId}/${assetId}/metadata/batch`, data);
  }

  getProviderAssetMetadataHistoryGrid(providerId: string, assetId: string): Observable<MetadataHistoryGrid> {
    return this.api.get<MetadataHistoryGrid>(`/provider-assets/${providerId}/${assetId}/metadata/history`);
  }

  bulkUpdateProviderAssetMetadataHistory(providerId: string, assetId: string, data: BulkHistoryUpdate): Observable<any> {
    return this.api.put(`/provider-assets/${providerId}/${assetId}/metadata/history/bulk`, data);
  }

  createMetadataType(name: string, displayName: string, description?: string, valueType = 'string'): Observable<MetadataType> {
    return this.api.post<MetadataType>('/types/metadata-types', { name, display_name: displayName, description, value_type: valueType });
  }

  // Asset Type Metadata Fields
  getAssetTypeMetadata(assetTypeId: string): Observable<AssetTypeMetadataField[]> {
    return this.api.get<AssetTypeMetadataField[]>(`/types/asset-types/${assetTypeId}/metadata`);
  }

  addAssetTypeMetadata(assetTypeId: string, data: AssetTypeMetadataCreate): Observable<AssetTypeMetadataField> {
    return this.api.post<AssetTypeMetadataField>(`/types/asset-types/${assetTypeId}/metadata`, data);
  }

  removeAssetTypeMetadata(assetTypeId: string, metadataId: string): Observable<any> {
    return this.api.delete(`/types/asset-types/${assetTypeId}/metadata/${metadataId}`);
  }

  // Asset Type Provider-Asset Metadata Fields
  getAssetTypeProviderAssetMetadata(assetTypeId: string): Observable<AssetTypeProviderAssetMetadataField[]> {
    return this.api.get<AssetTypeProviderAssetMetadataField[]>(`/types/asset-types/${assetTypeId}/provider-asset-metadata`);
  }

  addAssetTypeProviderAssetMetadata(assetTypeId: string, data: AssetTypeProviderAssetMetadataCreate): Observable<AssetTypeProviderAssetMetadataField> {
    return this.api.post<AssetTypeProviderAssetMetadataField>(`/types/asset-types/${assetTypeId}/provider-asset-metadata`, data);
  }

  removeAssetTypeProviderAssetMetadata(assetTypeId: string, metadataId: string): Observable<any> {
    return this.api.delete(`/types/asset-types/${assetTypeId}/provider-asset-metadata/${metadataId}`);
  }

  // Batch metadata
  batchSaveAssetMetadata(assetId: string, data: BatchMetadataCreate): Observable<MetadataEntry[]> {
    return this.api.post<MetadataEntry[]>(`/assets/${assetId}/metadata/batch`, data);
  }

  // History grid
  getAssetMetadataHistoryGrid(assetId: string): Observable<MetadataHistoryGrid> {
    return this.api.get<MetadataHistoryGrid>(`/assets/${assetId}/metadata/history`);
  }

  bulkUpdateAssetMetadataHistory(assetId: string, data: BulkHistoryUpdate): Observable<any> {
    return this.api.put(`/assets/${assetId}/metadata/history/bulk`, data);
  }
}
