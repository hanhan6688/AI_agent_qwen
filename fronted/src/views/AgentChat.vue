<template>
  <div class="agent-shell">
    <header class="chat-header">
      <div>
        <p class="eyebrow">LangChain Metric Agent</p>
        <h1>智能指标提取智能体</h1>
      </div>
      <div class="mode-tabs">
        <button
          v-for="mode in agentModes"
          :key="mode.value"
          :class="{ active: activeMode === mode.value }"
          @click="activeMode = mode.value"
        >
          {{ mode.label }}
        </button>
      </div>
    </header>

    <main ref="messageListRef" class="chat-window">
      <article
        v-for="(message, index) in messages"
        :key="`${message.role}-${index}`"
        class="message"
        :class="message.role"
      >
        <div class="avatar">{{ message.role === 'assistant' ? 'AI' : 'U' }}</div>
        <div class="bubble">
          <div v-if="message.attachments?.length" class="attachment-row">
            <span v-for="file in message.attachments" :key="file.name">PDF {{ file.name }}</span>
          </div>
          <div class="rendered" v-html="renderContent(message.content)" />
          <span v-if="message.streaming" class="cursor"></span>

      <div v-if="message.route" class="route-card">
        <div>
          <strong>{{ message.route.intentLabel || message.route.intent }}</strong>
          <span>{{ routeToolText(message.route.tool) }} · {{ modeText(message.route.recommendedMode) }} · {{ Math.round((message.route.confidence || 0) * 100) }}%</span>
        </div>
            <p :title="message.route.reason">{{ message.route.reason }}</p>
            <button
              v-if="message.route.shouldEnterExtraction"
              type="button"
              @click="goToExtraction(message.route)"
            >
              去上传解析页
            </button>
          </div>
        </div>
      </article>
    </main>

    <section class="quick-prompts">
      <button v-for="item in suggestions" :key="item" @click="inputText = item">
        {{ item }}
      </button>
    </section>

    <form class="composer" @submit.prevent="sendMessage">
      <div v-if="selectedFiles.length" class="selected-files">
        <span v-for="(file, index) in selectedFiles" :key="`${file.name}-${index}`">
          {{ file.name }}
          <button type="button" @click="removeFile(index)">×</button>
        </span>
      </div>

      <div class="composer-main">
        <input
          ref="fileInputRef"
          type="file"
          accept=".pdf,application/pdf"
          multiple
          hidden
          @change="handleFileSelect"
        />
        <button type="button" class="attach-btn" @click="fileInputRef?.click()">
          PDF
        </button>
        <textarea
          v-model="inputText"
          rows="2"
          :placeholder="activeModeMeta.placeholder"
          @keydown.enter.exact.prevent="sendMessage"
        />
        <button class="send-btn" type="submit" :disabled="loading || (!inputText.trim() && selectedFiles.length === 0)">
          {{ loading ? '生成中...' : '发送' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { agentApi } from '../api'

const router = useRouter()
const activeMode = ref('normal')
const inputText = ref('')
const loading = ref(false)
const selectedFiles = ref([])
const fileInputRef = ref(null)
const messageListRef = ref(null)
let scrollFrame = 0

const agentModes = [
  {
    value: 'normal',
    label: '普通版',
    placeholder: '输入问题，或上传 PDF 后让智能体提取指标...'
  },
  {
    value: 'pro',
    label: '专业版',
    placeholder: '上传复杂图表 PDF，或要求输出 Markdown / JSON...'
  }
]

const messages = ref([
  {
    role: 'assistant',
    content: '你好，我是基于通义千问大模型的智能指标提取智能体。现在支持 LangChain 流式对话、Markdown/JSON 渲染，以及在对话框直接上传 PDF。'
  }
])

const activeModeMeta = computed(() => agentModes.find(mode => mode.value === activeMode.value) || agentModes[0])

const suggestions = computed(() => {
  if (activeMode.value === 'pro') {
    return [
      '上传PDF后提取指标，JSON输出',
      '表格逐行展开成JSON'
    ]
  }
  return [
    '设计材料学提取字段',
    '普通版和专业版区别'
  ]
})

const scrollToBottom = async () => {
  await nextTick()
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

const scheduleScrollToBottom = () => {
  if (scrollFrame) {
    cancelAnimationFrame(scrollFrame)
  }
  scrollFrame = requestAnimationFrame(() => {
    scrollFrame = 0
    scrollToBottom()
  })
}

const handleFileSelect = (event) => {
  const files = Array.from(event.target.files || [])
  const pdfFiles = files.filter(file => file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf'))
  const rejected = files.length - pdfFiles.length
  selectedFiles.value.push(...pdfFiles)
  if (rejected > 0) {
    messages.value.push({ role: 'assistant', content: `已忽略 ${rejected} 个非 PDF 文件。` })
  }
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

const removeFile = (index) => {
  selectedFiles.value.splice(index, 1)
}

const sendMessage = async () => {
  if (loading.value || (!inputText.value.trim() && selectedFiles.value.length === 0)) {
    return
  }

  const text = inputText.value.trim() || '请分析我上传的 PDF，并提取关键指标。'
  const filesToSend = [...selectedFiles.value]
  const attachments = filesToSend.map(file => ({ name: file.name, size: file.size }))

  messages.value.push({ role: 'user', content: text, attachments })
  inputText.value = ''
  selectedFiles.value = []

  const assistantMessage = {
    role: 'assistant',
    content: '',
    route: null,
    streaming: true
  }
  messages.value.push(assistantMessage)
  const assistantIndex = messages.value.length - 1
  loading.value = true
  await scrollToBottom()

  const updateAssistant = (patch) => {
    const current = messages.value[assistantIndex]
    if (!current) {
      return
    }
    messages.value[assistantIndex] = { ...current, ...patch }
    scheduleScrollToBottom()
  }

  const appendAssistantContent = (chunk) => {
    if (!chunk) {
      return
    }
    const current = messages.value[assistantIndex]
    if (!current) {
      return
    }
    messages.value[assistantIndex] = {
      ...current,
      content: `${current.content || ''}${chunk}`
    }
    scheduleScrollToBottom()
  }

  const history = messages.value
    .filter(message => !message.streaming)
    .slice(-10)
    .map(message => ({ role: message.role, content: message.content }))

  try {
    await agentApi.streamChat({
      message: text,
      history,
      mode: activeMode.value,
      files: filesToSend,
      onMeta: (data) => {
        updateAssistant({ route: data.route || null })
      },
      onDelta: (chunk) => {
        appendAssistantContent(chunk)
      },
      onDone: (data) => {
        const current = messages.value[assistantIndex]
        if (current && !current.content && data.reply) {
          updateAssistant({ content: data.reply, route: data.route || current.route })
          return
        }
        updateAssistant({ route: data.route || current?.route || null })
      },
      onError: (message) => {
        appendAssistantContent(`\n\n> ${message}`)
      }
    })
  } catch (error) {
    updateAssistant({ content: error.message || '流式对话失败，请稍后重试。' })
  } finally {
    updateAssistant({ streaming: false })
    loading.value = false
    await scrollToBottom()
  }
}

const modeText = (mode) => mode === 'pro' ? '专业版' : '普通版'

const routeToolText = (tool) => {
  const labels = {
    document_parser: '文档解析',
    field_schema_builder: '字段配置',
    export_builder: '导出工具',
    result_interpreter: '结果解释',
    none: '普通问答'
  }
  return labels[tool] || tool || '普通问答'
}

const goToExtraction = (route) => {
  if (route?.recommendedMode) {
    sessionStorage.setItem('agentRecommendedMode', route.recommendedMode)
  }
  if (route?.reason) {
    sessionStorage.setItem('agentRouteReason', route.reason)
  }
  router.push('/')
}

const escapeHtml = (value) => {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

const renderInline = (value) => {
  return escapeHtml(value)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
}

const isTableRow = (line) => /^\s*\|.*\|\s*$/.test(line)

const isTableDivider = (line) => {
  const cells = splitTableRow(line)
  return cells.length > 1 && cells.every(cell => /^:?-{3,}:?$/.test(cell))
}

const splitTableRow = (line) => line
  .trim()
  .replace(/^\|/, '')
  .replace(/\|$/, '')
  .split('|')
  .map(cell => cell.trim())

const renderTable = (tableLines) => {
  const dividerIndex = tableLines.findIndex(isTableDivider)
  if (dividerIndex <= 0) {
    return tableLines.map(line => `<p>${renderInline(line)}</p>`).join('')
  }

  const headers = splitTableRow(tableLines[dividerIndex - 1])
  const bodyRows = tableLines
    .slice(dividerIndex + 1)
    .filter(line => isTableRow(line) && !isTableDivider(line))
    .map(splitTableRow)

  const thead = `<thead><tr>${headers.map(cell => `<th>${renderInline(cell)}</th>`).join('')}</tr></thead>`
  const tbody = `<tbody>${bodyRows.map(row => (
    `<tr>${headers.map((_, index) => `<td>${renderInline(row[index] || '')}</td>`).join('')}</tr>`
  )).join('')}</tbody>`

  return `<div class="table-wrap"><table>${thead}${tbody}</table></div>`
}

const renderMarkdownBlock = (block) => {
  const lines = block.split(/\r?\n/)
  let html = ''
  let listType = null

  const closeList = () => {
    if (!listType) {
      return
    }
    html += listType === 'ol' ? '</ol>' : '</ul>'
    listType = null
  }

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]
    const trimmed = line.trim()

    if (!trimmed) {
      const nextTableIndex = lines.findIndex((candidate, index) => index > i && candidate.trim())
      if (nextTableIndex > i && isTableRow(lines[nextTableIndex])) {
        continue
      }
      closeList()
      html += '<br />'
      continue
    }

    if (isTableRow(trimmed)) {
      const tableLines = [trimmed]
      let cursor = i + 1
      while (cursor < lines.length) {
        const next = lines[cursor].trim()
        if (!next) {
          const nextContentIndex = lines.findIndex((candidate, index) => index > cursor && candidate.trim())
          if (nextContentIndex > cursor && isTableRow(lines[nextContentIndex].trim())) {
            cursor += 1
            continue
          }
          break
        }
        if (!isTableRow(next)) {
          break
        }
        tableLines.push(next)
        cursor += 1
      }

      if (tableLines.some(isTableDivider)) {
        closeList()
        html += renderTable(tableLines)
        i = cursor - 1
        continue
      }
    }

    const unorderedMatch = line.match(/^\s*[-*]\s+(.+)$/)
    if (unorderedMatch) {
      if (listType !== 'ul') {
        closeList()
        html += '<ul>'
        listType = 'ul'
      }
      html += `<li>${renderInline(unorderedMatch[1])}</li>`
      continue
    }

    const orderedMatch = line.match(/^\s*\d+[.)]\s+(.+)$/)
    if (orderedMatch) {
      if (listType !== 'ol') {
        closeList()
        html += '<ol>'
        listType = 'ol'
      }
      html += `<li>${renderInline(orderedMatch[1])}</li>`
      continue
    }

    closeList()

    if (/^####\s+/.test(line)) html += `<h4>${renderInline(line.replace(/^####\s+/, ''))}</h4>`
    else if (/^###\s+/.test(line)) html += `<h3>${renderInline(line.replace(/^###\s+/, ''))}</h3>`
    else if (/^##\s+/.test(line)) html += `<h2>${renderInline(line.replace(/^##\s+/, ''))}</h2>`
    else if (/^#\s+/.test(line)) html += `<h1>${renderInline(line.replace(/^#\s+/, ''))}</h1>`
    else if (/^>\s?/.test(line)) html += `<blockquote>${renderInline(line.replace(/^>\s?/, ''))}</blockquote>`
    else html += `<p>${renderInline(trimmed)}</p>`
  }

  closeList()
  return html
}

const renderContent = (content) => {
  const text = String(content || '')
  const trimmed = text.trim()
  if (!trimmed) {
    return '<span class="muted">正在生成...</span>'
  }

  if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
    try {
      return `<pre class="json-block"><code>${escapeHtml(JSON.stringify(JSON.parse(trimmed), null, 2))}</code></pre>`
    } catch {
      // fall through to markdown renderer
    }
  }

  const parts = text.split(/(```[\s\S]*?```)/g)
  return parts.map(part => {
    if (part.startsWith('```')) {
      const code = part.replace(/^```[a-zA-Z0-9_-]*\s*/, '').replace(/```$/, '')
      return `<pre><code>${escapeHtml(code)}</code></pre>`
    }
    return renderMarkdownBlock(part)
  }).join('')
}

onMounted(() => {
  agentApi.profile().catch(() => {})
  scrollToBottom()
})

onBeforeUnmount(() => {
  if (scrollFrame) {
    cancelAnimationFrame(scrollFrame)
  }
})
</script>

<style scoped>
.agent-shell {
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto auto;
  gap: 0.55rem;
  padding: 0.75rem;
  color: #e7edf6;
}

.chat-header,
.composer,
.quick-prompts,
.chat-window {
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.72);
  box-shadow: 0 12px 34px rgba(0, 0, 0, 0.14);
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.6rem 0.75rem;
  border-radius: 16px;
}

.eyebrow {
  margin: 0;
  color: #67e8f9;
  font-size: 0.64rem;
  font-weight: 900;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.chat-header h1 {
  margin: 0;
  color: #f8fafc;
  font-size: 1.05rem;
}

.mode-tabs {
  display: inline-flex;
  padding: 0.18rem;
  border-radius: 999px;
  background: rgba(2, 6, 23, 0.55);
}

.mode-tabs button {
  border: none;
  border-radius: 999px;
  padding: 0.42rem 0.7rem;
  color: #94a3b8;
  background: transparent;
  cursor: pointer;
  font-weight: 800;
}

.mode-tabs button.active {
  color: #082f49;
  background: linear-gradient(135deg, #67e8f9, #38bdf8);
}

.chat-window {
  overflow: auto;
  padding: 0.85rem;
  border-radius: 18px;
}

.message {
  display: flex;
  gap: 0.55rem;
  margin-bottom: 0.68rem;
  align-items: flex-start;
}

.message.user {
  flex-direction: row-reverse;
}

.avatar {
  flex: 0 0 auto;
  width: 31px;
  height: 31px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  color: #fff;
  font-weight: 900;
  background: linear-gradient(135deg, #0891b2, #2563eb);
}

.message.user .avatar {
  background: linear-gradient(135deg, #f59e0b, #ef4444);
}

.bubble {
  max-width: min(920px, 84%);
  padding: 0.68rem 0.78rem;
  border-radius: 15px;
  color: #e2e8f0;
  background: rgba(30, 41, 59, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.14);
  line-height: 1.55;
}

.message.user .bubble {
  background: rgba(37, 99, 235, 0.78);
}

.attachment-row,
.selected-files {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-bottom: 0.42rem;
}

.attachment-row span,
.selected-files span {
  padding: 0.2rem 0.45rem;
  border-radius: 999px;
  color: #bae6fd;
  background: rgba(14, 116, 144, 0.24);
  font-size: 0.78rem;
}

.selected-files span button {
  margin-left: 0.35rem;
  border: none;
  color: #fecaca;
  background: transparent;
  cursor: pointer;
}

.route-card {
  margin-top: 0.5rem;
  padding: 0.5rem 0.55rem;
  border-radius: 12px;
  background: rgba(8, 47, 73, 0.48);
  border: 1px solid rgba(34, 211, 238, 0.22);
}

.route-card div {
  display: flex;
  justify-content: space-between;
  gap: 0.55rem;
}

.route-card strong {
  color: #f8fafc;
}

.route-card span,
.route-card p {
  color: #b6c6d9;
  font-size: 0.76rem;
}

.route-card p {
  margin-top: 0.28rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.route-card button {
  margin-top: 0.4rem;
  border: none;
  border-radius: 10px;
  padding: 0.36rem 0.55rem;
  color: #082f49;
  background: #67e8f9;
  cursor: pointer;
  font-weight: 900;
}

.cursor {
  display: inline-block;
  width: 0.55rem;
  height: 1rem;
  margin-left: 0.2rem;
  background: #67e8f9;
  animation: blink 0.9s steps(2, start) infinite;
  vertical-align: middle;
}

@keyframes blink {
  50% { opacity: 0; }
}

.quick-prompts {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  padding: 0.45rem;
  border-radius: 14px;
}

.quick-prompts button {
  border: 1px solid rgba(125, 211, 252, 0.22);
  border-radius: 999px;
  padding: 0.36rem 0.58rem;
  color: #dbeafe;
  background: rgba(8, 47, 73, 0.48);
  cursor: pointer;
}

.composer {
  padding: 0.55rem;
  border-radius: 16px;
}

.composer-main {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr) 70px;
  gap: 0.5rem;
  align-items: stretch;
}

.composer textarea {
  resize: none;
  min-height: 42px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  padding: 0.58rem 0.7rem;
  color: #e2e8f0;
  background: rgba(2, 6, 23, 0.45);
  outline: none;
  line-height: 1.42;
}

.composer textarea:focus {
  border-color: rgba(34, 211, 238, 0.55);
}

.attach-btn,
.send-btn {
  border: none;
  border-radius: 12px;
  padding: 0 0.7rem;
  color: #e0f2fe;
  background: rgba(14, 116, 144, 0.42);
  cursor: pointer;
  font-weight: 900;
}

.send-btn {
  color: #082f49;
  background: linear-gradient(135deg, #67e8f9, #38bdf8);
}

.send-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

:deep(.rendered p) {
  margin: 0.24rem 0;
}

:deep(.rendered h1),
:deep(.rendered h2),
:deep(.rendered h3),
:deep(.rendered h4) {
  margin: 0.42rem 0 0.25rem;
  color: #f8fafc;
}

:deep(.rendered ul),
:deep(.rendered ol) {
  margin: 0.3rem 0;
  padding-left: 1.2rem;
}

:deep(.rendered blockquote) {
  margin: 0.42rem 0;
  padding: 0.42rem 0.6rem;
  border-left: 3px solid #67e8f9;
  border-radius: 0 0.55rem 0.55rem 0;
  color: #cbd5e1;
  background: rgba(8, 47, 73, 0.34);
}

:deep(.table-wrap) {
  width: 100%;
  overflow-x: auto;
  margin: 0.55rem 0;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.16);
}

:deep(.rendered table) {
  width: 100%;
  min-width: 560px;
  border-collapse: collapse;
  background: rgba(2, 6, 23, 0.38);
}

:deep(.rendered th),
:deep(.rendered td) {
  padding: 0.5rem 0.58rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
  border-right: 1px solid rgba(148, 163, 184, 0.1);
  text-align: left;
  vertical-align: top;
  font-size: 0.82rem;
}

:deep(.rendered th) {
  color: #e0f2fe;
  background: rgba(14, 116, 144, 0.32);
  font-weight: 900;
  white-space: nowrap;
}

:deep(.rendered tr:last-child td) {
  border-bottom: none;
}

:deep(.rendered code) {
  padding: 0.1rem 0.25rem;
  border-radius: 0.35rem;
  color: #bae6fd;
  background: rgba(2, 6, 23, 0.55);
}

:deep(.rendered pre) {
  overflow: auto;
  margin: 0.45rem 0;
  padding: 0.62rem;
  border-radius: 11px;
  color: #dbeafe;
  background: rgba(2, 6, 23, 0.72);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

:deep(.muted) {
  color: #94a3b8;
}

@media (max-width: 760px) {
  .agent-shell {
    min-height: 100%;
    padding: 0.55rem;
  }

  .chat-header,
  .composer-main {
    grid-template-columns: 1fr;
    display: grid;
  }

  .mode-tabs {
    width: 100%;
  }

  .mode-tabs button {
    flex: 1;
  }

  .bubble {
    max-width: 90%;
  }

  .quick-prompts {
    display: none;
  }
}
</style>
