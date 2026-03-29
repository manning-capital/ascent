import { Injectable, inject, signal } from '@angular/core';
import { Subject, EMPTY, Observable } from 'rxjs';
import { switchMap, tap, catchError } from 'rxjs/operators';
import { ApiService } from './api.service';
import {
  EntityUsage,
  MetadataTypeItem, MetadataTypeCreate, MetadataTypeUpdate,
  AttributeItem, AttributeCreate, AttributeUpdate,
} from '../models/field.model';

@Injectable({ providedIn: 'root' })
export class FieldService {
  private api = inject(ApiService);

  metadataTypes = signal<MetadataTypeItem[]>([]);
  attributes = signal<AttributeItem[]>([]);
  loading = signal(false);

  private loadMetadataTypes$ = new Subject<void>();
  private loadAttributes$ = new Subject<void>();

  constructor() {
    this.loadMetadataTypes$.pipe(
      tap(() => this.loading.set(true)),
      switchMap(() =>
        this.api.get<MetadataTypeItem[]>('/types/metadata-types').pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(types => {
      this.metadataTypes.set(types);
      this.loading.set(false);
    });

    this.loadAttributes$.pipe(
      tap(() => this.loading.set(true)),
      switchMap(() =>
        this.api.get<AttributeItem[]>('/attributes').pipe(
          catchError(() => { this.loading.set(false); return EMPTY; })
        )
      ),
    ).subscribe(attrs => {
      this.attributes.set(attrs);
      this.loading.set(false);
    });
  }

  // Metadata Types
  loadMetadataTypes(): void {
    this.loadMetadataTypes$.next();
  }

  getMetadataType(id: string): Observable<MetadataTypeItem> {
    return this.api.get<MetadataTypeItem>(`/types/metadata-types/${id}`);
  }

  createMetadataType(data: MetadataTypeCreate): Observable<MetadataTypeItem> {
    return this.api.post<MetadataTypeItem>('/types/metadata-types', data);
  }

  updateMetadataType(id: string, data: MetadataTypeUpdate): Observable<MetadataTypeItem> {
    return this.api.put<MetadataTypeItem>(`/types/metadata-types/${id}`, data);
  }

  getMetadataTypeUsage(id: string): Observable<EntityUsage> {
    return this.api.get<EntityUsage>(`/types/metadata-types/${id}/usage`);
  }

  deleteMetadataType(id: string): Observable<any> {
    return this.api.delete(`/types/metadata-types/${id}`);
  }

  // Attributes
  loadAttributes(): void {
    this.loadAttributes$.next();
  }

  getAttribute(id: string): Observable<AttributeItem> {
    return this.api.get<AttributeItem>(`/attributes/${id}`);
  }

  createAttribute(data: AttributeCreate): Observable<AttributeItem> {
    return this.api.post<AttributeItem>('/attributes', data);
  }

  updateAttribute(id: string, data: AttributeUpdate): Observable<AttributeItem> {
    return this.api.put<AttributeItem>(`/attributes/${id}`, data);
  }

  getAttributeUsage(id: string): Observable<EntityUsage> {
    return this.api.get<EntityUsage>(`/attributes/${id}/usage`);
  }

  deleteAttribute(id: string): Observable<any> {
    return this.api.delete(`/attributes/${id}`);
  }

  // Asset Type usage + delete
  getAssetTypeUsage(id: string): Observable<EntityUsage> {
    return this.api.get<EntityUsage>(`/types/asset-types/${id}/usage`);
  }

  deleteAssetType(id: string): Observable<any> {
    return this.api.delete(`/types/asset-types/${id}`);
  }

  // Provider Type usage + delete
  getProviderTypeUsage(id: string): Observable<EntityUsage> {
    return this.api.get<EntityUsage>(`/types/provider-types/${id}/usage`);
  }

  deleteProviderType(id: string): Observable<any> {
    return this.api.delete(`/types/provider-types/${id}`);
  }

  // Asset usage
  getAssetUsage(id: string): Observable<EntityUsage> {
    return this.api.get<EntityUsage>(`/assets/${id}/usage`);
  }

  // Provider usage
  getProviderUsage(id: string): Observable<EntityUsage> {
    return this.api.get<EntityUsage>(`/providers/${id}/usage`);
  }
}
