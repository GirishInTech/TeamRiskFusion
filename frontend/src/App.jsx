import React, { useEffect, useState } from 'react'

const api = (p, opts) => fetch(p, opts).then(r => {
  if (!r.ok) throw new Error('API ' + r.status)
  return r.json()
})

const KIND_ICON = { definition: '📖', caveat: '⚠️', howto: '🛠️', process: '📋', note: '📝' }
const SRC_ICON = { kt_transcript: '🎤', jira: '🎫', repo: '📦', manual: '✍️', requirement: '📋', document: '📄' }
const COMP_ICON = { api: '🔌', database: '🗄️', repo: '📦', dashboard: '📊', widget: '🧩', computation: '🧮', report: '📄', doc: '📝', other: '🔧' }

function FreshBadge({ stale }) {
  return stale ? <span className="badge stale">⚠ STALE</span> : <span className="badge fresh">FRESH</span>
}
function KindBadge({ k }) {
  return <span className="badge kind">{KIND_ICON[k] || ''} {k}</span>
}
function StatusPill({ s }) {
  return <span className={`badge pill-${s}`}>{s}</span>
}
function initials(name) {
  return (name || '?').split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase()
}

/* ---------- Chat: AI grounded in repo, retrieval fallback ---------- */
function ChatBox({ go, topicId, projectId, roomy }) {
  const scopeNote = projectId ? ' (this project)' : topicId ? ' (this topic)' : ''
  const [msgs, setMsgs] = useState([{ from: 'bot', text: `Hi — ask me about a metric, an owner, an endpoint, or what’s stale. I answer from your repo${scopeNote}.` }])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const send = async () => {
    const text = input.trim()
    if (!text || busy) return
    const history = [...msgs.slice(-6).map(m => ({ role: m.from === 'user' ? 'user' : 'assistant', content: m.text }))].slice(-6)
    setMsgs(m => [...m, { from: 'user', text }])
    setInput(''); setBusy(true)
    try {
      const r = await api('/chat/ai', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, topic_id: topicId || null, project_id: projectId || null, history }) })
      setMsgs(m => [...m, { from: 'bot', text: r.answer, mode: r.mode,
        entries: r.entries || [], projects: r.projects || [], components: r.components || [] }])
    } catch (err) {
      const m = String((err && err.message) || '')
      setMsgs(msgs => [...msgs, { from: 'bot', mode: 'error', text:
        m.includes('404')
          ? 'Chat service not found — restart the backend (uvicorn app:app --port 8000) and refresh.'
          : 'Offline hiccup — try again.' }])
    }
    finally { setBusy(false) }
  }
  return (
    <div className={roomy ? 'chatroomy' : ''}>
      <div className="chatmsgs">
        {msgs.map((m, i) => (
          <div key={i} className={m.from === 'user' ? 'bubble-user' : 'bubble-bot'}>
            {m.from === 'bot' && m.mode && m.mode !== 'greeting' && m.mode !== 'error' && (
              <div className="meta" style={{ marginBottom: 4 }}>
                {m.mode === 'ai' ? '✦ AI · repo-grounded'
                  : m.mode === 'throttled' ? '⏳ model busy — offline quotes for now'
                  : m.mode === 'no-key' ? '⚠ AI key missing — offline quotes'
                  : 'offline answers · quoted'}
              </div>
            )}
            <div style={{ fontSize: 14 }}>{m.text}</div>
                {(m.entries || []).map(e => (
                  <div key={'e' + e.id} className="chathit" onClick={() => go({ name: 'entry', id: e.id })}>
                    {e.stale ? '⚠' : '📖'} {e.title}
                  </div>
                ))}
                {(m.projects || []).map(p => (
                  <div key={'p' + p.id} className="chathit" onClick={() => go({ name: 'project', id: p.id })}>
                    📦 {p.name} <span className="meta">· {p.owner_name}</span>
                  </div>
                ))}
                {(m.components || []).map((c, j) => (
                  <div key={'c' + j} className="chathit" onClick={() => go({ name: 'project', id: c.project_id })}>
                    🔌 <code className="mono">{c.ref || c.label}</code> <span className="meta">· {c.project_name}</span>
                  </div>
                ))}
          </div>
        ))}
        {busy && <div className="bubble-bot"><span className="meta">Searching the repo…</span></div>}
          </div>
          <div className="chatinput">
            <input value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') send() }} placeholder="Ask about a metric, owner, endpoint…" />
            <button className="primary" onClick={send} disabled={busy || !input.trim()}>Ask</button>
          </div>
      </div>
  )
}

function ChatDock({ go, topicId, projectId }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button className="chatfab" onClick={() => setOpen(o => !o)} title="Ask the repo">💬</button>
      {open && (
        <div className="chatpanel">
          <div className="chathead"><b>Ask the repo</b><span className="meta">{projectId ? 'this project' : topicId ? 'this topic' : 'whole repo'}</span></div>
          <ChatBox go={go} topicId={topicId} projectId={projectId} />
        </div>
      )}
    </>
  )
}

function ChatView({ go }) {
  return (
    <>
      <h1 className="pagetitle">Chat — ask the repo</h1>
      <p className="meta">AI answers grounded in your entries, projects and components — or honest offline quotes when the model is unreachable.</p>
      <div className="panel">
        <ChatBox go={go} roomy />
      </div>
    </>
  )
}

function DocSection({ projectId, entryId }) {
  const [docs, setDocs] = useState([])
  const [file, setFile] = useState(null)
  const [by, setBy] = useState('')
  const [inputKey, setInputKey] = useState(0)
  const [err, setErr] = useState('')
  const load = () => {
    const qs = projectId ? `project_id=${projectId}` : `entry_id=${entryId}`
    api(`/documents?${qs}`).then(setDocs).catch(() => setDocs([]))
  }
  useEffect(load, [projectId, entryId])
  const upload = async () => {
    if (!file) return
    setErr('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      if (projectId) fd.append('project_id', String(projectId))
      if (entryId) fd.append('entry_id', String(entryId))
      if (by) fd.append('uploaded_by', by)
      const r = await fetch('/documents/upload', { method: 'POST', body: fd })
      if (!r.ok) throw new Error('upload failed')
      setFile(null); setInputKey(k => k + 1); load()
    } catch (e) { setErr(e.message) }
  }
  return (
    <div>
      {docs.length === 0 && <div className="empty">No documents yet — attach the spec or mapping sheet so it doesn’t live on someone’s laptop.</div>}
      {docs.map(d => (
        <div key={d.id} className="docrow">
          <span>{d.filename.startsWith('REQ-') ? '📋' : '📎'}</span>
          <code className="mono">{d.filename}</code>
          <span className="meta">{Math.max(1, Math.round(d.size_bytes / 1024))} KB{d.uploaded_by ? ` · by ${d.uploaded_by}` : ''}</span>
          <a className="doclink" href={d.url} download>Download</a>
        </div>
      ))}
      <div className="row2" style={{ marginTop: 10 }}>
        <input key={inputKey} type="file" onChange={e => setFile(e.target.files[0] || null)} />
        <input placeholder="your name (optional)" value={by} onChange={e => setBy(e.target.value)} />
      </div>
      {file && <div className="docrow"><span>📎</span><code className="mono">{file.name}</code><span className="meta">{Math.max(1, Math.round(file.size / 1024))} KB · ready to upload</span><button className="ghost" onClick={() => { setFile(null); setInputKey(k => k + 1) }}>Cancel</button></div>}
      <div><button className="primary" onClick={upload} disabled={!file}>Attach document</button> <span className="meta">{err}</span></div>
    </div>
  )
}

function viewFromHash() {
  const parts = (window.location.hash.replace(/^#/, '') || '/').split('/').filter(Boolean)
  const nid = Number(parts[1])
  if (parts[0] === 'topic' && nid) return { name: 'topic', id: nid }
  if (parts[0] === 'entry' && nid) return { name: 'entry', id: nid }
  if (parts[0] === 'projects') return { name: 'projects' }
  if (parts[0] === 'project' && nid) return { name: 'project', id: nid }
  if (parts[0] === 'capture') return { name: 'capture' }
  if (parts[0] === 'chat') return { name: 'chat' }
  return { name: 'topics' }
}
function hashFor(v) {
  if (v.name === 'topic') return `#/topic/${v.id}`
  if (v.name === 'entry') return `#/entry/${v.id}`
  if (v.name === 'projects') return '#/projects'
  if (v.name === 'project') return `#/project/${v.id}`
  if (v.name === 'capture') return '#/capture'
  if (v.name === 'chat') return '#/chat'
  return '#/'
}

function Crumb({ go, trail }) {
  return (
    <nav className="crumb" aria-label="Breadcrumb">
      <ol>
        {trail.map((t, i) => (
          <li key={i}>
            {i === trail.length - 1
              ? <span className="crumb-current" aria-current="page" title={t.label}>{t.label}</span>
              : <a className="crumb-link" onClick={() => go(t.view)} title={t.label}>{t.label}</a>}
          </li>
        ))}
      </ol>
    </nav>
  )
}

export default function App() {
  const [view, setView] = useState(viewFromHash)
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem('trf-theme') || 'dark' } catch { return 'dark' }
  })
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem('trf-theme', theme) } catch { /* private mode: stay session-only */ }
  }, [theme])
  useEffect(() => {
    const onHash = () => setView(viewFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  const go = (v) => {
    const h = hashFor(v)
    if (window.location.hash === h) setView(viewFromHash())
    else window.location.hash = h
  }
  const analystActive = view.name === 'topics' || view.name === 'topic' || view.name === 'entry'
  return (
    <>
      <header className="topbar">
        <span className="brand" style={{ cursor: 'pointer' }} title="Go to home" onClick={() => go({ name: 'topics' })}>TeamRiskFusion</span>
        <span className="tagline">Answers that outlive their authors.</span>
        <button className="navbtn" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} title="Toggle light / dark mode">{theme === 'dark' ? '☀ Light' : '🌙 Dark'}</button>
      </header>
      <div className="demo-bar">Demo: analyst pain → knowledge page → Likhitha discovers → paste KT → continuity. “Wikis wait for people to write. Ours extracts.”</div>
      <div className="shell">
      <nav className="sidenav" aria-label="Primary">
        <button className={'sidebtn' + (analystActive ? ' active' : '')} onClick={() => go({ name: 'topics' })}>
          <span className="step">1</span>
          <span><span className="sidetitle">Analyst</span><span className="sidehint">Find answers, no tickets</span></span>
        </button>
        <button className={'sidebtn' + (view.name.startsWith('project') ? ' active' : '')} onClick={() => go({ name: 'projects' })}>
          <span className="step">2</span>
          <span><span className="sidetitle">Dev Projects</span><span className="sidehint">Find code, data & owners</span></span>
        </button>
        <button className={'sidebtn' + (view.name === 'capture' ? ' active' : '')} onClick={() => go({ name: 'capture' })}>
          <span className="step">3</span>
          <span><span className="sidetitle">Knowledge Feed</span><span className="sidehint">Log it in seconds</span></span>
        </button>
        <button className={'sidebtn' + (view.name === 'chat' ? ' active' : '')} onClick={() => go({ name: 'chat' })}>
          <span className="step">✦</span>
          <span><span className="sidetitle">Chat</span><span className="sidehint">Ask the repo, AI grounded</span></span>
        </button>
      </nav>
      <div className="wrap">
        {view.name === 'topics' && <Topics go={go} />}
        {view.name === 'topic' && <TopicView id={view.id} go={go} />}
        {view.name === 'entry' && <EntryView id={view.id} go={go} />}
        {view.name === 'projects' && <Projects go={go} />}
        {view.name === 'project' && <ProjectView id={view.id} go={go} />}
        {view.name === 'capture' && <Capture go={go} />}
        {view.name === 'chat' && <ChatView go={go} />}
      </div>
      </div>
      <ChatDock go={go}
        topicId={view.name === 'topic' ? view.id : null}
        projectId={view.name === 'project' ? view.id : null} />
    </>
  )
}

/* ---------- Analyst home ---------- */
function Topics({ go }) {
  const [topics, setTopics] = useState([])
  const [stats, setStats] = useState({})
  const [index, setIndex] = useState([])
  const [q, setQ] = useState('')
  useEffect(() => {
    api('/topics').then(async ts => {
      setTopics(ts)
      const s = {}
      const idx = []
      for (const t of ts) {
        try {
          const d = await api(`/topics/${t.id}`)
          const stale = d.entries.filter(e => e.stale).length
          s[t.id] = { entries: d.entries.length, projects: d.projects.length, stale,
            dot: stale > 0 ? 'dot-amber' : 'dot-green' }
          const subNames = {}
          d.subtopics.forEach(x => { subNames[x.id] = x.name })
          d.entries.forEach(e => idx.push({ ...e, topic: t.name, topicId: t.id, sub: subNames[e.subtopic_id] || '' }))
        } catch { s[t.id] = { entries: 0, projects: 0, stale: 0, dot: 'dot-green' } }
      }
      setStats(s)
      setIndex(idx)
    }).catch(() => setTopics([]))
  }, [])
  const query = q.trim().toLowerCase()
  const results = query
    ? index.filter(e => `${e.title} ${e.body} ${e.author}`.toLowerCase().includes(query)).slice(0, 30)
    : []
  return (
    <>
      <h1 className="pagetitle">Analyst home — pick a topic, get an answer. No ticket.</h1>
      <div className="row2" style={{ gridTemplateColumns: '1fr auto', alignItems: 'center' }}>
        <input placeholder="Search answers: e.g. CVaR, March spike, cut-off…" value={q} onChange={e => setQ(e.target.value)} />
        {query && <button className="ghost" onClick={() => setQ('')}>Clear</button>}
      </div>
      {query && (
        <>
          <h2 className="section">{results.length} result{results.length === 1 ? '' : 's'} for “{q.trim()}”</h2>
          {results.length === 0 && <div className="empty">Nothing matches — try fewer words, or ask in Knowledge Feed.</div>}
          {results.map(e => (
            <div key={e.id} className="entryrow" onClick={() => go({ name: 'entry', id: e.id })}>
              <span style={{ fontSize: 15, fontWeight: 700 }}>{e.title}</span>
              <KindBadge k={e.entry_kind} />
              <FreshBadge stale={e.stale} />
              <span className="meta">{e.topic}{e.sub ? ` › ${e.sub}` : ''} · by {e.author}</span>
            </div>
          ))}
        </>
      )}
      {!query && (
      <>
      {topics.length === 0 && <div className="empty">No topics yet — paste a KT transcript in Knowledge Feed to create the first one.</div>}
      <div className="cards3">
        {topics.map(t => (
          <div key={t.id} className="card" onClick={() => go({ name: 'topic', id: t.id })}>
            <div className="card-title">{t.name}<span className={`dot ${(stats[t.id] || {}).dot || 'dot-green'}`} /></div>
            <div className="meta">{t.subtopic_count} subtopics · {(stats[t.id] || {}).entries ?? '…'} entries · {(stats[t.id] || {}).projects ?? '…'} projects</div>
            <p style={{ fontSize: 15 }}>{t.description}</p>
          </div>
        ))}
      </div>
      <div className="panel"><b>Before:</b> month-end, a number looks off, dashboard author left — file a ticket and wait. <b>After:</b> open a topic above.</div>
      </>
      )}
    </>
  )
}

/* ---------- Health + continuity ---------- */
function HealthPanel({ topicId }) {
  const [h, setH] = useState(null)
  useEffect(() => { api(`/health/${topicId}`).then(setH).catch(() => {}) }, [topicId])
  if (!h) return null
  return (
    <div>
      <h2 className="section">Knowledge health</h2>
      <div className="tiles">
        <div className="tile"><b>{h.contributor_count}</b><span className="meta">Contributors<br />{h.contributors.join(', ') || '—'}</span></div>
        <div className="tile"><b>{h.fresh_pct}%</b><span className="meta">Fresh<br />of {h.total_entries} entries</span></div>
        <div className="tile"><b>{h.stalest_entries.length}</b><span className="meta">Stale entries</span></div>
      </div>
      {h.single_owner && <div className="warnbanner">Single-owner warning: only {h.contributors[0] || 'one person'} knows this topic — bus-factor risk.</div>}
      {h.stalest_entries.length > 0 ? (
        h.stalest_entries.map(e => <div key={e.id} className="entryrow"><span className="badge stale">⚠ STALE</span><span style={{ fontSize: 15 }}>{e.title}</span></div>)
      ) : <div className="meta" style={{ marginTop: 8 }}>No stale entries — everything verified after its sources.</div>}
    </div>
  )
}

function ContinuityCard({ projectId }) {
  const [p, setP] = useState(null)
  useEffect(() => { api(`/projects/${projectId}`).then(setP).catch(() => {}) }, [projectId])
  if (!p) return null
  const builtBy = (p.people.find(x => x.role === 'owner') || {}).person_name || p.owner_name
  const extend = (p.attributes.find(a => a.key === 'how_to_extend') || {}).value || 'contact owner for review'
  return (
    <div className="panel">
      <div style={{ fontSize: 15 }}>Built by <b>{builtBy}</b> · Made of <b>{p.components.length} components</b> · Owned now by <b>{p.owner_name}</b> · Extend via <b>{extend}</b></div>
    </div>
  )
}

/* ---------- Topic page: subtopics as sections ---------- */
function TopicView({ id, go }) {
  const [t, setT] = useState(null)
  const [fq, setFq] = useState('')
  useEffect(() => { api(`/topics/${id}`).then(setT).catch(() => {}) }, [id])
  if (!t) return <div>Loading…</div>
  const fquery = fq.trim().toLowerCase()
  const matches = e => !fquery || `${e.title} ${e.body} ${e.author}`.toLowerCase().includes(fquery)
  const visibleSubs = t.subtopics.filter(s => t.entries.some(e => e.subtopic_id === s.id && matches(e)))
  return (
    <>
      <Crumb go={go} trail={[{ label: 'Topics', view: { name: 'topics' } }, { label: t.name }]} />
      <h1 className="pagetitle">{t.name}</h1>
      <p style={{ fontSize: 15 }}>{t.description}</p>
      <HealthPanel topicId={id} />
      <div className="row2" style={{ gridTemplateColumns: '1fr auto', alignItems: 'center' }}>
        <input placeholder="Filter in this topic: e.g. refresh, caveat, EEPE…" value={fq} onChange={e => setFq(e.target.value)} />
        {fquery && <button className="ghost" onClick={() => setFq('')}>Clear</button>}
      </div>
      {fquery && visibleSubs.length === 0 && <div className="empty">No entries match “{fq.trim()}” in this topic — clear the filter.</div>}
      <div className="cols">
      <div>
      {(fquery ? visibleSubs : t.subtopics).map(s => {
        const entries = t.entries.filter(e => e.subtopic_id === s.id && matches(e))
        return (
          <div key={s.id}>
            <h2 className="section">{s.name}</h2>
            {entries.length === 0 && !fquery && <div className="empty">No entries yet — paste a KT transcript in Knowledge Feed to create the first one.</div>}
            {entries.map(e => (
              <div key={e.id} className="entryrow" onClick={() => go({ name: 'entry', id: e.id })}>
                <span style={{ fontSize: 15, fontWeight: 700 }}>{e.title}</span>
                <KindBadge k={e.entry_kind} />
                <FreshBadge stale={e.stale} />
                <span className="meta">by {e.author}</span>
              </div>
            ))}
          </div>
        )
      })}
      </div>
      <aside className="side">
      <h2 className="section">Projects in this topic</h2>
      {t.projects.length === 0 && <div className="empty">No projects yet — log one in Knowledge Feed (5 fields).</div>}
      {t.projects.map(p => (
        <div key={p.id} className="card" onClick={() => go({ name: 'project', id: p.id })}>
          <div className="card-title">{p.name}</div>
          <StatusPill s={p.status} />
          <div className="meta">owner: {p.owner_name}</div>
          <p style={{ fontSize: 15 }}>{p.summary}</p>
        </div>
      ))}
      {t.projects.map(p => <ContinuityCard key={'c' + p.id} projectId={p.id} />)}
      </aside>
      </div>
    </>
  )
}

/* ---------- Entry page ---------- */
function EntryView({ id, go }) {
  const [e, setE] = useState(null)
  const [crumb, setCrumb] = useState({ topic: '', topicId: null, sub: '' })
  const [team, setTeam] = useState([])
  const [tick, setTick] = useState(0)
  const [verifying, setVerifying] = useState(false)
  useEffect(() => {
    api(`/entries/${id}`).then(async entry => {
      setE(entry)
      try {
        const ts = await api('/topics')
        for (const t of ts) {
          const d = await api(`/topics/${t.id}`)
          const s = d.subtopics.find(x => x.id === entry.subtopic_id)
          if (s) { setCrumb({ topic: t.name, topicId: t.id, sub: s.name }); break }
        }
      } catch { /* offline-safe: keep breadcrumb empty */ }
    }).catch(() => {})
  }, [id, tick])
  const projId = e && e.project ? e.project.id : null
  useEffect(() => {
    if (projId) api(`/projects/${projId}`).then(p => setTeam((p.people || []).map(x => x.person_name))).catch(() => setTeam([]))
    else setTeam([])
  }, [projId])
  if (!e) return <div>Loading…</div>
  const contributors = [...new Set([e.author, ...team].filter(Boolean))]
  return (
    <>
      <Crumb go={go} trail={[
        { label: 'Topics', view: { name: 'topics' } },
        ...(crumb.topicId ? [{ label: crumb.topic, view: { name: 'topic', id: crumb.topicId } }] : []),
        ...(crumb.sub ? [{ label: crumb.sub }] : []),
        { label: e.title },
      ]} />
      <h1 className="pagetitle">{e.title}</h1>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginBottom: 8, alignItems: 'center' }}>
        <KindBadge k={e.entry_kind} /><FreshBadge stale={e.stale} />
        {e.stale && (
          <button className="primary" disabled={verifying} onClick={async () => {
            setVerifying(true)
            try { await api(`/entries/${e.id}/verify`, { method: 'PATCH' }); setTick(t => t + 1) }
            finally { setVerifying(false) }
          }}>{verifying ? 'Verifying…' : '✓ Mark verified'}</button>
        )}
      </div>
      {e.project && (
        <div className="glance">
          <b>At a glance</b>
          <div><b>What it means:</b> {e.project.summary}</div>
          <div><b>Caveats:</b> check caveat entries on the <a style={{ color: '#4F46E5', cursor: 'pointer' }} onClick={() => go({ name: 'project', id: e.project.id })}>project page</a></div>
          <div><b>Refresh:</b> Daily 06:30 CET · cut-off 19:00 CET</div>
          <div><b>Owner:</b> {e.project.owner_name} ({e.project.status})</div>
          <div><b>How to request a change:</b> DAF ‘metric-change’, tag owner — 3-day SLA.</div>
        </div>
      )}
      <div className="cols">
      <div>
      <pre className="body">{e.body}</pre>
      </div>
      <aside className="side">
      <h2 className="section">Contributors</h2>
      <div className="avatars">{contributors.map(c => <span key={c} title={c}><span className="avatar">{initials(c)}</span> <span className="meta">{c}</span></span>)}<span className="meta">verified {e.verified_at?.slice(0, 10)}</span></div>
      <h2 className="section">Sources</h2>
      {(e.sources || []).length === 0 && <div className="empty">No sources linked.</div>}
      {(e.sources || []).map(s => (
        <div key={s.id} className="srctag" style={{ margin: '6px 0' }}>
          {SRC_ICON[s.source_type] || '•'} {s.source_type} · <code className="mono">{s.source_ref}</code> · <span className="meta">updated {s.source_updated_at?.slice(0, 10)}</span>
        </div>
      ))}
      <h2 className="section">Documents</h2>
      <DocSection entryId={e.id} />
      </aside>
      </div>
      {e.stale && <div className="warnbanner">⚠ STALE: a source updated after this entry was verified.</div>}
    </>
  )
}

/* ---------- Dev discovery ---------- */
function Projects({ go }) {
  const [list, setList] = useState([])
  const [topics, setTopics] = useState([])
  const [topicId, setTopicId] = useState('')
  const [q, setQ] = useState('')
  const [counts, setCounts] = useState({})
  useEffect(() => { api('/topics').then(setTopics).catch(() => {}) }, [])
  useEffect(() => {
    api(topicId ? `/projects?topic_id=${topicId}` : '/projects').then(async ps => {
      setList(ps)
      const c = {}
      await Promise.all(ps.map(async p => {
        try { const d = await api(`/projects/${p.id}`); c[p.id] = d.components.length }
        catch { c[p.id] = 0 }
      }))
      setCounts(c)
    }).catch(() => setList([]))
  }, [topicId])
  const filtered = list.filter(p => !q || (p.name + p.summary).toLowerCase().includes(q.toLowerCase()))
  return (
    <>
      <h1 className="pagetitle">Dev discovery — “I want to build X, what already exists?”</h1>
      <div className="chips">
        <span className={'chip' + (!topicId ? ' active' : '')} onClick={() => setTopicId('')}>All</span>
        {topics.map(t => <span key={t.id} className={'chip' + (String(topicId) === String(t.id) ? ' active' : '')} onClick={() => setTopicId(String(t.id))}>{t.name}</span>)}
      </div>
      <input placeholder="Filter: e.g. limit, exposure, RWA…" value={q} onChange={e => setQ(e.target.value)} />
      {filtered.length === 0 && <div className="empty">No projects match — log one in Knowledge Feed (5 fields).</div>}
      <div className="cards3">
        {filtered.map(p => (
          <div key={p.id} className="card" onClick={() => go({ name: 'project', id: p.id })}>
            <div className="card-title">{p.name}</div>
            <StatusPill s={p.status} />
            <div className="meta">owner: {p.owner_name} · {counts[p.id] ?? '…'} components</div>
            <p style={{ fontSize: 15 }}>{p.summary}</p>
          </div>
        ))}
      </div>
      <div className="panel">Likhitha flow: search topic → find project → see databases, API endpoints, repos, owner. “Where do I get the data?” in 2 minutes.</div>
    </>
  )
}

/* ---------- Add-to-project forms (living project page) ---------- */
function KTAttach({ project, onAdded }) {
  const [text, setText] = useState('')
  const [drafts, setDrafts] = useState(null)
  const [done, setDone] = useState('')
  const [busy, setBusy] = useState(false)
  const preview = async () => {
    if (!text.trim()) return
    setBusy(true); setDone('')
    try {
      const r = await api('/ingest/transcript', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) })
      setDrafts(r.draft_entries.map(en => ({ title: en.title, body: en.body, kind: en.entry_kind, speaker: en.suggested_speaker || '' })))
    } finally { setBusy(false) }
  }
  const approve = async () => {
    setBusy(true)
    try {
      for (const en of drafts) {
        await api(`/projects/${project.id}/entries`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: en.title, body: en.body, entry_kind: en.kind, author: en.speaker, source_type: 'kt_transcript', source_ref: 'kt-paste' }) })
      }
      setDone(`Attached ${drafts.length} entr${drafts.length === 1 ? 'y' : 'ies'} to ${project.name}.`)
      setDrafts(null); setText(''); onAdded()
    } finally { setBusy(false) }
  }
  return (
    <div>
      <p className="meta">Same deterministic parsing as Knowledge Feed — but entries link here, no new project. One click to approve.</p>
      <textarea rows={4} value={text} onChange={e => setText(e.target.value)} placeholder="Paste the KT session about this project…" />
      <div><button className="primary" onClick={preview} disabled={busy || !text.trim()}>{busy ? 'Working…' : 'Generate drafts'}</button></div>
      {drafts && (
        <>
          <h3 className="sub">Draft entries ({drafts.length}) → {project.name}</h3>
          {drafts.map((en, i) => (
            <div key={i} className="panel">
              <input value={en.title} onChange={e => setDrafts(drafts.map((x, j) => j === i ? { ...x, title: e.target.value } : x))} />
              <textarea rows={2} value={en.body} onChange={e => setDrafts(drafts.map((x, j) => j === i ? { ...x, body: e.target.value } : x))} />
              <select value={en.kind} onChange={e => setDrafts(drafts.map((x, j) => j === i ? { ...x, kind: e.target.value } : x))}>
                <option value="definition">definition</option><option value="caveat">caveat</option><option value="howto">howto</option><option value="process">process</option><option value="note">note</option>
              </select>
              <span className="meta">from {en.speaker || 'transcript'}</span>
            </div>
          ))}
          <div><button className="primary" onClick={approve} disabled={busy}>{busy ? 'Attaching…' : `Approve ${drafts.length} → ${project.name}`}</button></div>
        </>
      )}
      {done && <div className="meta" style={{ marginTop: 8 }}>{done} See Linked knowledge above.</div>}
    </div>
  )
}

function NoteForm({ project, onAdded }) {
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [kind, setKind] = useState('note')
  const submit = async () => {
    if (!title.trim()) return
    await api(`/projects/${project.id}/entries`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, body, entry_kind: kind }) })
    setTitle(''); setBody(''); setKind('note'); onAdded()
  }
  return (
    <div>
      <input placeholder="Note title*" value={title} onChange={e => setTitle(e.target.value)} />
      <textarea rows={3} placeholder="What should the next person know?" value={body} onChange={e => setBody(e.target.value)} />
      <div className="row2" style={{ gridTemplateColumns: '1fr auto', alignItems: 'center' }}>
        <select value={kind} onChange={e => setKind(e.target.value)}>
          <option value="definition">definition</option><option value="caveat">caveat</option><option value="howto">howto</option><option value="process">process</option><option value="note">note</option>
        </select>
        <button className="primary" onClick={submit} disabled={!title.trim()}>Add note</button>
      </div>
    </div>
  )
}

function CompForm({ project, onAdded }) {
  const [kind, setKind] = useState('repo')
  const [label, setLabel] = useState('')
  const [ref, setRef] = useState('')
  const submit = async () => {
    if (!label && !ref) return
    await api(`/projects/${project.id}/components`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind, label, ref }) })
    setLabel(''); setRef(''); onAdded()
  }
  return (
    <div className="row2" style={{ gridTemplateColumns: '140px 1fr 1fr auto', alignItems: 'center' }}>
      <select value={kind} onChange={e => setKind(e.target.value)}>
        <option>api</option><option>database</option><option>repo</option><option>dashboard</option><option>widget</option><option>computation</option><option>report</option><option>doc</option><option>other</option>
      </select>
      <input placeholder="label" value={label} onChange={e => setLabel(e.target.value)} />
      <input placeholder="ref / URL" value={ref} onChange={e => setRef(e.target.value)} />
      <button className="primary" onClick={submit} disabled={!label && !ref}>Add</button>
    </div>
  )
}

function AttrForm({ project, onAdded }) {
  const [key, setKey] = useState('')
  const [value, setValue] = useState('')
  const submit = async () => {
    if (!key.trim()) return
    await api(`/projects/${project.id}/attributes`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, value }) })
    setKey(''); setValue(''); onAdded()
  }
  return (
    <div className="row2" style={{ gridTemplateColumns: '1fr 1fr auto', alignItems: 'center' }}>
      <input placeholder="key (e.g. owner-oncall)" value={key} onChange={e => setKey(e.target.value)} />
      <input placeholder="value" value={value} onChange={e => setValue(e.target.value)} />
      <button className="primary" onClick={submit} disabled={!key.trim()}>Add</button>
    </div>
  )
}

function ProjectView({ id, go }) {
  const [p, setP] = useState(null)
  const [tick, setTick] = useState(0)
  const [verifyingId, setVerifyingId] = useState(null)
  const reload = () => setTick(t => t + 1)
  useEffect(() => { api(`/projects/${id}`).then(setP).catch(() => {}) }, [id, tick])
  const verifyEntry = async (ev, entryId) => {
    ev.stopPropagation()
    setVerifyingId(entryId)
    try { await api(`/entries/${entryId}/verify`, { method: 'PATCH' }); reload() }
    finally { setVerifyingId(null) }
  }
  if (!p) return <div>Loading…</div>
  const groups = {}
  p.components.forEach(c => { (groups[c.kind] = groups[c.kind] || []).push(c) })
  return (
    <>
      <Crumb go={go} trail={[{ label: 'Projects', view: { name: 'projects' } }, { label: p.name }]} />
      <h1 className="pagetitle">{p.name} <StatusPill s={p.status} /></h1>
      <div className="meta">Subtopic: {p.subtopic_name} · Owner: {p.owner_name}</div>
      <p style={{ fontSize: 15 }}>{p.summary}</p>
      <div className="cols">
      <div>
      <h2 className="section">Components — what it’s made of</h2>
      {p.components.length === 0 && <div className="empty">No components yet — attach a repo link in Knowledge Feed.</div>}
      <div className="tablewrap">
      <table className="grid"><thead><tr><th></th><th>Label</th><th>Ref</th><th>Notes</th></tr></thead>
        <tbody>{Object.keys(groups).sort().map(k => (
          <React.Fragment key={k}>
            <tr className="grouprow"><td colSpan={4}>{COMP_ICON[k] || ''} {k} ({groups[k].length})</td></tr>
            {groups[k].map(c => <tr key={c.id}><td>{COMP_ICON[c.kind] || ''}</td><td>{c.label}</td><td><code className="mono">{c.ref}</code></td><td>{c.notes}</td></tr>)}
          </React.Fragment>
        ))}</tbody>
      </table>
      </div>
      <h2 className="section">Linked knowledge</h2>
      {p.entries.length === 0 && <div className="empty">No linked entries yet — attach a KT transcript or add the first note below.</div>}
      {p.entries.map(e => (
        <div key={e.id} className="entryrow" onClick={() => go({ name: 'entry', id: e.id })}>
          <span style={{ fontSize: 15 }}>{e.title}</span><KindBadge k={e.entry_kind} /><FreshBadge stale={e.stale} />
          {e.stale && (
            <button className="ghost" style={{ marginLeft: 'auto' }} disabled={verifyingId === e.id}
              onClick={ev => verifyEntry(ev, e.id)}>
              {verifyingId === e.id ? 'Verifying…' : '✓ Verify'}
            </button>
          )}
        </div>
      ))}
      </div>
      <aside className="side">
      <h2 className="section">People</h2>
      <div className="avatars">{p.people.map((x, i) => <span key={i} title={`${x.person_name} (${x.role})`}><span className="avatar">{initials(x.person_name)}</span> <span className="meta">{x.person_name} ({x.role})</span></span>)}</div>
      <h2 className="section">Documents</h2>
      <DocSection projectId={p.id} />
      <h2 className="section">Business continuity</h2>
      <ContinuityCard projectId={p.id} />
      </aside>
      </div>
      <h2 className="section">Add to this project</h2>
      <details className="addbox" open>
        <summary>🎤 Attach a KT transcript to {p.name}</summary>
        <KTAttach project={p} onAdded={reload} />
      </details>
      <details className="addbox">
        <summary>📝 Add a note</summary>
        <NoteForm project={p} onAdded={reload} />
      </details>
      <details className="addbox">
        <summary>🔧 Add a component row</summary>
        <CompForm project={p} onAdded={reload} />
      </details>
      <details className="addbox">
        <summary>🏷️ Add a key-value attribute</summary>
        <AttrForm project={p} onAdded={reload} />
      </details>
      <h2 className="section">Downstream impact — what breaks if this changes</h2>
      {(p.lineage || []).length === 0 && <div className="empty">Nothing else reuses these pieces yet — this project is a leaf, not a root.</div>}
      {(p.lineage || []).length > 0 && (
      <div className="lineage">
      {(p.lineage || []).map(c => (
        <div key={c.id} className="panel">
          <div style={{ fontSize: 15 }}>{COMP_ICON[c.kind] || ''} <b>{c.label}</b> <code className="mono">{c.ref}</code></div>
          <div className="meta">also feeds: {c.used_by.map(u => `${u.name} (${u.status})`).join(' · ')}</div>
        </div>
      ))}
      </div>
      )}
      <h2 className="section">Related via shared pieces</h2>
      {(p.shared_related || []).length === 0 && <div className="empty">No shared computations, endpoints, databases or codebases — see same-subtopic projects below, if any.</div>}
      <div className="cards3">
        {(p.shared_related || []).map(r => (
          <div key={r.id} className="card" onClick={() => go({ name: 'project', id: r.id })}>
            <div className="card-title">{r.name}</div><StatusPill s={r.status} />
            <div className="meta">shares: {r.shared.map(s => `${s.kind} ${s.ref}`).join(' · ')}</div>
          </div>
        ))}
      </div>
      <h2 className="section">Related projects</h2>
      <div className="cards3">
        {p.related_projects.map(r => (
          <div key={r.id} className="card" onClick={() => go({ name: 'project', id: r.id })}><div className="card-title">{r.name}</div><StatusPill s={r.status} /></div>
        ))}
      </div>
    </>
  )
}

/* ---------- Capture ---------- */
function Capture({ go }) {
  const [tab, setTab] = useState('form')
  return (
    <>
      <h1 className="pagetitle">Knowledge Feed — logging is a byproduct, not homework</h1>
      <div className="tabs">
        <span className={'tab' + (tab === 'form' ? ' active' : '')} onClick={() => setTab('form')}>Log a project (5 fields)</span>
        <span className={'tab' + (tab === 'kt' ? ' active' : '')} onClick={() => setTab('kt')}>From KT transcript</span>
        <span className={'tab' + (tab === 'jira' ? ' active' : '')} onClick={() => setTab('jira')}>Import Jira ticket</span>
      </div>
      {tab === 'form' && <LogForm go={go} />}
      {tab === 'kt' && <KTForm go={go} />}
      {tab === 'jira' && <JiraForm go={go} />}
    </>
  )
}

function useSubtopics() {
  const [subs, setSubs] = useState([])
  useEffect(() => {
    api('/topics').then(async ts => {
      const all = []
      for (const t of ts) {
        try { const d = await api(`/topics/${t.id}`); d.subtopics.forEach(s => all.push({ ...s, topic: t.name })) }
        catch { /* skip offline */ }
      }
      setSubs(all)
    }).catch(() => {})
  }, [])
  return subs
}

function LogForm({ go }) {
  const subs = useSubtopics()
  const [f, setF] = useState({ name: '', subtopic_id: '', summary: '', status: 'live', owner: '' })
  const [comps, setComps] = useState([{ kind: 'repo', label: '', ref: '', notes: '' }])
  const [attrs, setAttrs] = useState([{ key: '', value: '' }])
  const [files, setFiles] = useState([])
  const [filesKey, setFilesKey] = useState(0)
  const [impFiles, setImpFiles] = useState([])
  const [impKey, setImpKey] = useState(0)
  const [importing, setImporting] = useState(false)
  const [importMsg, setImportMsg] = useState('')
  const [suggEntries, setSuggEntries] = useState([])
  const set = k => e => setF({ ...f, [k]: e.target.value })
  const importDoc = async () => {
    if (!impFiles.length) return
    setImporting(true); setImportMsg('')
    try {
      const fd = new FormData()
      impFiles.forEach(fl => fd.append('file', fl))
      const r = await fetch('/ingest/document', { method: 'POST', body: fd })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail || 'import failed')
      const dp = d.draft_project || {}
      setF(prev => ({ ...prev,
        name: prev.name || dp.name || '',
        summary: prev.summary || dp.summary || '',
        owner: prev.owner || dp.owner || '' }))
      const fresh = (d.components || []).map(c => ({ kind: c.kind, label: c.label, ref: c.ref, notes: c.notes || '' }))
      setComps(prev => {
        const untouched = prev.length === 1 && !prev[0].label && !prev[0].ref
        return [...(untouched ? [] : prev), ...fresh]
      })
      const freshA = (d.attributes || []).map(a => ({ key: a.key, value: a.value }))
      setAttrs(prev => {
        const untouched = prev.length === 1 && !prev[0].key
        return [...(untouched ? [] : prev), ...freshA]
      })
      const nEnt = (d.suggested_entries || []).length
      setSuggEntries((d.suggested_entries || []).map(en => ({ ...en, include: true })))
      setFiles(prev => [...prev, ...impFiles.filter(fl => !prev.some(p => p.name === fl.name && p.size === fl.size))])
      const names = (d.filenames || [d.filename]).join(', ')
      const warns = (d.warnings || []).map(w => `${w.filename}: ${w.error}`).join('; ')
      setImportMsg(`${d.mode === 'ai' ? '✦ AI read' : 'Regex basics (AI unreachable)'} ${names} (${Math.max(1, Math.round(d.chars / 1024))} KB text): ${fresh.length} components, ${nEnt} entries proposed — review everything, then Save.${warns ? ' Skipped: ' + warns : ''}`)
    } catch (e) { setImportMsg('Import failed: ' + e.message) }
    finally { setImporting(false) }
  }
  const submit = async () => {
    const body = { ...f, subtopic_id: Number(f.subtopic_id), components: comps.filter(c => c.label || c.ref), attributes: attrs.filter(a => a.key) }
    const r = await api('/projects', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    for (const fl of files) {
      const fd = new FormData()
      fd.append('file', fl)
      fd.append('project_id', String(r.id))
      if (f.owner) fd.append('uploaded_by', f.owner)
      await fetch('/documents/upload', { method: 'POST', body: fd })
    }
    for (const en of suggEntries.filter(x => x.include && x.title.trim())) {
      await api(`/projects/${r.id}/entries`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: en.title, body: en.body, entry_kind: en.entry_kind,
          source_type: 'document', source_ref: impFiles.map(fl => fl.name).join(', ') || 'imported-doc' }) })
    }
    go({ name: 'project', id: r.id })
  }
  return (
    <div className="panel">
      <p className="meta">Only 5 required fields. Everything else is optional rows. If logging feels like work, the product fails.</p>
      <h3 className="sub">Import from document (optional — skip it and type manually)</h3>
      <p className="meta">Drop a messy spec, spreadsheet, or link-dump (pdf / docx / xlsx / csv / txt). The tool reads it and fills this form — you review and Save.</p>
      <div className="row2" style={{ gridTemplateColumns: '1fr auto', alignItems: 'center' }}>
        <input key={impKey} type="file" multiple accept=".pdf,.docx,.xlsx,.csv,.txt,.md" onChange={e => { setImpFiles([...e.target.files]); setImportMsg('') }} />
        <button className="primary" onClick={importDoc} disabled={importing || !impFiles.length}>{importing ? 'Reading…' : `Extract & fill${impFiles.length > 1 ? ` (${impFiles.length})` : ''}`}</button>
      </div>
      {importMsg && <div className="meta" style={{ marginBottom: 8 }}>{importMsg}</div>}
      {suggEntries.length > 0 && (
        <>
          <h3 className="sub">Proposed entries (created on Save, sourced to the doc)</h3>
          {suggEntries.map((en, i) => (
            <div key={i} className="docrow">
              <input type="checkbox" style={{ width: 'auto' }} checked={en.include} onChange={e => setSuggEntries(suggEntries.map((x, j) => j === i ? { ...x, include: e.target.checked } : x))} />
              <span><b>{en.title}</b> <span className="meta">· {en.entry_kind}</span></span>
            </div>
          ))}
        </>
      )}
      <div className="row2">
        <div><label>Name*</label><input value={f.name} onChange={set('name')} /></div>
        <div><label>Owner*</label><input value={f.owner} onChange={set('owner')} /></div>
      </div>
      <label>Subtopic*</label>
      <select value={f.subtopic_id} onChange={set('subtopic_id')}><option value="">—</option>{subs.map(s => <option key={s.id} value={s.id}>{s.topic} / {s.name}</option>)}</select>
      <label>Summary*</label><input value={f.summary} onChange={set('summary')} />
      <label>Status*</label><select value={f.status} onChange={set('status')}><option>live</option><option>ongoing</option><option>deprecated</option></select>
      <h3 className="sub">Components (optional, repeatable)</h3>
      {comps.map((c, i) => (
        <div className="row2" key={i} style={{ gridTemplateColumns: '140px 1fr 1fr' }}>
          <select value={c.kind} onChange={e => setComps(comps.map((x, j) => j === i ? { ...x, kind: e.target.value } : x))}>
            <option>api</option><option>database</option><option>repo</option><option>dashboard</option><option>widget</option><option>computation</option><option>report</option><option>doc</option><option>other</option>
          </select>
          <input placeholder="label" value={c.label} onChange={e => setComps(comps.map((x, j) => j === i ? { ...x, label: e.target.value } : x))} />
          <input placeholder="ref / URL" value={c.ref} onChange={e => setComps(comps.map((x, j) => j === i ? { ...x, ref: e.target.value } : x))} />
        </div>
      ))}
      <button className="ghost" onClick={() => setComps([...comps, { kind: 'repo', label: '', ref: '', notes: '' }])}>+ Add component</button>
      <h3 className="sub">Attributes (optional key-value)</h3>
      {attrs.map((a, i) => (
        <div className="row2" key={i}>
          <input placeholder="key" value={a.key} onChange={e => setAttrs(attrs.map((x, j) => j === i ? { ...x, key: e.target.value } : x))} />
          <input placeholder="value" value={a.value} onChange={e => setAttrs(attrs.map((x, j) => j === i ? { ...x, value: e.target.value } : x))} />
        </div>
      ))}
      <div><button className="ghost" onClick={() => setAttrs([...attrs, { key: '', value: '' }])}>+ Add attribute</button></div>
      <h3 className="sub">Documents (optional — 5 required fields stay required)</h3>
      <input key={filesKey} type="file" multiple onChange={e => setFiles([...e.target.files])} />
      {files.map((fl, i) => (
        <div key={`${fl.name}-${i}`} className="docrow"><span>📎</span><code className="mono">{fl.name}</code><span className="meta">{Math.max(1, Math.round(fl.size / 1024))} KB · attaches on save</span><button className="ghost" onClick={() => setFiles(files.filter((_, j) => j !== i))}>Remove</button></div>
      ))}
      {files.length > 0 && <div><button className="ghost" onClick={() => { setFiles([]); setFilesKey(k => k + 1) }}>Clear all</button></div>}
      <div style={{ marginTop: 12 }}><button className="primary" onClick={submit}>Save project</button></div>
    </div>
  )
}

function KTForm({ go }) {
  const subs = useSubtopics()
  const [text, setText] = useState('Nikhil: The CVAR iFlow reports read EEPE from the shared engine.\nQ: Where does the data come from?\nA: CCR Data Creator publishes the mart and the endpoint; iFlow only displays.')
  const [subtopicId, setSubtopicId] = useState('')
  const [draft, setDraft] = useState(null)
  const [owner, setOwner] = useState('')
  const [done, setDone] = useState(null)
  const preview = async () => {
    const r = await api('/ingest/transcript', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, subtopic_id: subtopicId ? Number(subtopicId) : null }) })
    setDraft({ ...r, projectName: r.draft_project.name, projectSummary: r.draft_project.summary,
      entries: r.draft_entries.map(en => ({ ...en, kind: en.entry_kind, subtopic_id: subtopicId || '' })) })
    setDone(null)
  }
  const approve = async () => {
    const r = await api('/ingest/approve', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subtopic_id: Number(subtopicId), project_name: draft.projectName, project_summary: draft.projectSummary, project_status: 'live', owner, entries: draft.entries.map(en => ({ title: en.title, body: en.body, entry_kind: en.kind })) }) })
    setDone(r)
  }
  return (
    <div className="panel">
      <label>Paste KT transcript</label>
      <textarea rows={6} value={text} onChange={e => setText(e.target.value)} />
      <label>Subtopic*</label>
      <select value={subtopicId} onChange={e => setSubtopicId(e.target.value)}><option value="">—</option>{subs.map(s => <option key={s.id} value={s.id}>{s.topic} / {s.name}</option>)}</select>
      <div><button className="primary" onClick={preview}>Generate drafts (deterministic, offline)</button></div>
      {draft && (
        <>
          <h3 className="sub">Draft project (edit inline)</h3>
          <input value={draft.projectName} onChange={e => setDraft({ ...draft, projectName: e.target.value })} />
          <input value={draft.projectSummary} onChange={e => setDraft({ ...draft, projectSummary: e.target.value })} />
          <label>Owner</label><input value={owner} onChange={e => setOwner(e.target.value)} placeholder="e.g. Likhitha Sharma" />
          <h3 className="sub">Draft entries ({draft.entries.length})</h3>
          {draft.entries.map((en, i) => (
            <div key={i} className="panel">
              <input value={en.title} onChange={e => setDraft({ ...draft, entries: draft.entries.map((x, j) => j === i ? { ...x, title: e.target.value } : x) })} />
              <textarea rows={3} value={en.body} onChange={e => setDraft({ ...draft, entries: draft.entries.map((x, j) => j === i ? { ...x, body: e.target.value } : x) })} />
              <div className="row2">
                <select value={en.kind} onChange={e => setDraft({ ...draft, entries: draft.entries.map((x, j) => j === i ? { ...x, kind: e.target.value } : x) })}>
                  <option value="definition">definition</option><option value="caveat">caveat</option><option value="howto">howto</option><option value="process">process</option><option value="note">note</option>
                </select>
                <select value={en.subtopic_id} onChange={e => setDraft({ ...draft, entries: draft.entries.map((x, j) => j === i ? { ...x, subtopic_id: e.target.value } : x) })}>
                  <option value="">same as project</option>{subs.map(s => <option key={s.id} value={s.id}>{s.topic} / {s.name}</option>)}
                </select>
              </div>
              <span className="meta">from {en.suggested_speaker}</span>
            </div>
          ))}
          <button className="primary" onClick={approve}>Approve all — create everything</button>
        </>
      )}
      {done && <div className="panel"><b>Created!</b> <a style={{ color: '#4F46E5', cursor: 'pointer' }} onClick={() => go({ name: 'project', id: done.project_id })}>Open project #{done.project_id}</a> · entries {done.entry_ids.join(', ')}</div>}
    </div>
  )
}

function JiraForm({ go }) {
  const [keysText, setKeysText] = useState('RISQ-5107')
  const [projects, setProjects] = useState([])
  const [projectId, setProjectId] = useState('')
  const [previews, setPreviews] = useState(null)
  const [done, setDone] = useState(null)
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { api('/projects').then(ps => { setProjects(ps); if (ps.length && !projectId) setProjectId(String(ps[0].id)) }).catch(() => {}) }, [])
  const keys = [...new Set(keysText.toUpperCase().split(/[\s,;]+/).map(k => k.trim()).filter(Boolean))]
  const preview = async () => {
    setBusy(true); setDone(null); setMsg('')
    try {
      const out = []
      for (const k of keys) out.push(await api(`/jira/ticket/${encodeURIComponent(k)}`))
      setPreviews(out)
    } catch (e) { setMsg('Preview failed: ' + e.message) }
    finally { setBusy(false) }
  }
  const submit = async () => {
    if (!keys.length || !projectId) { setMsg('Add at least one ticket ID and pick a project.'); return }
    setBusy(true); setMsg('')
    try {
      const r = await api('/ingest/jira', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: Number(projectId), ticket_keys: keys }) })
      setDone(r); setPreviews(null)
    } catch (e) { setMsg('Import failed: ' + e.message) }
    finally { setBusy(false) }
  }
  return (
    <div className="panel">
      <p className="meta">Type one or more ticket IDs — imports each ticket's description + labels plus all consecutive worklogs, linked to the project. Offline mock Jira, deterministic per ID.</p>
      <label>Ticket IDs (comma or space separated)*</label>
      <input value={keysText} onChange={e => { setKeysText(e.target.value); setDone(null) }} placeholder="RISQ-4821, RISQ-5001" />
      <label>Link to project*</label>
      <select value={projectId} onChange={e => setProjectId(e.target.value)}>
        {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      <div className="row2" style={{ gridTemplateColumns: 'auto auto 1fr', alignItems: 'center' }}>
        <button className="ghost" onClick={preview} disabled={busy || !keys.length}>Preview {keys.length > 0 ? `(${keys.length})` : ''}</button>
        <button className="primary" onClick={submit} disabled={busy || !keys.length || !projectId}>{busy ? 'Working…' : `Import ${keys.length > 1 ? `${keys.length} tickets` : 'ticket'}`}</button>
        <span className="meta">{msg}</span>
      </div>
      {(previews || []).map(t => (
        <div key={t.ticket_key} className="panel">
          <div style={{ fontSize: 16 }}><code className="mono">{t.ticket_key}</code> <b>{t.summary}</b></div>
          <p style={{ fontSize: 15 }}>{t.description}</p>
          <div className="meta">Labels: {t.labels.map(l => <code key={l} className="mono">{l}</code>).join(' ')}</div>
          <div className="meta">Reporter: {t.reporter} · {t.worklogs.length} worklogs:</div>
          {t.worklogs.map((w, i) => (
            <div key={i} className="srctag" style={{ margin: '6px 0' }}>🎫 {w.author} · {w.created.slice(0, 16).replace('T', ' ')} — {w.text}</div>
          ))}
        </div>
      ))}
      {done && (
        <div className="panel"><b>Imported {done.entry_ids.length} entries.</b>
          {done.tickets.map(t => (
            <div key={t.ticket_key} style={{ marginTop: 8 }}>
              <code className="mono">{t.ticket_key}</code>{' '}
              <a style={{ color: 'var(--accent)', cursor: 'pointer' }} onClick={() => go({ name: 'entry', id: t.entry_id })}>ticket entry #{t.entry_id}</a>
              <span className="meta"> + {t.worklog_entry_ids.length} worklogs</span>
            </div>
          ))}
          <div style={{ marginTop: 10 }}><button className="primary" onClick={() => go({ name: 'project', id: Number(projectId) })}>Open project page</button></div>
        </div>
      )}
    </div>
  )
}
