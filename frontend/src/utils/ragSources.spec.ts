import { describe, expect, it } from 'vitest';
import { sourceLocation, citationSources, validateRagTraceSources } from './ragSources';
import type { RetrievedChunk } from '@/types/chat';

const leaf: RetrievedChunk = {
  filename: 'specs.xlsx',
  chunk_id: 'v1::specs.xlsx::p0::l3::0',
  chunk_level: 3,
  document_id: 'd1',
  document_version_id: 'v1',
  section_id: 'sheet:Specs',
  index_version: 'index-v1',
  content_hash: 'a'.repeat(64),
  sheet_name: 'Specs',
  row_start: 2,
  row_end: 2,
  source_anchor: 'sheet:Specs:row:2',
};

describe('trusted RAG source presentation', () => {
  it('accepts response-model nulls as absent provenance when loading history', () => {
    const history = JSON.parse(
      JSON.stringify({
        filename: 'guide.html',
        page_number: 4,
        sheet_name: null,
        row_start: null,
        row_end: null,
        source_anchor: null,
        matched_leaf_sources: null,
        matched_leaf_sources_truncated: null,
      })
    );
    expect(sourceLocation(history)).toBe('第 4 页');
    expect(validateRagTraceSources({ retrieved_chunks: [history] })).toBeTruthy();
    const parent = JSON.parse(
      JSON.stringify({
        ...leaf,
        sheet_name: null,
        row_start: null,
        row_end: null,
        source_anchor: null,
        matched_leaf_sources: null,
        matched_leaf_sources_truncated: null,
      })
    );
    expect(sourceLocation(parent)).toBe('文件级来源');
  });
  it.each([
    { row_start: true },
    { row_start: '2' },
    { row_end: 1 },
    { source_anchor: 'sheet:Specs:row:99' },
    { document_version_id: 'foreign' },
  ])('rejects malformed source data at the public boundary: %j', (update) => {
    expect(() =>
      validateRagTraceSources(
        JSON.parse(JSON.stringify({ retrieved_chunks: [{ ...leaf, ...update }] }))
      )
    ).toThrow();
  });
  it('renders a real physical row, not a page', () => {
    expect(sourceLocation(leaf)).toBe('Specs · 第 2 行');
  });
  it('never enlarges discontinuous parent matches into a range', () => {
    const { sheet_name, row_start, row_end, source_anchor, ...identity } = leaf;
    const first = {
      chunk_id: leaf.chunk_id,
      sheet_name: sheet_name!,
      row_start: row_start!,
      row_end: row_end!,
      source_anchor: source_anchor!,
    };
    const parent = {
      ...identity,
      chunk_id: 'v1::specs.xlsx::p0::l1::0',
      chunk_level: 1,
      merged_from_children: true,
      matched_leaf_sources: [
        first,
        {
          ...first,
          chunk_id: 'v1::specs.xlsx::p0::l3::4',
          row_start: 6,
          row_end: 6,
          source_anchor: 'sheet:Specs:row:6',
        },
      ],
      matched_leaf_sources_truncated: true,
    };
    expect(sourceLocation(parent)).toBe('父块正文；Specs · 命中行：2、6；部分命中来源未展示');
  });
  it('prefers selected evidence, even an empty selection', () => {
    expect(citationSources({ retrieved_chunks: [leaf], evidence_chunks: [] })).toEqual([]);
  });
  it('replays an independently numbered leaf while retaining its parent retrieval context', () => {
    const parent: RetrievedChunk = {
      filename: leaf.filename,
      chunk_id: 'v1::specs.xlsx::p0::l2::0',
      chunk_level: 2,
      document_id: leaf.document_id,
      document_version_id: leaf.document_version_id,
      section_id: leaf.section_id,
      index_version: leaf.index_version,
      content_hash: 'b'.repeat(64),
      merged_from_children: true,
      matched_leaf_sources: [
        {
          chunk_id: leaf.chunk_id,
          sheet_name: 'Specs',
          row_start: 2,
          row_end: 2,
          source_anchor: 'sheet:Specs:row:2',
        },
      ],
    };
    const trace = { retrieved_chunks: [parent], evidence_chunks: [leaf], cited_evidence_ids: [1] };
    const replay = validateRagTraceSources(JSON.parse(JSON.stringify(trace)));
    expect(citationSources(replay)).toEqual([leaf]);
    expect(sourceLocation(citationSources(replay)[0]!)).toBe('Specs · 第 2 行');
    expect(replay?.retrieved_chunks).toEqual([parent]);
  });
  it('preserves old PDF pages and does not invent rows for old XLSX', () => {
    const {
      sheet_name: _sheet,
      row_start: _start,
      row_end: _end,
      source_anchor: _anchor,
      ...legacy
    } = leaf;
    expect(sourceLocation({ ...legacy, page_number: 4 })).toBe('文件级来源');
    expect(sourceLocation({ ...legacy, filename: 'guide.pdf', page_number: 4 })).toBe('第 4 页');
  });
});
