/**
 * Markdown 渲染工具
 * 使用 marked + highlight.js + DOMPurify
 */
import { Marked } from 'marked'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'

// 创建带代码高亮的 marked 实例
const marked = new Marked({
  renderer: {
    code({ text, lang }: { text: string; lang?: string }) {
      const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
      let highlighted: string
      try {
        highlighted = hljs.highlight(text, { language }).value
      } catch {
        highlighted = hljs.highlightAuto(text).value
      }
      const langLabel = lang || 'code'
      return `<div class="code-block"><div class="code-header"><span class="code-lang">${langLabel}</span><button class="copy-btn" onclick="navigator.clipboard.writeText(this.closest('.code-block').querySelector('code').textContent)">复制</button></div><pre><code class="hljs language-${language}">${highlighted}</code></pre></div>`
    },
  },
  gfm: true,
  breaks: true,
})

/**
 * 将 Markdown 文本渲染为安全的 HTML
 */
export function renderMarkdown(text: string): string {
  if (!text) return ''

  // 渲染 Markdown → HTML
  const rawHtml = marked.parse(text) as string

  // DOMPurify 清洗 XSS
  const cleanHtml = DOMPurify.sanitize(rawHtml, {
    ALLOWED_TAGS: [
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'p', 'br', 'hr',
      'strong', 'em', 'b', 'i', 'u', 's', 'del', 'mark',
      'ul', 'ol', 'li',
      'blockquote',
      'pre', 'code',
      'a',
      'img',
      'table', 'thead', 'tbody', 'tr', 'th', 'td',
      'div', 'span',
      'button',
      'sup', 'sub',
      'details', 'summary',
      'input', // for task lists
    ],
    ALLOWED_ATTR: [
      'href', 'target', 'rel',
      'src', 'alt', 'title', 'width', 'height',
      'class', 'id',
      'colspan', 'rowspan',
      'onclick', // for copy button
      'type', 'checked', 'disabled', // for task lists
    ],
  })

  return cleanHtml
}
