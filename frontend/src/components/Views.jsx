import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ArrowUpTrayIcon, PencilIcon } from '@heroicons/react/24/outline';
import { apiService, getApiBase } from '../services/api';
import { Card } from './UIPrimitives';

// Update the BaseView component to apply the no-scroll style globally
export function BaseView({ children }) {
  // Simple wrapper component — avoid modifying global body styles which can have side effects
  return (
    <div className="base-view">
      {children}
    </div>
  );
}

export function UploadView({ file, setFile, doUpload, busy, canUpload, token, apiService, setFilesList }) {
    return (
        <Card>
            <h2 className="text-xl font-semibold text-gray-900">Upload document</h2>
            <div className="mt-4 space-y-4">
                <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-gray-300 bg-gray-50 px-4 py-6 hover:bg-gray-100">
                    <ArrowUpTrayIcon className="h-6 w-6 text-gray-500" />
                    <span className="text-gray-700">{file ? file.name : 'Choose a file (PNG/JPEG/PDF up to 5MB)'} </span>
                    <input type="file" className="hidden" onChange={e => setFile(e.target.files?.[0] || null)} />
                </label>
                <button disabled={busy || !canUpload} onClick={async () => { await doUpload(); try { const files = await apiService.getFiles(token); setFilesList(files || []); } catch (_err) { /* ignore refresh error */ } }} className="w-full rounded-xl bg-indigo-600 px-4 py-2 font-semibold text-white hover:bg-indigo-500 disabled:opacity-50">{busy ? 'Uploading...' : 'Upload'}</button>
            </div>
        </Card>
    );
}

export function ProfileView({ me, profile, onEdit }) {
    const [expanded, setExpanded] = useState(false);

    const summaryFields = [
        { k: 'Medications (current)', v: profile?.medications_current },
        { k: 'Medications (past)', v: profile?.medications_past },
        { k: 'Allergies', v: profile?.allergies },
        { k: 'Surgeries', v: profile?.surgeries },
        { k: 'Immunizations', v: profile?.immunizations },
        { k: 'Lifestyle', v: profile?.lifestyle_factors },
        { k: 'Medical history', v: profile?.medical_history },
        { k: 'Family history', v: profile?.family_history },
    ].filter(f => f.v);

    const truncate = (text, n = 220) => (text && text.length > n ? text.slice(0, n) + '…' : text || '-');

    return (
        <Card className="p-4 sm:p-6">
            {/* Basic details (avatar, name, contact) */}
            <div className="flex items-center gap-4">
                <div className="h-12 w-12 flex-none rounded-full bg-indigo-600 text-white grid place-items-center font-semibold text-lg">{(me?.name || '?').slice(0, 1).toUpperCase()}</div>
                <div className="min-w-0">
                    <div className="text-base sm:text-lg font-semibold text-gray-900 truncate">{me?.name || me?.email || 'User'}</div>
                    <div className="text-sm text-gray-500 truncate">{me?.email || '-'}</div>
                    <div className="mt-1 flex gap-2 text-xs">
                        {me?.age ? <div className="rounded-md bg-gray-100 px-2 py-0.5">Age: {me.age}</div> : null}
                        {me?.gender ? <div className="rounded-md bg-gray-100 px-2 py-0.5">{me.gender}</div> : null}
                        {me?.phone ? <div className="rounded-md bg-gray-100 px-2 py-0.5">{me.phone}</div> : null}
                    </div>
                </div>
            </div>

            {/* Heading + edit icon (placed after basic details) */}
            <div className="flex items-center justify-between mt-3">
                <h2 className="text-lg sm:text-xl font-semibold text-gray-900">Medical info</h2>
                <button onClick={onEdit} aria-label="Edit medical profile" className="p-1 rounded-md text-gray-500 hover:bg-gray-100">
                    <PencilIcon className="h-5 w-5" />
                </button>
            </div>

            <div className="mt-4 grid gap-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="rounded-lg border border-gray-100 bg-white p-4">
                        <div className="text-sm text-gray-500">Present conditions</div>
                        <div className="mt-2 text-sm text-gray-800">{truncate(profile?.present_conditions)}</div>
                    </div>
                    <div className="rounded-lg border border-gray-100 bg-white p-4">
                        <div className="text-sm text-gray-500">Diagnosed conditions</div>
                        <div className="mt-2 text-sm text-gray-800">{truncate(profile?.diagnosed_conditions)}</div>
                    </div>
                </div>

                <div>
                    <div className="text-sm text-gray-600">Summary</div>
                    <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {summaryFields.slice(0, expanded ? summaryFields.length : 4).map(f => (
                            <div key={f.k} className="rounded-md border border-gray-100 bg-gray-50 p-3 text-sm">
                                <div className="text-xs text-gray-500">{f.k}</div>
                                <div className="text-sm text-gray-800 mt-1">{truncate(f.v, 140)}</div>
                            </div>
                        ))}
                    </div>

                    {summaryFields.length > 4 && (
                        <div className="mt-3">
                            <button onClick={() => setExpanded(s => !s)} className="text-sm text-indigo-600 hover:underline">{expanded ? 'Show less' : `Show ${summaryFields.length - 4} more`}</button>
                        </div>
                    )}
                </div>
            </div>
        </Card>
    );
}

export function EditMedicalView({ profile, setProfile, onSave, onCancel, busy }) {
    return (
        <Card>
            <div className="flex items-start justify-between">
                <h2 className="text-xl font-semibold text-gray-900">Edit medical profile</h2>
                <button onClick={onCancel} className="text-sm text-gray-500 hover:text-gray-700">Cancel</button>
            </div>

            <div className="mt-4 space-y-3">
                <label className="block text-sm text-gray-600">Present conditions</label>
                <textarea rows={3} className="w-full rounded-lg border border-gray-300 px-3 py-2" value={profile.present_conditions} onChange={e => setProfile(p => ({ ...p, present_conditions: e.target.value }))} />

                <label className="block text-sm text-gray-600">Diagnosed conditions</label>
                <textarea rows={3} className="w-full rounded-lg border border-gray-300 px-3 py-2" value={profile.diagnosed_conditions} onChange={e => setProfile(p => ({ ...p, diagnosed_conditions: e.target.value }))} />

                <label className="block text-sm text-gray-600">Medications (past)</label>
                <textarea rows={2} className="w-full rounded-lg border border-gray-300 px-3 py-2" value={profile.medications_past} onChange={e => setProfile(p => ({ ...p, medications_past: e.target.value }))} />

                <label className="block text-sm text-gray-600">Medications (current)</label>
                <textarea rows={2} className="w-full rounded-lg border border-gray-300 px-3 py-2" value={profile.medications_current} onChange={e => setProfile(p => ({ ...p, medications_current: e.target.value }))} />

                <label className="block text-sm text-gray-600">Allergies</label>
                <textarea rows={2} className="w-full rounded-lg border border-gray-300 px-3 py-2" value={profile.allergies} onChange={e => setProfile(p => ({ ...p, allergies: e.target.value }))} />

                <label className="block text-sm text-gray-600">Medical history</label>
                <textarea rows={2} className="w-full rounded-lg border border-gray-300 px-3 py-2" value={profile.medical_history} onChange={e => setProfile(p => ({ ...p, medical_history: e.target.value }))} />

                <label className="block text-sm text-gray-600">Family history</label>
                <textarea rows={2} className="w-full rounded-lg border border-gray-300 px-3 py-2" value={profile.family_history} onChange={e => setProfile(p => ({ ...p, family_history: e.target.value }))} />

                <label className="block text-sm text-gray-600">Surgeries</label>
                <textarea rows={2} className="w-full rounded-lg border border-gray-300 px-3 py-2" value={profile.surgeries} onChange={e => setProfile(p => ({ ...p, surgeries: e.target.value }))} />

                <label className="block text-sm text-gray-600">Immunizations</label>
                <textarea rows={2} className="w-full rounded-lg border border-gray-300 px-3 py-2" value={profile.immunizations} onChange={e => setProfile(p => ({ ...p, immunizations: e.target.value }))} />

                <label className="block text-sm text-gray-600">Lifestyle factors</label>
                <textarea rows={2} className="w-full rounded-lg border border-gray-300 px-3 py-2" value={profile.lifestyle_factors} onChange={e => setProfile(p => ({ ...p, lifestyle_factors: e.target.value }))} />

                <div className="flex gap-2">
                    <button disabled={busy} onClick={onSave} className="rounded-xl bg-gray-900 px-4 py-2 font-semibold text-white hover:bg-black disabled:opacity-50">{busy ? 'Saving...' : 'Save'}</button>
                    <button onClick={onCancel} className="rounded-xl border px-4 py-2">Cancel</button>
                </div>
            </div>
        </Card>
    );
}

export function UploadsView({ filesList, loadingProfile, token, showSchedule = true }) {
    const [loadingMap, setLoadingMap] = useState({});
    const [reviewMap, setReviewMap] = useState({});
    const [busyMap, setBusyMap] = useState({});
    const [schedule, setSchedule] = useState([]);
    const [retryBusy, setRetryBusy] = useState({});

    useEffect(() => {
        let mounted = true;
        (async () => {
            try {
                const s = await apiService.getSchedule(token);
                if (mounted) setSchedule(Array.isArray(s) ? s : []);
            } catch {}
        })();
        return () => { mounted = false; };
    }, [token]);

    const openFile = async (f) => {
        const baseUrl = f.s3_url || (f.filename ? `https://${import.meta.env.VITE_S3_BUCKET || 'bucket'}.s3.${import.meta.env.VITE_S3_REGION || 'region'}.amazonaws.com/${f.filename}` : '#');
        setLoadingMap(m => ({ ...m, [f.id]: true }));
        try {
            const res = await apiService.presignFile(f.id, token);
            const url = res?.presigned_url || baseUrl;
            window.open(url, '_blank', 'noopener,noreferrer');
        } catch (err) {
            console.warn('Presign failed, falling back to base URL', err);
            try { window.open(baseUrl, '_blank', 'noopener,noreferrer'); } catch { }
        } finally {
            setLoadingMap(m => ({ ...m, [f.id]: false }));
        }
    };

    const badge = (status) => {
        const s = String(status || '').toLowerCase();
        const cls = s === 'accepted' ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
            : s === 'uploaded' ? 'bg-blue-50 text-blue-700 border-blue-100'
            : s === 'awaiting_review' ? 'bg-amber-50 text-amber-700 border-amber-100'
            : 'bg-gray-50 text-gray-600 border-gray-100';
        const label = s.replace(/_/g, ' ') || 'unknown';
        return <span className={`text-xs rounded-md px-2 py-0.5 border ${cls}`}>{label}</span>;
    };

    const refreshList = async () => {
        try {
            const files = await apiService.getFiles(token);
            // naive global refresh by reloading the page state triggering parent effect is not available here,
            // so we just force a location reload as a simple approach
            // Ideally, lift state up to OnePageApp and pass a setter.
            window.dispatchEvent(new Event('refresh-files'));
            return files;
        } catch {
            return null;
        }
    };

    return (
        <Card>
            <h2 className="text-xl font-semibold text-gray-900">Uploaded documents</h2>
            {showSchedule && schedule && schedule.length > 0 ? (
                <div className="mt-4">
                    <div className="text-sm text-gray-700 font-medium">Your medication schedule</div>
                    <div className="mt-2 grid gap-2">
                        {schedule.slice(0, 6).map(e => (
                            <div key={e.id} className="rounded-md border border-gray-100 p-2 text-sm flex items-center justify-between">
                                <div className="min-w-0">
                                    <div className="font-medium text-gray-900 truncate">{e.name}</div>
                                    <div className="text-gray-600 text-xs truncate">{[e.dose, e.frequency].filter(Boolean).join(' • ') || '—'}</div>
                                </div>
                                {e.file_id ? <a href="#" onClick={(ev) => { ev.preventDefault(); /* could scroll to file */ }} className="text-xs text-indigo-600 hover:underline">from doc</a> : null}
                            </div>
                        ))}
                    </div>
                </div>
            ) : null}
            <div className="mt-4 space-y-2">
                {loadingProfile ? <div className="text-sm text-gray-500">Loading...</div> : (
                    filesList.length ? filesList.map(f => {
                        return (
                            <div key={f.id} className="flex items-center justify-between rounded-md border border-gray-100 px-3 py-2 min-w-0">
                                <div className="flex-1 min-w-0 pr-2">
                                    <div className="flex items-center gap-2">
                                        <span className="block min-w-0 truncate break-all text-sm text-gray-800">{f.display_name || f.filename}</span>
                                        {badge(f.status)}
                                    </div>
                                    <div className="text-xs text-gray-500 mt-0.5">{new Date(f.upload_date).toLocaleString()}</div>
                                </div>
                                <div className="flex items-center gap-3 flex-shrink-0">
                                    <button disabled={loadingMap[f.id]} onClick={() => openFile(f)} className="text-xs text-indigo-600 hover:underline">{loadingMap[f.id] ? 'Opening…' : 'View'}</button>
                                    {f.status !== 'accepted' ? (
                                        <button
                                            disabled={!!reviewMap[f.id]}
                                            onClick={async () => {
                                                setReviewMap(m => ({ ...m, [f.id]: true }));
                                                try {
                                                    const res = await apiService.getExtraction(f.id, token);
                                                    const pretty = JSON.stringify(res?.extracted?.llm_parsed || res?.extracted || {}, null, 2);
                                                    const ok = window.confirm(`Accept extracted data for:\n\n${pretty}\n\nClick OK to accept and save.`);
                                                    if (ok) {
                                                        await apiService.acceptExtraction(f.id, token);
                                                        f.status = 'accepted';
                                                    }
                                                } catch (_err) { /* ignore */ }
                                                finally { setReviewMap(m => ({ ...m, [f.id]: false })); }
                                            }}
                                            className="text-xs text-green-700 hover:underline"
                                        >
                                            {reviewMap[f.id] ? 'Reviewing…' : 'Review/Accept'}
                                        </button>
                                    ) : null}
                                    {f.status !== 'accepted' ? (
                                        <button
                                            disabled={!!retryBusy[f.id]}
                                            onClick={async () => {
                                                setRetryBusy(m => ({ ...m, [f.id]: true }));
                                                try {
                                                    await apiService.retryExtraction(f.id, token);
                                                    // Refresh files list to reflect awaiting_review and timestamps
                                                    await refreshList();
                                                    alert('Retry requested. The extraction has been re-run; open Review to check the new result.');
                                                } catch (err) {
                                                    const msg = err?.message || '';
                                                    // If backend returned cooldown with seconds, surface it
                                                    const m = /([0-9]+) seconds/gi.exec(msg);
                                                    if (m && m[1]) {
                                                        alert(`Please wait ~${m[1]}s before retrying again.`);
                                                    } else {
                                                        alert(msg || 'Retry failed');
                                                    }
                                                } finally {
                                                    setRetryBusy(m => ({ ...m, [f.id]: false }));
                                                }
                                            }}
                                            className="text-xs text-amber-700 hover:underline"
                                        >
                                            {retryBusy[f.id] ? 'Retrying…' : 'Retry'}
                                        </button>
                                    ) : null}
                                    <button
                                        disabled={!!busyMap[f.id]}
                                        onClick={async () => {
                                            const ok = window.confirm('Delete this document and its data? This cannot be undone.');
                                            if (!ok) return;
                                            setBusyMap(m => ({ ...m, [f.id]: true }));
                                            try {
                                                await apiService.deleteFile(f.id, token);
                                                // remove from local list optimistically
                                                const idx = filesList.findIndex(x => x.id === f.id);
                                                if (idx >= 0) filesList.splice(idx, 1);
                                                // attempt to refresh upstream
                                                await refreshList();
                                            } catch (err) {
                                                alert(err?.message || 'Delete failed');
                                            } finally {
                                                setBusyMap(m => ({ ...m, [f.id]: false }));
                                            }
                                        }}
                                        className="text-xs text-red-600 hover:underline"
                                    >
                                        {busyMap[f.id] ? 'Deleting…' : 'Delete'}
                                    </button>
                                </div>
                            </div>
                        );
                    }) : <div className="text-sm text-gray-500">No files uploaded yet.</div>
                )}
            </div>
        </Card>
    );
}

export function ScheduleView({ token }) {
    const [schedule, setSchedule] = useState([]);
    const [loading, setLoading] = useState(true);
    const [opening, setOpening] = useState({});

    useEffect(() => {
        let mounted = true;
        (async () => {
            setLoading(true);
            try {
                const s = await apiService.getSchedule(token);
                if (mounted) setSchedule(Array.isArray(s) ? s : []);
            } catch {
                if (mounted) setSchedule([]);
            } finally {
                if (mounted) setLoading(false);
            }
        })();
        return () => { mounted = false; };
    }, [token]);

    const openFromEntry = async (entry) => {
        if (!entry?.file_id) return;
        setOpening(m => ({ ...m, [entry.id]: true }));
        try {
            const res = await apiService.presignFile(entry.file_id, token);
            const url = res?.presigned_url;
            if (url) window.open(url, '_blank', 'noopener,noreferrer');
        } catch {
            // ignore
        } finally {
            setOpening(m => ({ ...m, [entry.id]: false }));
        }
    };

    return (
        <Card>
            <h2 className="text-xl font-semibold text-gray-900">Medication schedule</h2>
            {loading ? (
                <div className="mt-4 text-sm text-gray-500">Loading…</div>
            ) : schedule.length === 0 ? (
                <div className="mt-4 text-sm text-gray-500">No schedule entries yet. Upload and accept a prescription to populate your schedule.</div>
            ) : (
                <div className="mt-4 overflow-auto">
                    <table className="min-w-full text-sm">
                        <thead>
                            <tr className="text-left text-gray-600">
                                <th className="py-2 pr-4">Name</th>
                                <th className="py-2 pr-4">Dose</th>
                                <th className="py-2 pr-4">Frequency</th>
                                <th className="py-2 pr-4">Added</th>
                                <th className="py-2 pr-2">Source</th>
                            </tr>
                        </thead>
                        <tbody>
                            {schedule.map(e => (
                                <tr key={e.id} className="border-t border-gray-100">
                                    <td className="py-2 pr-4 text-gray-900">{e.name || '—'}</td>
                                    <td className="py-2 pr-4 text-gray-700">{e.dose || '—'}</td>
                                    <td className="py-2 pr-4 text-gray-700">{e.frequency || '—'}</td>
                                    <td className="py-2 pr-4 text-gray-500">{e.created_at ? new Date(e.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) : '—'}</td>
                                    <td className="py-2 pr-2">
                                        {e.file_id ? (
                                            <button
                                                className="text-xs text-indigo-600 hover:underline"
                                                disabled={!!opening[e.id]}
                                                onClick={() => openFromEntry(e)}
                                            >
                                                {opening[e.id] ? 'Opening…' : 'View'}
                                            </button>
                                        ) : (
                                            <span className="text-xs text-gray-400">—</span>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </Card>
    );
}

export function HomeView({ file, setFile, fileName, setFileName, doUpload, busy, canUpload, token, filesList, loadingProfile, setFilesList }) {
    return (
        <div className="grid gap-6">
            <Card>
                <h2 className="text-xl font-semibold text-gray-900">Upload document</h2>
                <div className="mt-4 space-y-4">
                    <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-gray-300 bg-gray-50 px-4 py-6 hover:bg-gray-100">
                        <ArrowUpTrayIcon className="h-6 w-6 text-gray-500" />
                        <span className="text-gray-700">{file ? file.name : 'Choose a file (PNG/JPEG/PDF up to 5MB)'} </span>
                        <input type="file" className="hidden" onChange={e => setFile(e.target.files?.[0] || null)} />
                    </label>
                    <input value={fileName} onChange={e => setFileName(e.target.value)} className="w-full rounded-lg border border-gray-300 px-3 py-2" placeholder="Optional display name (e.g., Prescription Oct.pdf)" />
                    <button disabled={busy || !canUpload} onClick={async () => { await doUpload(); try { const files = await apiService.getFiles(token); setFilesList(files || []); } catch (_err) {} }} className="w-full rounded-xl bg-indigo-600 px-4 py-2 font-semibold text-white hover:bg-indigo-500 disabled:opacity-50">{busy ? 'Uploading...' : 'Upload'}</button>
                </div>
            </Card>
            <UploadsView filesList={filesList} loadingProfile={loadingProfile} token={token} showSchedule={false} />
        </div>
    );
}

export function ChatView({ token, messages, setMessages }) {
    const [text, setText] = useState('');
    const [sending, setSending] = useState(false);

    const send = async () => {
        if (!text || !token) return;
        const userMsg = { role: 'user', content: text };
        // append user message
        setMessages(m => [...m, { id: Date.now() + Math.random(), ...userMsg }]);
        setText('');
        setSending(true);
        try {
            const base = getApiBase();
            const res = await fetch(`${base}/chat/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ message: userMsg.content })
            });
            if (!res.ok) throw new Error('Chat request failed');
            const data = await res.json();
            setMessages(m => [...m, { id: Date.now() + Math.random(), role: 'assistant', content: data.reply }]);
        } catch (_err) {
            setMessages(m => [...m, { id: Date.now() + Math.random(), role: 'assistant', content: 'Error: could not get response' }]);
        } finally { setSending(false); }
    };

    return (
        <div className="flex flex-col h-full min-h-0">
            <div className="flex-1 min-h-0 overflow-auto rounded-lg border border-gray-100 bg-white p-3">
                {(!messages || messages.length === 0) ? <div className="text-sm text-gray-500">No messages yet. Ask something about your documents or health.</div> : messages.map(m => (
                    <div key={m.id} className={`my-2 max-w-[85%] ${m.role === 'user' ? 'ml-auto text-right' : 'mr-auto text-left'}`}>
                        <div className={`inline-block rounded-lg px-3 py-2 ${m.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-900'}`}>
                            {m.role === 'assistant' ? (
                                <div className="prose max-w-none text-sm">
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content || ''}</ReactMarkdown>
                                </div>
                            ) : (
                                <div className="text-sm">{m.content}</div>
                            )}
                        </div>
                    </div>
                ))}
            </div>

            <div className="mt-3 flex gap-2">
                <input value={text} onChange={e => setText(e.target.value)} placeholder="Ask the assistant..." className="flex-1 rounded-lg border border-gray-300 px-3 py-2" />
                <button disabled={sending} onClick={send} className="rounded-lg bg-indigo-600 px-4 py-2 text-white">{sending ? 'Sending…' : 'Send'}</button>
            </div>
        </div>
    );
}
