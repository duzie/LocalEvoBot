/**
 * Smart File Input Component - 方案 C: 拖拽 + 智能识别
 * 
 * 功能:
 * 1. 拖拽文件/文件夹到聊天框
 * 2. 粘贴识别（路径/代码/图片）
 * 3. 路径自动补全
 * 4. 右键菜单
 */

class SmartFileInput {
  constructor(options = {}) {
    this.chatInput = options.chatInput || document.getElementById('chatInput')
    this.chatList = options.chatList || document.getElementById('chatList')
    this.sendBtn = options.sendBtn || document.getElementById('sendBtn')
    this.projectRoot = options.projectRoot || '.'
    
    this.dragOver = false
    this.contextMenu = null
    this.selectedFile = null
    this.autocompleteVisible = false
    this.suggestions = []
    
    this.init()
  }
  
  init() {
    this.setupDragDrop()
    this.setupPaste()
    this.setupAutocomplete()
    this.setupContextMenu()
    this.createDropZone()
    console.log('[SmartFileInput] 初始化完成')
  }
  
  // ========== 创建拖拽提示区域 ==========
  createDropZone() {
    const dropHint = document.createElement('div')
    dropHint.id = 'smartDropHint'
    dropHint.className = 'smart-drop-hint'
    dropHint.innerHTML = `
      <div class="drop-hint-content">
        <span class="drop-icon">📎</span>
        <span class="drop-text">拖拽文件/文件夹到此处，或粘贴路径/代码/截图</span>
      </div>
    `
    dropHint.style.display = 'none'
    
    if (this.chatList && this.chatList.parentElement) {
      this.chatList.parentElement.insertBefore(dropHint, this.chatList)
    }
    
    this.dropHint = dropHint
  }
  
  // ========== 拖拽处理 ==========
  // ========== 拖拽处理 ==========
  setupDragDrop() {
    // 使用更大的拖拽区域：整个 chatPane 或 chatInput 父元素
    const dropZone = this.chatInput.closest('.chatPane') || this.chatInput.parentElement || document.body
    this.dropZone = dropZone
    
    console.log('[SmartFileInput] 拖拽区域设置:', dropZone)
    console.log('[SmartFileInput] chatInput:', this.chatInput)
    console.log('[SmartFileInput] chatPane:', this.chatInput.closest('.chatPane'))
    
    // 全局拖拽事件（关键修复：阻止浏览器默认行为）
    document.addEventListener('dragenter', (e) => {
      console.log('[SmartFileInput] 全局 dragenter', e.target)
      e.preventDefault()
      e.stopPropagation()
    }, true)
    
    document.addEventListener('dragover', (e) => {
      e.preventDefault()
      e.stopPropagation()
      e.dataTransfer.dropEffect = 'copy'
    }, true)
    
    document.addEventListener('drop', (e) => {
      console.log('[SmartFileInput] 全局 drop', e.target)
      e.preventDefault()
      e.stopPropagation()
    }, true)
    
    // 拖拽进入
    dropZone.addEventListener('dragenter', (e) => {
      console.log('[SmartFileInput] dropZone dragenter', e.target)
      e.preventDefault()
      e.stopPropagation()
      this.dragOver = true
      this.showDropHint(e.dataTransfer)
      dropZone.classList.add('drag-over')
    })
    
    // 拖拽离开
    dropZone.addEventListener('dragleave', (e) => {
      e.preventDefault()
      e.stopPropagation()
      const rect = dropZone.getBoundingClientRect()
      if (e.clientX < rect.left || e.clientX >= rect.right || e.clientY < rect.top || e.clientY >= rect.bottom) {
        this.dragOver = false
        this.hideDropHint()
        dropZone.classList.remove('drag-over')
      }
    })
    
    // 拖拽中
    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault()
      e.stopPropagation()
      e.dataTransfer.dropEffect = 'copy'
    })
    
    // 放下文件
    dropZone.addEventListener('drop', (e) => {
      console.log('[SmartFileInput] dropZone drop', e.target, e.dataTransfer.files.length, 'files')
      e.preventDefault()
      e.stopPropagation()
      this.dragOver = false
      this.hideDropHint()
      dropZone.classList.remove('drag-over')
      this.handleDrop(e.dataTransfer)
    })
  }
  
  async handleDrop(dataTransfer) {
    const items = dataTransfer.items
    const files = dataTransfer.files
    
    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      try {
        if (item.kind === 'file' && item.getAsFileSystemHandle) {
          const handle = await item.getAsFileSystemHandle()
          await this.handleFileSystemHandle(handle)
          continue
        }
        if (item.kind === 'file') {
          const file = files[i]
          await this.handleFile(file)
          continue
        }
        if (item.kind === 'string') {
          const text = await this.getAsString(item)
          await this.handleTextDrop(text)
          continue
        }
      } catch (err) {
        console.error('[SmartFileInput] 处理拖拽项失败:', err)
      }
    }
  }
  
  async handleFileSystemHandle(handle) {
    if (handle.kind === 'file') {
      const file = await handle.getFile()
      
      // 尝试通过后端 API 匹配项目中的文件路径
      let matchedPath = handle.name
      console.log('[SmartFileInput] 🔍 开始匹配文件:', handle.name, '项目根目录:', this.projectRoot)
      try {
        const response = await fetch(`/api/files/list?path=${encodeURIComponent(this.projectRoot)}&recursive=true`)
        console.log('[SmartFileInput] 📡 API 响应状态:', response.status)
        if (response.ok) {
          const data = await response.json()
          console.log('[SmartFileInput] 📂 API 返回文件数量:', data.items ? data.items.length : 0)
          // 放宽匹配条件：只用文件名匹配（因为 size 可能有微小差异）
          const matched = data.items.find(f => f.name === handle.name)
          if (matched) {
            matchedPath = matched.rel_path || matched.path
            console.log('[SmartFileInput] ✅ 匹配到文件:', matched)
            console.log('[SmartFileInput] ✅ 使用路径:', matchedPath, '(rel_path:', matched.rel_path, ', path:', matched.path, ')')
          } else {
            console.log('[SmartFileInput] ❌ 未找到匹配文件:', handle.name)
            // 打印前10个文件名帮助调试
            if (data.items && data.items.length > 0) {
              console.log('[SmartFileInput] 📋 前10个文件:', data.items.slice(0, 10).map(f => f.name))
            }
          }
        }
      } catch (err) {
        console.warn('[SmartFileInput] ⚠️ 路径匹配失败，使用文件名:', err.message)
      }
      
      this.addFileToChat({ type: 'file', name: handle.name, path: matchedPath, file: file, source: 'drag-drop' })
    } else if (handle.kind === 'directory') {
      await this.traverseDirectory(handle, '')
    }
  }
  
  async traverseDirectory(dirHandle, path) {
    const entries = []
    try {
      for await (const entry of dirHandle.values()) {
        if (entry.kind === 'file') {
          const file = await entry.getFile()
          entries.push({ type: 'file', name: entry.name, path: `${path}/${entry.name}`, file: file })
        } else if (entry.kind === 'directory') {
          const subEntries = await this.traverseDirectory(entry, `${path}/${entry.name}`)
          entries.push(...subEntries)
        }
      }
      this.addFolderToChat({ type: 'folder', name: dirHandle.name, path: path, files: entries })
    } catch (err) {
      console.error('[SmartFileInput] 遍历目录失败:', err)
    }
  }
  
  async handleFile(file) {
    const fileInfo = await this.identifyFile(file)
    
    // 尝试通过后端 API 匹配项目中的文件路径
    let matchedPath = file.webkitRelativePath || file.name
    try {
      const response = await fetch(`/api/files/list?path=${encodeURIComponent(this.projectRoot)}&recursive=true`)
      if (response.ok) {
        const data = await response.json()
        // 放宽匹配条件：只用文件名匹配（因为 size 可能有微小差异）
          const matched = data.items.find(f => f.name === file.name)
        if (matched) {
          matchedPath = matched.rel_path || matched.path
          console.log('[SmartFileInput] ✅ 匹配到文件路径:', matchedPath)
        }
      }
    } catch (err) {
      console.warn('[SmartFileInput] ⚠️ 路径匹配失败，使用文件名:', err.message)
    }
    
    this.addFileToChat({ type: 'file', name: file.name, path: matchedPath, file: file, ...fileInfo, source: 'drag-drop' })
  }
  
  async handleTextDrop(text) {
    const result = await this.smartIdentifyText(text)
    if (result.type === 'file-path') this.addPathToChat(text)
    else if (result.type === 'code') this.addCodeToChat(text, result.language)
    else if (result.type === 'url') this.addPathToChat(text)
  }



  // ========== 粘贴处理 ==========
  setupPaste() {
    document.addEventListener('paste', (e) => {
      if (document.activeElement !== this.chatInput) return
      const clipboardData = e.clipboardData
      const items = clipboardData.items
      
      for (let i = 0; i < items.length; i++) {
        const item = items[i]
        if (item.type.startsWith('image/')) {
          e.preventDefault()
          const blob = item.getAsFile()
          this.addImageToChat(blob)
          return
        }
      }
      
      const text = clipboardData.getData('text')
      if (text) {
        this.smartIdentifyText(text).then(result => {
          if (result.type === 'file-path' && result.confidence > 0.8) {
            e.preventDefault()
            this.addPathToChat(text)
          }
        })
      }
    })
  }
  
  // ========== 智能文本识别 ==========
  async smartIdentifyText(text) {
    const trimmed = text.trim()
    if (this.isFilePath(trimmed)) return { type: 'file-path', confidence: 0.95 }
    if (this.isCodeSnippet(trimmed)) return { type: 'code', language: this.detectLanguageFromText(trimmed), confidence: 0.85 }
    if (this.isURL(trimmed)) return { type: 'url', confidence: 0.9 }
    return { type: 'text', confidence: 0.5 }
  }
  
  isFilePath(text) {
    if (/^[A-Za-z]:\\[^\s:*?"<>|]+/.test(text)) return true
    if (/^\/[^\s:*?"<>|]+/.test(text)) return true
    if (/^\.\.?\/[^\s:*?"<>|]+/.test(text)) return true
    if (/^\.\.?\\[^\s:*?"<>|]+/.test(text)) return true
    if (/\.[a-zA-Z0-9]+$/.test(text) && !text.includes(' ') && text.length < 500) return true
    return false
  }
  
  isCodeSnippet(text) {
    const codePatterns = [
      /^\s*(import|from|def|class|function|var|let|const|public|private|protected|interface)\s+/m,
      /^\s*(if|else|for|while|switch|try|catch|finally|return|yield)\s*[\(\{]?/m,
      /^\s*(export|default|async|await)\s+/m,
      /[{};]\s*$/,
      /^\s*\/\/.*$/m,
      /^\s*#.*$/m,
      /^\s*\/\*.*\*\/\s*$/m,
      /^\s*\*\s/m
    ]
    return codePatterns.some(pattern => pattern.test(text))
  }
  
  detectLanguageFromText(text) {
    if (/^\s*(import|from|def|class|async\s+def)\s+/m.test(text)) return 'python'
    if (/^\s*(function|const|let|var|=>|console\.log)\s*/m.test(text)) return 'javascript'
    if (/^\s*(public|private|protected|class|interface|implements)\s+/m.test(text)) return 'java'
    if (/^\s*(using|namespace|class|public|private)\s+/m.test(text)) return 'csharp'
    if (/<\!DOCTYPE html>|<html>|<head>|<body>|<div|<script/i.test(text)) return 'html'
    if (/^\s*[.#@][a-zA-Z].*\{|^\s*[a-zA-Z-]+\s*:\s*/m.test(text)) return 'css'
    if (/^\s*(package|func|import|println)\s+/m.test(text)) return 'go'
    if (/^\s*(fn|let|mut|impl|struct)\s+/m.test(text)) return 'rust'
    return 'plaintext'
  }
  
  isURL(text) {
    return /^https?:\/\/[^\s]+$/.test(text) || /^www\.[^\s]+$/.test(text)
  }
  
  getAsString(item) {
    return new Promise((resolve) => { item.getAsString(resolve) })
  }
  
  // ========== 文件识别 ==========
  async identifyFile(file) {
    const ext = file.name.split('.').pop().toLowerCase()
    const languageMap = {
      'py': 'python', 'js': 'javascript', 'ts': 'typescript',
      'html': 'html', 'css': 'css', 'json': 'json', 'md': 'markdown',
      'java': 'java', 'cs': 'csharp', 'cpp': 'cpp', 'c': 'c',
      'go': 'go', 'rs': 'rust', 'rb': 'ruby', 'php': 'php'
    }
    return { language: languageMap[ext] || 'plaintext', size: file.size, ext: ext }
  }
  
  // ========== 添加到聊天框 ==========
  addFileToChat(fileInfo) {
    const path = fileInfo.path || fileInfo.name
    const icon = this.getFileIcon(fileInfo.ext)
    const fileCard = this.createFileCard({ icon: icon, name: fileInfo.name, path: path, size: fileInfo.size, language: fileInfo.language, type: 'file' })
    this.insertFileCard(fileCard)
  }
  
  addFolderToChat(folderInfo) {
    const fileCount = folderInfo.files ? folderInfo.files.length : 0
    const folderCard = this.createFileCard({ icon: '📁', name: folderInfo.name, path: folderInfo.path, size: fileCount, type: 'folder', files: folderInfo.files })
    this.insertFileCard(folderCard)
  }
  
  addPathToChat(path) {
    const pathCard = this.createFileCard({ icon: '📎', name: path.split(/[\\/]/).pop(), path: path, type: 'path' })
    this.insertFileCard(pathCard)
  }
  
  addCodeToChat(code, language) {
    const prefix = `\n\`\`\`${language}\n`
    const suffix = `\n\`\`\`\n`
    const startPos = this.chatInput.selectionStart || 0
    const endPos = this.chatInput.selectionEnd || 0
    const text = this.chatInput.value
    this.chatInput.value = text.substring(0, startPos) + prefix + code + suffix + text.substring(endPos)
    this.chatInput.focus()
  }
  
  addImageToChat(blob) {
    const reader = new FileReader()
    reader.onload = (e) => {
      const imgCard = document.createElement('div')
      imgCard.className = 'file-card image-card'
      imgCard.innerHTML = `<div class="file-card-header"><span class="file-icon">🖼️</span><span class="file-name">粘贴的图片</span></div><img src="${e.target.result}" style="max-width:200px;max-height:150px;border-radius:8px;" /><button class="file-remove-btn" onclick="this.parentElement.remove()">×</button>`
      this.insertFileCard(imgCard)
    }
    reader.readAsDataURL(blob)
  }



  createFileCard(fileInfo) {
    const card = document.createElement('div')
    card.className = 'file-card'
    card.dataset.path = fileInfo.path
    card.dataset.type = fileInfo.type
    
    let sizeText = ''
    if (fileInfo.type === 'file' && fileInfo.size) {
      if (fileInfo.size < 1024) sizeText = fileInfo.size + ' B'
      else if (fileInfo.size < 1024 * 1024) sizeText = (fileInfo.size / 1024).toFixed(1) + ' KB'
      else sizeText = (fileInfo.size / (1024 * 1024)).toFixed(1) + ' MB'
    } else if (fileInfo.type === 'folder' && fileInfo.size) {
      sizeText = fileInfo.size + ' 个文件'
    }
    
    card.innerHTML = `
      <div class="file-card-header">
        <span class="file-icon">${fileInfo.icon}</span>
        <span class="file-name">${fileInfo.name}</span>
        ${sizeText ? `<span class="file-size">${sizeText}</span>` : ''}
      </div>
      <div class="file-card-path" title="${fileInfo.path}">${fileInfo.path}</div>
      <div class="file-card-actions">
        <button class="file-action-btn" onclick="smartFileInput.previewFile('${fileInfo.path}')" title="预览">👁</button>
        <button class="file-action-btn" onclick="smartFileInput.copyPath('${fileInfo.path}')" title="复制路径">📋</button>
        <button class="file-action-btn" onclick="smartFileInput.removeFileCard(this)" title="移除">×</button>
      </div>
    `
    return card
  }
  
  insertFileCard(card) {
    let container = document.getElementById('fileCardsContainer')
    if (!container) {
      container = document.createElement('div')
      container.id = 'fileCardsContainer'
      container.className = 'file-cards-container'
      const chatInputWrapper = this.chatInput.parentElement
      chatInputWrapper.insertBefore(container, this.chatInput)
    }
    container.appendChild(card)
  }
  
  removeFileCard(btn) { btn.parentElement.parentElement.remove() }
  
  async previewFile(path) {
    try {
      const res = await fetch(`/api/files/preview?path=${encodeURIComponent(path)}&lines=50`)
      const data = await res.json()
      if (data.error) { alert('预览失败：' + data.error); return }
      
      const modal = document.createElement('div')
      modal.className = 'file-preview-modal'
      modal.innerHTML = `
        <div class="file-preview-content">
          <div class="file-preview-header"><h3>📄 ${path.split(/[\\/]/).pop()}</h3><button class="close-btn" onclick="this.closest('.file-preview-modal').remove()">×</button></div>
          <div class="file-preview-body"><pre><code class="language-${data.language || 'plaintext'}">${this.escapeHtml(data.content)}</code></pre></div>
        </div>
      `
      document.body.appendChild(modal)
      modal.style.display = 'flex'
      modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove() })
    } catch (err) {
      console.error('[SmartFileInput] 预览失败:', err)
      alert('预览失败：' + err.message)
    }
  }
  
  copyPath(path) {
    navigator.clipboard.writeText(path).then(() => {
      const toast = document.createElement('div')
      toast.className = 'copy-toast'
      toast.textContent = '✓ 路径已复制'
      document.body.appendChild(toast)
      setTimeout(() => toast.remove(), 2000)
    }).catch(err => console.error('[SmartFileInput] 复制失败:', err))
  }
  
  showDropHint(dataTransfer) {
    if (!this.dropHint) return
    this.dropHint.style.display = 'block'
    const fileCount = dataTransfer.files ? dataTransfer.files.length : 0
    const text = fileCount > 0 ? `📎 释放以添加 ${fileCount} 个文件` : '📎 释放以添加内容'
    const hintText = this.dropHint.querySelector('.drop-text')
    if (hintText) hintText.textContent = text
  }
  
  hideDropHint() { if (this.dropHint) this.dropHint.style.display = 'none' }
  
  getFileIcon(ext) {
    const icons = {
      'py': '🐍', 'js': '📜', 'ts': '📘', 'html': '🌐', 'css': '🎨',
      'json': '📋', 'md': '📝', 'java': '☕', 'cs': '⚡', 'cpp': '⚙️',
      'c': '⚙️', 'go': '🐹', 'rs': '🦀', 'rb': '💎', 'php': '🐘'
    }
    return icons[ext] || '📄'
  }
  
  escapeHtml(text) {
    const div = document.createElement('div')
    div.textContent = text
    return div.innerHTML
  }
  
  // ========== 获取待发送的文件路径列表 ==========
  getPendingFilePaths() {
    const fileCards = document.querySelectorAll('#fileCardsContainer .file-card')
    const paths = []
    fileCards.forEach(card => {
      const pathElem = card.querySelector('.file-card-path')
      if (pathElem) {
        paths.push(pathElem.textContent.trim())
      }
    })
    return paths
  }
  
  // ========== 清空文件卡片 ==========
  clearFileCards() {
    const container = document.getElementById('fileCardsContainer')
    if (container) {
      container.innerHTML = ''
    }
  }
  
  setupContextMenu() { /* 预留右键菜单功能 */ }
  setupAutocomplete() { /* 预留自动补全功能 */ }
}

// 全局实例
window.smartFileInput = null

document.addEventListener('DOMContentLoaded', () => {
  window.smartFileInput = new SmartFileInput({
    chatInput: document.getElementById('chatInput'),
    chatList: document.getElementById('chatList'),
    sendBtn: document.getElementById('sendBtn')
  })
})
