import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { PaginatedResponse } from '../models/trade.model';
import {
  EntityUsage,
  MetadataTypeItem, MetadataTypeCreate, MetadataTypeUpdate,
  AttributeItem, AttributeCreate, AttributeUpdate,
} from '../models/field.model';

@Injectable({ providedIn: 'root' })
export class FieldService {
  private api = inject(ApiService);

  // Metadata Types

  loadMetadataTypesPaginated(page: number, pageSize: number, filters?: { search?: string; is_active?: boolean | null }, sort?: { field: string; order: string }): Observable<PaginatedResponse<MetadataTypeItem>> {
    const params: Record<string, any> = { page, page_size: pageSize };
    if (filters?.search) params['search'] = filters.search;
    if (filters?.is_active != null) params['is_active'] = filters.is_active;
    if (sort) { params['sort_field'] = sort.field; params['sort_order'] = sort.order; }
    return this.api.get<PaginatedResponse<MetadataTypeItem>>('/metadata', params);
  }

  getMetadataType(id: string): Observable<MetadataTypeItem> {
    return this.api.get<MetadataTypeItem>(`/metadata/${id}`);
  }

  createMetadataType(data: MetadataTypeCreate): Observable<MetadataTypeItem> {
    return this.api.post<MetadataTypeItem>('/metadata', data);
  }

  updateMetadataType(id: string, data: MetadataTypeUpdate): Observable<MetadataTypeItem> {
    return this.api.put<MetadataTypeItem>(`/metadata/${id}`, data);
  }

  getMetadataTypeUsage(id: string): Observable<EntityUsage> {
    return this.api.get<EntityUsage>(`/metadata/${id}/usage`);
  }

  deleteMetadataType(id: string): Observable<any> {
    return this.api.delete(`/metadata/${id}`);
  }

  // Attributes
  loadAttributesPaginated(page: number, pageSize: number, filters?: { search?: string; is_active?: boolean | null }, sort?: { field: string; order: string }): Observable<PaginatedResponse<AttributeItem>> {
    const params: Record<string, any> = { page, page_size: pageSize };
    if (filters?.search) params['search'] = filters.search;
    if (filters?.is_active != null) params['is_active'] = filters.is_active;
    if (sort) { params['sort_field'] = sort.field; params['sort_order'] = sort.order; }
    return this.api.get<PaginatedResponse<AttributeItem>>('/attributes', params);
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

  // Instrument Type usage + delete
  getInstrumentTypeUsage(id: string): Observable<EntityUsage> {
    return this.api.get<EntityUsage>(`/types/instrument-types/${id}/usage`);
  }

  deleteInstrumentType(id: string): Observable<any> {
    return this.api.delete(`/types/instrument-types/${id}`);
  }

  // Asset usage
  getAssetUsage(id: string): Observable<EntityUsage> {
    return this.api.get<EntityUsage>(`/assets/${id}/usage`);
  }

  // Provider usage
  getProviderUsage(id: string): Observable<EntityUsage> {
    return this.api.get<EntityUsage>(`/providers/${id}/usage`);
  }

  // Instrument usage
  getInstrumentUsage(id: string): Observable<EntityUsage> {
    return this.api.get<EntityUsage>(`/instruments/${id}/usage`);
  }

  // Composite usage
  getCompositeUsage(id: string): Observable<EntityUsage> {
    return this.api.get<EntityUsage>(`/composites/${id}/usage`);
  }

  // Composite Type usage + delete
  getCompositeTypeUsage(id: string): Observable<EntityUsage> {
    return this.api.get<EntityUsage>(`/types/composite-types/${id}/usage`);
  }

  deleteCompositeType(id: string): Observable<any> {
    return this.api.delete(`/types/composite-types/${id}`);
  }
}
