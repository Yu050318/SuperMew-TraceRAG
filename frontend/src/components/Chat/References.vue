<template>
  <div v-if="sources.length" class="references-section">
    <details ref="detailsRef" class="references-details">
      <summary class="references-title">
        <span><i class="fa-regular fa-bookmark"></i> 引用来源</span>
        <small
          >{{ sources.length }} 个{{
            msg.ragTrace?.evidence_chunks ? '入选证据' : '检索片段（旧记录）'
          }}</small
        >
      </summary>
      <ul class="sources-list references-list">
        <li
          v-for="(chunk, cIdx) in sources"
          :id="'chunk-' + msgIndex + '-' + (cIdx + 1)"
          :key="cIdx"
          class="source-item"
        >
          <button
            type="button"
            class="ref-index cite-ref"
            :data-msg-index="msgIndex"
            :data-chunk-index="cIdx + 1"
            @click="onCiteClick(cIdx + 1)"
          >
            {{ cIdx + 1 }}
          </button>
          <div class="source-content">
            <div class="source-title-line">
              <span class="source-file"
                ><i class="fa-regular fa-file-lines"></i>{{ chunk.filename }}</span
              >
              <span class="source-page">{{ sourceLocation(chunk) }}</span>
            </div>
            <div class="source-meta-line">
              <span>{{
                msg.ragTrace?.cited_evidence_ids?.includes(cIdx + 1)
                  ? '回答已引用'
                  : msg.ragTrace?.evidence_chunks
                    ? '入选但未引用'
                    : '仅检索记录'
              }}</span>
              <span v-if="chunk.evidence_text_truncated">证据正文已截断</span>
              <span>RRF #{{ chunk.rrf_rank || cIdx + 1 }}</span>
              <span v-if="chunk.rerank_score !== null && chunk.rerank_score !== undefined">
                Rerank {{ Number(chunk.rerank_score).toFixed(4) }}
              </span>
            </div>
            <div v-if="chunk.text" class="source-excerpt">{{ chunk.text }}</div>
          </div>
        </li>
      </ul>
    </details>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import type { Message } from '@/types/chat';
import { citationSources, sourceLocation } from '@/utils/ragSources';

const props = defineProps<{
  msg: Message;
  msgIndex: number;
}>();

const emit = defineEmits<{
  (e: 'cite-click', msgIndex: number, chunkIndex: number): void;
}>();

const detailsRef = ref<HTMLDetailsElement | null>(null);
const sources = computed(() => citationSources(props.msg.ragTrace));

const openDetails = () => {
  if (detailsRef.value) detailsRef.value.open = true;
};

defineExpose({ openDetails });

const onCiteClick = (chunkIndex: number) => {
  if (!Number.isInteger(chunkIndex) || chunkIndex < 1 || chunkIndex > sources.value.length) return;
  emit('cite-click', props.msgIndex, chunkIndex);
};
</script>
