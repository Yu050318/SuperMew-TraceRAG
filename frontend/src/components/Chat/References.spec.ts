// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { createApp, nextTick, type App } from 'vue';
import References from './References.vue';
import MessageContent from './MessageContent.vue';
import type { Message, RetrievedChunk } from '@/types/chat';

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
  text: 'Power 120 W',
};

describe('answer citation components', () => {
  let app: App | null = null;
  let root: HTMLDivElement | null = null;
  afterEach(() => {
    app?.unmount();
    root?.remove();
  });
  it('shows selected sources and their cited status, not discarded candidates', async () => {
    const msg: Message = {
      text: '120 W[1]',
      isUser: false,
      ragTrace: {
        retrieved_chunks: [leaf, { ...leaf, filename: 'other.html' }],
        evidence_chunks: [leaf],
        cited_evidence_ids: [1],
      },
    };
    root = document.createElement('div');
    document.body.append(root);
    app = createApp(References, { msg, msgIndex: 0 });
    app.mount(root);
    await nextTick();
    expect(root.textContent).toContain('Specs · 第 2 行');
    expect(root.textContent).toContain('回答已引用');
    expect(root.textContent).not.toContain('other.html');
    expect(root.querySelector('#chunk-0-1')).not.toBeNull();
  });
  it('does not turn an unknown citation marker into a clickable source', async () => {
    root = document.createElement('div');
    document.body.append(root);
    app = createApp(MessageContent, {
      text: 'real[1] false[99] `code[99]`',
      isUser: false,
      msgIndex: 0,
      allowedCitationIds: [1],
    });
    app.mount(root);
    await nextTick();
    expect(root.querySelectorAll('.cite-ref')).toHaveLength(1);
    expect(root.querySelector('.cite-ref')?.getAttribute('data-chunk-index')).toBe('1');
    expect(root.textContent).toContain('false[99]');
  });
});
