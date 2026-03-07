;(function(){
  function ensureStyle(){
    if (document.getElementById('shellStyle')) return
    var style = document.createElement('style')
    style.id = 'shellStyle'
    style.textContent = [
      '.shellHeader{margin-top:6px;padding:14px 16px;background:var(--card,#fff);border:1px solid var(--border,#e5e7eb);border-radius:var(--radius,14px);display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;box-shadow:var(--shadow,0 8px 24px rgba(15,23,42,.08))}',
      '.shellLeft{display:flex;align-items:center;gap:10px;flex-wrap:wrap;min-width:0}',
      '.shellBrand{font-weight:800;display:flex;align-items:center;gap:10px;min-width:0}',
      '.shellTitle{font-size:12px;color:var(--muted,#6b1024);background:#f1f5f9;border:1px solid #e2e8f0;padding:5px 10px;border-radius:999px;white-space:nowrap}',
      '.shellRight{display:flex;align-items:center;gap:10px;flex-wrap:wrap}',
      '.shellBadge{font-size:12px;color:var(--muted,#6b1024);background:#f1f5f9;border:1px solid #e2e8f0;padding:5px 10px;border-radius:999px;white-space:nowrap}',
      '.shellStatus{font-size:12px;display:flex;align-items:center;gap:8px;color:var(--muted,#6b1024)}',
      '.shellDot{width:10px;height:10px;border-radius:999px;background:#cbd5f5;box-shadow:0 0 0 3px #eef2ff}',
      '.shellDot.online{background:var(--green,#22c55e)}',
      '.shellNav{margin:12px 0;display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start}',
      '.shellGroup{display:flex;gap:8px;flex-wrap:wrap;align-items:center;background:rgba(255,255,255,.7);border:1px solid var(--border,#e5e7eb);border-radius:999px;padding:6px 8px}',
      '.shellGroupLabel{font-size:12px;color:var(--muted,#6b1024);font-weight:800;padding:0 6px;white-space:nowrap}',
      '.shellNav a{display:inline-block;padding:8px 10px;border-radius:999px;background:#fff;border:1px solid var(--border,#e5e7eb);text-decoration:none;color:#334155;font-weight:700;font-size:13px}',
      '.shellNav a.active{background:#eef2ff;border-color:#c7d2fe;color:#4338ca}',
      '@media (max-width:640px){.shellGroup{width:100%;justify-content:space-between}.shellNav a{font-size:12px;padding:7px 10px}}'
    ].join('')
    document.head.appendChild(style)
  }

  function pathOf(href){
    try{
      var u = new URL(href, window.location.origin)
      return u.pathname
    }catch(e){
      return href
    }
  }

  function normalizePath(p){
    var s = (p || '').trim()
    if (!s) return '/'
    if (s === '/') return '/index.html'
    return s
  }

  function buildShell(opts){
    ensureStyle()
    var mount = document.getElementById('shell')
    if (!mount) return

    var title = (opts && opts.title) ? String(opts.title) : ''
    var badge = (opts && opts.badge) ? String(opts.badge) : ''
    var showStatus = !!(opts && opts.showStatus)

    var header = document.createElement('header')
    header.className = 'shellHeader'

    var left = document.createElement('div')
    left.className = 'shellLeft'
    var brand = document.createElement('div')
    brand.className = 'shellBrand'
    brand.innerHTML = '<span>🍈</span><span>小冬瓜智能助手</span>'
    left.appendChild(brand)
    if (title){
      var t = document.createElement('div')
      t.className = 'shellTitle'
      t.textContent = title
      left.appendChild(t)
    }
    header.appendChild(left)

    var right = document.createElement('div')
    right.className = 'shellRight'
    if (badge){
      var b = document.createElement('div')
      b.className = 'shellBadge'
      b.textContent = badge
      right.appendChild(b)
    }
    if (showStatus){
      var st = document.createElement('div')
      st.className = 'shellStatus'
      st.innerHTML = '<span id="statusDot" class="shellDot"></span><span id="statusText">离线</span>'
      right.appendChild(st)
    }
    header.appendChild(right)

    var nav = document.createElement('nav')
    nav.className = 'shellNav'

    var groups = [
      {label:'工作台', items:[{href:'/index.html', text:'对话'},{href:'/logs.html', text:'日志'}]},
      {label:'能力中心', items:[{href:'/skills.html', text:'技能'},{href:'/templates.html', text:'模板'}]},
      {label:'设置', items:[{href:'/config.html', text:'配置'},{href:'/cookies.html', text:'Cookie'}]},
      {label:'数据', items:[{href:'/memories.html', text:'记忆'}]}
    ]

    var current = normalizePath(window.location.pathname)
    groups.forEach(function(g){
      var group = document.createElement('div')
      group.className = 'shellGroup'
      var gl = document.createElement('div')
      gl.className = 'shellGroupLabel'
      gl.textContent = g.label
      group.appendChild(gl)
      g.items.forEach(function(it){
        var a = document.createElement('a')
        a.href = it.href
        a.textContent = it.text
        if (normalizePath(pathOf(it.href)) === current) a.className = 'active'
        group.appendChild(a)
      })
      nav.appendChild(group)
    })

    mount.textContent = ''
    mount.appendChild(header)
    mount.appendChild(nav)
  }

  window.renderShell = buildShell
  
  // 上下文监控和压缩功能
  // 注意：这些函数依赖于 index.html 中定义的 el() 和 state
  // 所以需要在 index.html 加载后才能调用
  window.updateContextUsage = function() {
    var el = window.el || function(id){return document.getElementById(id)}
    var state = window.state || {sessionHistory:[],modelCurrent:'doubao',modelOptions:[],isSending:false,isRunning:false}
    
    var contextUsed = el('contextUsed')
    var contextTotal = el('contextTotal')
    var contextRemaining = el('contextRemaining')
    var contextUsageBar = el('contextUsageBar')
    var contextUsageText = el('contextUsageText')
    var compressBtn = el('compressContextBtn')
    
    if (!contextUsed || !contextTotal || !contextUsageBar) return
    
    // 获取当前模型的上下文窗口
    var modelOptions = state.modelOptions || []
    var currentModel = state.modelCurrent || 'doubao'
    var maxTokens = 0
    
    modelOptions.forEach(function(m) {
      if (m.id === currentModel || m.name === currentModel) {
        maxTokens = m.contextWindow || m.maxTokens || 100000
      }
    })
    
    if (maxTokens === 0) {
      if (contextUsageText) contextUsageText.textContent = '未知'
      contextUsageBar.style.width = '0%'
      if (compressBtn) compressBtn.disabled = true
      return
    }
    
    // 估算当前上下文使用量（基于历史记录）
    var estimatedTokens = 0
    if (state.sessionHistory && state.sessionHistory.length > 0) {
      // 简单估算：每个字符约4个token
      var historyText = JSON.stringify(state.sessionHistory)
      estimatedTokens = Math.floor(historyText.length / 4)
    }
    
    // 确保 estimatedTokens 不超过 maxTokens
    if (estimatedTokens > maxTokens) {
      estimatedTokens = maxTokens - 1000
    }
    
    var remaining = maxTokens - estimatedTokens
    var usagePercent = (estimatedTokens / maxTokens) * 100
    
    // 更新显示
    if (contextUsed) contextUsed.textContent = estimatedTokens.toLocaleString()
    if (contextTotal) contextTotal.textContent = maxTokens.toLocaleString()
    if (contextRemaining) contextRemaining.textContent = remaining.toLocaleString()
    if (contextUsageText) contextUsageText.textContent = usagePercent.toFixed(1) + '%'
    contextUsageBar.style.width = usagePercent + '%'
    
    // 设置颜色
    if (usagePercent >= 95) {
      contextUsageBar.style.background = 'linear-gradient(90deg, #ef4444 0%, #dc2626 100%)'
    } else if (usagePercent >= 85) {
      contextUsageBar.style.background = 'linear-gradient(90deg, #f97316 0%, #ea580c 100%)'
    } else if (usagePercent >= 70) {
      contextUsageBar.style.background = 'linear-gradient(90deg, #eab308 0%, #ca8a04 100%)'
    } else {
      contextUsageBar.style.background = 'linear-gradient(90deg, var(--primary) 0%, var(--primary2) 100%)'
    }
    
    if (compressBtn) compressBtn.disabled = false
    
    // 自动压缩（超过85%）
    if (usagePercent >= 85 && !state.isSending && !state.isRunning) {
      setTimeout(function() {
        if (typeof compressContext === 'function') {
          if (confirm('上下文使用率已达 ' + usagePercent.toFixed(1) + '%，是否自动压缩上下文以节省token？')) {
            compressContext()
          }
        }
      }, 1000)
    }
  }
  
  window.compressContext = function() {
    var el = window.el || function(id){return document.getElementById(id)}
    var state = window.state || {isSending:false,isRunning:false}
    
    var compressBtn = el('compressContextBtn')
    var originalText = compressBtn ? compressBtn.textContent : '压缩上下文'
    
    if (compressBtn) {
      compressBtn.textContent = '压缩中...'
      compressBtn.disabled = true
    }
    
    fetch('/api/chat/compact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    }).then(function(res) {
      if (res.ok) {
        alert('上下文已压缩！')
        // 刷新历史记录
        if (typeof loadHistory === 'function') loadHistory()
        if (typeof updateContextUsage === 'function') updateContextUsage()
      } else {
        alert('压缩失败：' + res.status)
      }
    }).catch(function(e) {
      alert('压缩出错：' + e.message)
    }).finally(function() {
      if (compressBtn) {
        compressBtn.textContent = originalText
        compressBtn.disabled = false
      }
    })
  }
})()

