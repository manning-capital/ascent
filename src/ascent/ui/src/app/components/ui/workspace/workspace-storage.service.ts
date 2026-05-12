import { Injectable } from '@angular/core';

const PREFIX = 'ascent-workspace-';

/**
 * Reads/writes splitter panel sizes (numbers in % of container) keyed by
 * a stable storageKey such as 'strategy-detail-top'. Callers handle the
 * fallback to defaults when no stored value exists.
 */
@Injectable({ providedIn: 'root' })
export class WorkspaceStorageService {
  read(key: string): number[] | null {
    try {
      const raw = localStorage.getItem(PREFIX + key);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.every((n) => typeof n === 'number')) {
        return parsed;
      }
      return null;
    } catch {
      return null;
    }
  }

  save(key: string, sizes: number[]): void {
    try {
      localStorage.setItem(PREFIX + key, JSON.stringify(sizes));
    } catch {
      /* storage unavailable — ignore */
    }
  }

  clear(key: string): void {
    try {
      localStorage.removeItem(PREFIX + key);
    } catch {
      /* ignore */
    }
  }
}
