import { Injectable, inject, signal } from '@angular/core';
import { Subject, EMPTY, Observable } from 'rxjs';
import { switchMap, tap, catchError } from 'rxjs/operators';
import { ApiService } from './api.service';
import {
  AssetListItem, AssetDetail, AssetCreate, AssetUpdate,
  ProviderAssetLink, ProviderAssetLinkCreate,
  AssetGroup, AssetGroupCreate, AssetGroupMemberCreate,
  TypeItem, MetadataEntry, MetadataEntryCreate, MetadataHistoryEntry, MetadataHistoryUpdate, MetadataType,
  AssetTypeMetadataField, AssetTypeMetadataCreate,
} from '../models/asset.model';

@Injectable({ providedIn: 'root' })
export class AssetService {
  private api = inject(ApiService);

  assets = signal<AssetListItem[]>([]);
  assetTypes = signal<TypeItem[]>([]);
  providerAssetLinks = signal<ProviderAssetLink[]>([]);
  assetGroups = signal<AssetGroup[]>([]);
  metadataTypes = signal<MetadataType[]>([]);
  selectedAsset = signal<AssetDetail | null>(null);
  loading = signal(true);
  saving = signal(false);

  private loadAssets$ = new Subject<void>();
  private loadTypes$ = new Subject<void>();
  private loadLinks$ = new Subject<Record<string, string> | undefined>();
  private loadGroups$ = new Subject<Record<string, string> | undefined>();
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

    this.loadGroups$.pipe(
      switchMap(params =>
        this.api.get<AssetGroup[]>('/asset-groups', params).pipe(
          catchError(() => EMPTY)
        )
      ),
    ).subscribe(groups => {
      this.assetGroups.set(groups);
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

  loadAssetGroups(params?: Record<string, string>): void {
    this.loadGroups$.next(params);
  }

  loadAssetDetail(assetId: string, silent = false): void {
    this.loadDetail$.next({ assetId, silent });
  }

  loadMetadataTypes(): void {
    this.loadMetadataTypes$.next();
  }

  createAssetType(name: string, description?: string): Observable<TypeItem> {
    return this.api.post<TypeItem>('/types/asset-types', { name, description });
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

  getAssetGroupDetail(groupId: string): Observable<AssetGroup> {
    return this.api.get<AssetGroup>(`/asset-groups/${groupId}`);
  }

  createAssetGroup(data: AssetGroupCreate) {
    return this.api.post<AssetGroup>('/asset-groups', data);
  }

  deleteAssetGroup(id: string) {
    return this.api.delete(`/asset-groups/${id}`);
  }

  addGroupMember(groupId: string, data: AssetGroupMemberCreate) {
    return this.api.post(`/asset-groups/${groupId}/members`, data);
  }

  removeGroupMember(groupId: string, providerId: string, fromAssetId: string, toAssetId: string) {
    return this.api.delete(`/asset-groups/${groupId}/members/${providerId}/${fromAssetId}/${toAssetId}`);
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

  createMetadataType(name: string, description?: string, valueType = 'string'): Observable<MetadataType> {
    return this.api.post<MetadataType>('/types/metadata-types', { name, description, value_type: valueType });
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
}
