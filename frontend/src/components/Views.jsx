import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ArrowUpTrayIcon, PencilIcon } from '@heroicons/react/24/outline';
import { apiService } from '../services/api';
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
                <button disabled={busy || !canUpload} onClick={async () => { await doUpload(); try { const files = await apiService.getFiles(token); setFilesList(files || []); } catch { } }} className="w-full rounded-xl bg-indigo-600 px-4 py-2 font-semibold text-white hover:bg-indigo-500 disabled:opacity-50">{busy ? 'Uploading...' : 'Upload'}</button>
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

export function UploadsView({ filesList, loadingProfile, token }) {
    const [loadingMap, setLoadingMap] = useState({});

    const openFile = async (f) => {
        const baseUrl = f.s3_url || (f.filename ? `https://${import.meta.env.VITE_S3_BUCKET || 'bucket'}.s3.${import.meta.env.VITE_S3_REGION || 'region'}.amazonaws.com/${f.filename}` : '#');
        setLoadingMap(m => ({ ...m, [f.id]: true }));
        try {
            // Always request a presigned URL from the backend. This ensures access for private buckets.
            const res = await apiService.presignFile(f.id, token);
            const url = res?.presigned_url || baseUrl;
            window.open(url, '_blank', 'noopener,noreferrer');
        } catch (e) {
            // fallback to plain url if presign failed for any reason
            console.warn('Presign failed, falling back to base URL', e);
            try { window.open(baseUrl, '_blank', 'noopener,noreferrer'); } catch { }
        } finally {
            setLoadingMap(m => ({ ...m, [f.id]: false }));
        }
    };

    return (
        <Card>
            <h2 className="text-xl font-semibold text-gray-900">Uploaded documents</h2>
            <div className="mt-4 space-y-2">
                {loadingProfile ? <div className="text-sm text-gray-500">Loading...</div> : (
                    filesList.length ? filesList.map(f => {
                        const baseUrl = f.s3_url || (f.filename ? `https://${import.meta.env.VITE_S3_BUCKET || 'bucket'}.s3.${import.meta.env.VITE_S3_REGION || 'region'}.amazonaws.com/${f.filename}` : '#');
                        return (
                            <div key={f.id} className="flex items-center justify-between rounded-md border border-gray-100 px-3 py-2 min-w-0">
                                <div className="flex-1 min-w-0">
                                    <span className="block min-w-0 truncate break-all text-sm text-gray-800">{f.filename}</span>
                                </div>
                                <div className="flex items-center gap-3 flex-shrink-0">
                                    <div className="text-xs text-gray-500">{new Date(f.upload_date).toLocaleString()}</div>
                                    <button disabled={loadingMap[f.id]} onClick={() => openFile(f)} className="text-xs text-indigo-600 hover:underline">{loadingMap[f.id] ? 'Opening…' : 'View'}</button>
                                </div>
                            </div>
                        );
                    }) : <div className="text-sm text-gray-500">No files uploaded yet.</div>
                )}
            </div>
        </Card>
    );
}

export function ChatView({ token, apiService, messages, setMessages }) {
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
            console.log(`${import.meta.env.VITE_API_BASE_URL}/chat/`);
            const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/chat/`, {
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
        } catch (e) {
            setMessages(m => [...m, { id: Date.now() + Math.random(), role: 'assistant', content: 'Error: could not get response' }]);
        } finally { setSending(false); }
    };

    return (
        <div className="flex flex-col h-full min-h-0">
            <div className="flex-1 min-h-0 overflow-auto rounded-lg border border-gray-100 bg-white p-3">
                {(!messages || messages.length) === 0 ? <div className="text-sm text-gray-500">No messages yet. Ask something about your documents or health.</div> : messages.map(m => (
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
