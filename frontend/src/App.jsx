import React, { useEffect, useState } from 'react'

const api = (p, opts) => fetch(p, opts).then(r => {
  if (!r.ok) throw new Error('API ' + r.status)
  return r.json()
})

const KIND_ICON = { definition: '📖', caveat: '⚠️', howto: '🛠️', process: '📋', note: '📝' }
const SRC_ICON = { kt_transcript: '🎤', jira: '🎫', repo: '📦', manual: '✍️' }
const COMP_ICON = { api: '🔌', database: '🗄️', repo: '📦', dashboard: '📊', report: '📄', doc: '📝', other: '🔧' }

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
          <span>📎</span>
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

export default function App() {
  const [view, setView] = useState({ name: 'topics' })
  const analystActive = view.name === 'topics' || view.name === 'topic' || view.name === 'entry'
  return (
    <>
      <header className="topbar">
        <span className="brand" style={{ cursor: 'pointer' }} title="Go to home" onClick={() => setView({ name: 'topics' })}>TeamRiskFusion</span>
        <span className="tagline">Answers that outlive their authors.</span>
        <button className={'navbtn' + (analystActive ? ' active' : '')} onClick={() => setView({ name: 'topics' })}>Analyst</button>
        <button className={'navbtn' + (view.name.startsWith('project') ? ' active' : '')} onClick={() => setView({ name: 'projects' })}>Dev Projects</button>
        <button className={'navbtn' + (view.name === 'capture' ? ' active' : '')} onClick={() => setView({ name: 'capture' })}>Capture</button>
      </header>
      <div className="demo-bar">Demo: analyst pain → knowledge page → Priya discovers → paste KT → continuity. “Wikis wait for people to write. Ours extracts.”</div>
      <div className="wrap">
        {view.name === 'topics' && <Topics go={setView} />}
        {view.name === 'topic' && <TopicView id={view.id} go={setView} />}
        {view.name === 'entry' && <EntryView id={view.id} go={setView} />}
        {view.name === 'projects' && <Projects go={setView} />}
        {view.name === 'project' && <ProjectView id={view.id} go={setView} />}
        {view.name === 'capture' && <Capture go={setView} />}
      </div>
    </>
  )
}

/* ---------- Analyst home ---------- */
function Topics({ go }) {
  const [topics, setTopics] = useState([])
  const [stats, setStats] = useState({})
  useEffect(() => {
    api('/topics').then(async ts => {
      setTopics(ts)
      const s = {}
      for (const t of ts) {
        try {
          const d = await api(`/topics/${t.id}`)
          const stale = d.entries.filter(e => e.stale).length
          s[t.id] = { entries: d.entries.length, projects: d.projects.length, stale,
            dot: stale > 0 ? 'dot-amber' : 'dot-green' }
        } catch { s[t.id] = { entries: 0, projects: 0, stale: 0, dot: 'dot-green' } }
      }
      setStats(s)
    }).catch(() => setTopics([]))
  }, [])
  return (
    <>
      <h1 className="pagetitle">Analyst home — pick a topic, get an answer. No ticket.</h1>
      {topics.length === 0 && <div className="empty">No topics yet — paste a KT transcript in Capture to create the first one.</div>}
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
  useEffect(() => { api(`/topics/${id}`).then(setT).catch(() => {}) }, [id])
  if (!t) return <div>Loading…</div>
  return (
    <>
      <div className="crumb"><a onClick={() => go({ name: 'topics' })}>Topics</a> / {t.name}</div>
      <h1 className="pagetitle">{t.name}</h1>
      <p style={{ fontSize: 15 }}>{t.description}</p>
      <HealthPanel topicId={id} />
      {t.subtopics.map(s => {
        const entries = t.entries.filter(e => e.subtopic_id === s.id)
        return (
          <div key={s.id}>
            <h2 className="section">{s.name}</h2>
            {entries.length === 0 && <div className="empty">No entries yet — paste a KT transcript in Capture to create the first one.</div>}
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
      <h2 className="section">Projects in this topic</h2>
      {t.projects.length === 0 && <div className="empty">No projects yet — log one in Capture (5 fields).</div>}
      <div className="cards3">
        {t.projects.map(p => (
          <div key={p.id} className="card" onClick={() => go({ name: 'project', id: p.id })}>
            <div className="card-title">{p.name}</div>
            <StatusPill s={p.status} />
            <div className="meta">owner: {p.owner_name}</div>
            <p style={{ fontSize: 15 }}>{p.summary}</p>
          </div>
        ))}
      </div>
      {t.projects.map(p => <ContinuityCard key={'c' + p.id} projectId={p.id} />)}
    </>
  )
}

/* ---------- Entry page ---------- */
function EntryView({ id, go }) {
  const [e, setE] = useState(null)
  const [crumb, setCrumb] = useState({ topic: '', topicId: null, sub: '' })
  const [team, setTeam] = useState([])
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
  }, [id])
  const projId = e && e.project ? e.project.id : null
  useEffect(() => {
    if (projId) api(`/projects/${projId}`).then(p => setTeam((p.people || []).map(x => x.person_name))).catch(() => setTeam([]))
    else setTeam([])
  }, [projId])
  if (!e) return <div>Loading…</div>
  const contributors = [...new Set([e.author, ...team].filter(Boolean))]
  return (
    <>
      <div className="crumb">
        <a onClick={() => go({ name: 'topics' })}>Topics</a>
        {crumb.topicId && <> / <a onClick={() => go({ name: 'topic', id: crumb.topicId })}>{crumb.topic}</a></>}
        {crumb.sub && <> / {crumb.sub}</>}
      </div>
      <h1 className="pagetitle">{e.title}</h1>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 4, marginBottom: 8 }}>
        <KindBadge k={e.entry_kind} /><FreshBadge stale={e.stale} />
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
      <pre className="body">{e.body}</pre>
      <h2 className="section">Contributors</h2>
      <div className="avatars">{contributors.map(c => <span key={c} title={c}><span className="avatar">{initials(c)}</span> <span className="meta">{c}</span></span>)}<span className="meta">verified {e.verified_at?.slice(0, 10)}</span></div>
      <h2 className="section">Sources</h2>
      {(e.sources || []).length === 0 && <div className="empty">No sources linked.</div>}
      {(e.sources || []).map(s => (
        <div key={s.id} className="srctag" style={{ margin: '6px 0' }}>
          {SRC_ICON[s.source_type] || '•'} {s.source_type} · <code className="mono">{s.source_ref}</code> · <span className="meta">updated {s.source_updated_at?.slice(0, 10)}</span>
        </div>
      ))}
      {e.stale && <div className="warnbanner">⚠ STALE: a source updated after this entry was verified.</div>}
      <h2 className="section">Documents</h2>
      <DocSection entryId={e.id} />
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
      {filtered.length === 0 && <div className="empty">No projects match — log one in Capture (5 fields).</div>}
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
      <div className="panel">Priya flow: search topic → find project → see databases, API endpoints, repos, owner. “Where do I get the data?” in 2 minutes.</div>
    </>
  )
}

function ProjectView({ id, go }) {
  const [p, setP] = useState(null)
  useEffect(() => { api(`/projects/${id}`).then(setP).catch(() => {}) }, [id])
  if (!p) return <div>Loading…</div>
  const groups = {}
  p.components.forEach(c => { (groups[c.kind] = groups[c.kind] || []).push(c) })
  return (
    <>
      <div className="crumb"><a onClick={() => go({ name: 'projects' })}>Projects</a> / {p.name}</div>
      <h1 className="pagetitle">{p.name} <StatusPill s={p.status} /></h1>
      <div className="meta">Subtopic: {p.subtopic_name} · Owner: {p.owner_name}</div>
      <p style={{ fontSize: 15 }}>{p.summary}</p>
      <h2 className="section">Components — what it’s made of</h2>
      {p.components.length === 0 && <div className="empty">No components yet — attach a repo link in Capture.</div>}
      <table className="grid"><thead><tr><th></th><th>Label</th><th>Ref</th><th>Notes</th></tr></thead>
        <tbody>{Object.keys(groups).sort().map(k => (
          <React.Fragment key={k}>
            <tr className="grouprow"><td colSpan={4}>{COMP_ICON[k] || ''} {k} ({groups[k].length})</td></tr>
            {groups[k].map(c => <tr key={c.id}><td>{COMP_ICON[c.kind] || ''}</td><td>{c.label}</td><td><code className="mono">{c.ref}</code></td><td>{c.notes}</td></tr>)}
          </React.Fragment>
        ))}</tbody>
      </table>
      <h2 className="section">People</h2>
      <div className="avatars">{p.people.map((x, i) => <span key={i} title={`${x.person_name} (${x.role})`}><span className="avatar">{initials(x.person_name)}</span> <span className="meta">{x.person_name} ({x.role})</span></span>)}</div>
      <h2 className="section">Documents</h2>
      <DocSection projectId={p.id} />
      <h2 className="section">Linked knowledge</h2>
      {p.entries.length === 0 && <div className="empty">No linked entries — paste a KT transcript in Capture.</div>}
      {p.entries.map(e => (
        <div key={e.id} className="entryrow" onClick={() => go({ name: 'entry', id: e.id })}>
          <span style={{ fontSize: 15 }}>{e.title}</span><KindBadge k={e.entry_kind} /><FreshBadge stale={e.stale} />
        </div>
      ))}
      <h2 className="section">Business continuity</h2>
      <ContinuityCard projectId={p.id} />
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
      <h1 className="pagetitle">Capture — logging is a byproduct, not homework</h1>
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
  const set = k => e => setF({ ...f, [k]: e.target.value })
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
    go({ name: 'project', id: r.id })
  }
  return (
    <div className="panel">
      <p className="meta">Only 5 required fields. Everything else is optional rows. If logging feels like work, the product fails.</p>
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
            <option>api</option><option>database</option><option>repo</option><option>dashboard</option><option>report</option><option>doc</option><option>other</option>
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
  const [text, setText] = useState('Arjun: The exposure dashboard refreshes daily at 06:30 CET.\nQ: What is EAD?\nA: Exposure at default, after netting and collateral.')
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
          <label>Owner</label><input value={owner} onChange={e => setOwner(e.target.value)} placeholder="e.g. Priya Nair" />
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
  const [json, setJson] = useState('{"project_id": 2, "ticket_key": "RISQ-5001", "summary": "RWA explains need April footnote", "description": "Add footnote: April RWA includes methodology fix.", "entry_kind": "note", "author": "Aisha Khan"}')
  const [msg, setMsg] = useState('')
  const submit = async () => {
    try {
      const body = JSON.parse(json)
      const r = await api('/ingest/jira', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      setMsg('Created entry #' + r.entry_id)
    } catch (e) { setMsg('Error: ' + e.message) }
  }
  return (
    <div className="panel">
      <label>Paste mock Jira ticket JSON</label>
      <textarea rows={7} value={json} onChange={e => setJson(e.target.value)} />
      <div><button className="primary" onClick={submit}>Import</button> <span className="meta">{msg}</span></div>
      {!!msg.startsWith('Created') && <div className="meta">Find it on its project page → linked knowledge.</div>}
    </div>
  )
}
