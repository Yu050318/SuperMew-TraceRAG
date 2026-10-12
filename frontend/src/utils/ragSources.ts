import type { ExcelSource, RagTrace, RetrievedChunk } from '@/types/chat';

export function citationSources(trace?: RagTrace | null): RetrievedChunk[] {
  return trace?.evidence_chunks ?? trace?.retrieved_chunks ?? [];
}

export function allowedCitationIds(trace?: RagTrace | null): number[] {
  return citationSources(trace).map((_, index) => index + 1);
}

function anchor(source: ExcelSource): string {
  const sheet = encodeURIComponent(source.sheet_name).replace(
    /[!'()*]/g,
    (char) => '%' + char.charCodeAt(0).toString(16).toUpperCase()
  );
  return (
    `sheet:${sheet}:row:${source.row_start}` +
    (source.row_start === source.row_end ? '' : `-${source.row_end}`)
  );
}

function validateSource(source: ExcelSource): void {
  if (
    typeof source.sheet_name !== 'string' ||
    !source.sheet_name.length ||
    source.sheet_name.length > 31 ||
    [...source.sheet_name].some((char) => char.charCodeAt(0) < 32 || '/\\:*?[]'.includes(char)) ||
    !Number.isInteger(source.row_start) ||
    !Number.isInteger(source.row_end) ||
    source.row_start < 1 ||
    source.row_end < source.row_start ||
    source.row_end > 10000 ||
    source.source_anchor !== anchor(source)
  ) {
    throw new Error('Invalid RAG source contract');
  }
}

export function validateChunkSource(chunk: RetrievedChunk): void {
  const direct = ['sheet_name', 'row_start', 'row_end', 'source_anchor'].some(
    (key) => chunk[key as keyof RetrievedChunk] != null
  );
  if (!direct && chunk.matched_leaf_sources == null && chunk.matched_leaf_sources_truncated == null)
    return;
  if (
    !chunk.filename.toLowerCase().endsWith('.xlsx') ||
    [...chunk.filename].some((char) => char.charCodeAt(0) < 32 || '/\\'.includes(char)) ||
    !chunk.document_id ||
    !chunk.document_version_id ||
    !chunk.index_version ||
    !chunk.section_id ||
    !/^[a-fA-F0-9]{64}$/.test(chunk.content_hash)
  )
    throw new Error('Invalid RAG source identity');
  const prefix = `${chunk.document_version_id}::${chunk.filename}::p0::`;
  const own = chunk.chunk_id?.slice(prefix.length);
  if (
    !chunk.chunk_id?.startsWith(prefix) ||
    !new RegExp(`^l${chunk.chunk_level}::[0-9]+$`).test(own)
  )
    throw new Error('Invalid RAG source identity');
  if (direct) {
    if (chunk.chunk_level !== 3 || chunk.merged_from_children)
      throw new Error('Invalid RAG leaf source');
    validateSource({
      sheet_name: chunk.sheet_name!,
      row_start: chunk.row_start!,
      row_end: chunk.row_end!,
      source_anchor: chunk.source_anchor!,
    });
  }
  if (chunk.matched_leaf_sources != null) {
    if (
      direct ||
      !chunk.merged_from_children ||
      ![1, 2].includes(chunk.chunk_level!) ||
      !Array.isArray(chunk.matched_leaf_sources) ||
      chunk.matched_leaf_sources.length > 32 ||
      new TextEncoder().encode(JSON.stringify(chunk.matched_leaf_sources)).length > 16384
    )
      throw new Error('Invalid RAG parent source');
    for (const leaf of chunk.matched_leaf_sources) {
      validateSource(leaf);
      if (
        !leaf.chunk_id.startsWith(prefix) ||
        !/^l3::[0-9]+$/.test(leaf.chunk_id.slice(prefix.length))
      )
        throw new Error('Foreign RAG leaf source');
    }
  } else if (chunk.matched_leaf_sources_truncated != null)
    throw new Error('Missing RAG parent sources');
}

export function validateRagTraceSources(trace: RagTrace | null): RagTrace | null {
  if (!trace) return trace;
  for (const chunks of [
    trace.retrieved_chunks,
    trace.initial_retrieved_chunks,
    trace.rewrite_retrieved_chunks,
    trace.hitl_targeted_retrieved_chunks,
    trace.evidence_chunks,
  ]) {
    for (const chunk of chunks ?? []) validateChunkSource(chunk);
  }
  if (
    trace.cited_evidence_ids?.some(
      (id) =>
        !Number.isInteger(id) ||
        id < 1 ||
        trace.evidence_chunks === undefined ||
        id > trace.evidence_chunks.length
    )
  )
    throw new Error('Invalid RAG citation identity');
  for (const child of trace.sub_traces ?? []) validateRagTraceSources(child);
  return trace;
}

function rowLabel(source: ExcelSource): string {
  return source.row_start === source.row_end
    ? String(source.row_start)
    : `${source.row_start}～${source.row_end}`;
}

export function sourceLocation(chunk: RetrievedChunk): string {
  validateChunkSource(chunk);
  if (chunk.sheet_name)
    return `${chunk.sheet_name} · 第 ${rowLabel({ sheet_name: chunk.sheet_name, row_start: chunk.row_start!, row_end: chunk.row_end!, source_anchor: chunk.source_anchor! })} 行`;
  if (chunk.matched_leaf_sources) {
    const sheets = new Map<string, Set<string>>();
    for (const leaf of chunk.matched_leaf_sources) {
      if (!sheets.has(leaf.sheet_name)) sheets.set(leaf.sheet_name, new Set());
      sheets.get(leaf.sheet_name)!.add(rowLabel(leaf));
    }
    const locations = [...sheets.entries()]
      .sort()
      .map(
        ([sheet, rows]) =>
          `${sheet} · 命中行：${[...rows].sort((a, b) => parseInt(a) - parseInt(b)).join('、')}`
      );
    return (
      '父块正文；' +
      locations.join('；') +
      (chunk.matched_leaf_sources_truncated ? '；部分命中来源未展示' : '')
    );
  }
  if (/\.xlsx?$/i.test(chunk.filename)) return '文件级来源';
  return chunk.page_number ? `第 ${chunk.page_number} 页` : '文件级来源';
}
