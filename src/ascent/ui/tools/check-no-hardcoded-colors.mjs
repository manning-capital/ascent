#!/usr/bin/env node
/**
 * Forbids hardcoded color values across the Angular UI.
 *
 *   - Hex literals (#abc, #abcdef, #abcdefab) in *.ts / *.html / *.css.
 *   - Tailwind palette utilities (text-red-500, bg-green-500, etc.) in *.html / *.ts.
 *
 * The single legitimate location for hex literals is the PrimeNG preset in
 * app.config.ts, where the design tokens are defined. Everything else must
 * reference --p-* tokens, --canvas/--fg/--positive aliases, or Tailwind
 * semantic utilities (text-fg, bg-canvas, text-positive, etc.).
 *
 * Run via:  node tools/check-no-hardcoded-colors.mjs
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = join(__dirname, '..');
const srcRoot = join(projectRoot, 'src');

const HEX_RE = /#[0-9a-fA-F]{3,8}\b/g;
const TAILWIND_PALETTE_RE =
  /\b(?:text|bg|border|ring|fill|stroke|from|via|to|outline|divide|placeholder|caret|accent|shadow|decoration)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(?:50|100|200|300|400|500|600|700|800|900|950)\b/g;

const HEX_ALLOWLIST = new Set([
  'src/app/app.config.ts',
  'tools/check-no-hardcoded-colors.mjs',
]);

const TAILWIND_ALLOWLIST = new Set([
  'tools/check-no-hardcoded-colors.mjs',
]);

// ag-grid's theme API requires raw color values; the metadata-history table
// is the only remaining ag-grid consumer (kept for inline cell editing —
// not yet supported in AppDataTable). The theme file lives next to it.
const PATH_PREFIX_ALLOWLIST = [
  'src/app/components/shared/metadata-history-ag-grid-theme.ts',
];

const SCAN_DIRS = ['src', 'tools'];
const SKIP_DIRS = new Set(['node_modules', 'dist', '.angular', '.git']);
const HEX_EXTS = new Set(['.ts', '.html', '.css', '.scss']);
const TAILWIND_EXTS = new Set(['.ts', '.html']);

const findings = [];

for (const dir of SCAN_DIRS) {
  walk(join(projectRoot, dir));
}

if (findings.length === 0) {
  console.log('check-no-hardcoded-colors: 0 violations found.');
  process.exit(0);
}

const grouped = new Map();
for (const f of findings) {
  if (!grouped.has(f.file)) grouped.set(f.file, []);
  grouped.get(f.file).push(f);
}

console.error(`check-no-hardcoded-colors: ${findings.length} violation(s) in ${grouped.size} file(s).\n`);
for (const [file, items] of grouped) {
  console.error(file);
  for (const item of items) {
    console.error(`  ${item.line}: ${item.kind} → ${item.match}`);
  }
  console.error('');
}
process.exit(1);

function walk(dirPath) {
  let entries;
  try { entries = readdirSync(dirPath); } catch { return; }
  for (const entry of entries) {
    if (SKIP_DIRS.has(entry)) continue;
    const full = join(dirPath, entry);
    let st;
    try { st = statSync(full); } catch { continue; }
    if (st.isDirectory()) walk(full);
    else if (st.isFile()) scanFile(full);
  }
}

function scanFile(file) {
  const ext = extname(file);
  if (!HEX_EXTS.has(ext) && !TAILWIND_EXTS.has(ext)) return;

  const rel = relative(projectRoot, file).split(sep).join('/');
  if (PATH_PREFIX_ALLOWLIST.some((p) => rel.startsWith(p))) return;
  const checkHex = HEX_EXTS.has(ext) && !HEX_ALLOWLIST.has(rel);
  const checkTailwind = TAILWIND_EXTS.has(ext) && !TAILWIND_ALLOWLIST.has(rel);
  if (!checkHex && !checkTailwind) return;

  let contents;
  try { contents = readFileSync(file, 'utf8'); } catch { return; }
  const lines = contents.split('\n');

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (checkHex) {
      for (const m of line.matchAll(HEX_RE)) {
        findings.push({ file: rel, line: i + 1, kind: 'hex-literal', match: m[0] });
      }
    }
    if (checkTailwind) {
      for (const m of line.matchAll(TAILWIND_PALETTE_RE)) {
        findings.push({ file: rel, line: i + 1, kind: 'tailwind-palette', match: m[0] });
      }
    }
  }
}

function extname(file) {
  const dot = file.lastIndexOf('.');
  return dot === -1 ? '' : file.slice(dot);
}
