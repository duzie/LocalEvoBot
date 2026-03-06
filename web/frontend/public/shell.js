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
})()

