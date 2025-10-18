import { useMemo, useState, useRef, useEffect } from 'react';
import { Toaster, toast } from 'react-hot-toast';
import { useAuth } from '../context/AuthContext';
import { apiService } from '../services/api';
import { ArrowUpTrayIcon, UserIcon, EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline';
import ProfileMenu from './ProfileMenu';
import { UploadView, ProfileView, UploadsView, EditMedicalView, ChatView, HomeView, ScheduleView } from './Views';
import { Card } from './UIPrimitives';


function CustomSelect({ value, onChange, options = [], placeholder = '' }) {
    const [open, setOpen] = useState(false);
    const ref = useRef(null);

    useEffect(() => {
        const onDoc = (e) => {
            if (!ref.current) return;
            if (!ref.current.contains(e.target)) setOpen(false);
        };
        document.addEventListener('click', onDoc);
        return () => document.removeEventListener('click', onDoc);
    }, []);

    const label = options.find(o => o.value === value)?.label || placeholder || '';

    return (
        <div ref={ref} className="relative w-full max-w-full min-w-0">
            <button
                type="button"
                onClick={() => setOpen(s => !s)}
                className="w-full text-left flex items-center justify-between gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm hover:border-gray-400"
                aria-haspopup="listbox"
                aria-expanded={open}
                aria-label={placeholder || 'select'}
            >
                <span className={`truncate ${!value ? 'text-gray-400' : 'text-gray-700'}`}>{label}</span>
                <svg className="h-4 w-4 text-gray-500" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M6 8l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
            </button>

            {open && (
                <ul className="absolute z-20 mt-1 w-full max-w-full min-w-0 overflow-auto rounded-lg border border-gray-200 bg-white shadow-lg" style={{ maxHeight: 200 }} role="listbox">
                    {options.map(opt => (
                        <li
                            key={opt.value}
                            role="option"
                            aria-selected={opt.value === value}
                            onClick={() => { onChange(opt.value); setOpen(false); }}
                            className="cursor-pointer px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 truncate"
                            title={opt.label}
                        >
                            {opt.label}
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}

export default function OnePageApp() {
    const { isAuthenticated, login, logout, token, user } = useAuth();
    const [view, setView] = useState(() => {
        try {
            return localStorage.getItem('view') || 'home';
        } catch (_err) {
            return 'home';
        }
    });
    const [authTab, setAuthTab] = useState('register');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [name, setName] = useState('');
    const [age, setAge] = useState('');
    const [gender, setGender] = useState('');
    const [phone, setPhone] = useState('');
    const [file, setFile] = useState(null);
    const [fileName, setFileName] = useState('');
    const defaultProfile = {
        present_conditions: '', diagnosed_conditions: '', medications_past: '', medications_current: '', allergies: '', medical_history: '', family_history: '', surgeries: '', immunizations: '', lifestyle_factors: ''
    };
    const [profile, setProfile] = useState(defaultProfile);
    const [originalProfile, setOriginalProfile] = useState(defaultProfile);
    const [busy, setBusy] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const [me, setMe] = useState(null);
    const [showProfileMenu, setShowProfileMenu] = useState(false);
    const menuRef = useRef(null);
    const [chatMessages, setChatMessages] = useState([]);

    const canLogin = useMemo(() => email && password, [email, password]);
    const canRegister = useMemo(() => name && email && password, [name, email, password]);
    const canUpload = useMemo(() => !!file, [file]);

    const doLogin = async () => {
        setBusy(true);
        try {
            await login(email, password);
            toast.success('Welcome back!');
        } catch (err) {
            toast.error(err.message || 'Login failed');
        } finally { setBusy(false); }
    };

    const doRegister = async () => {
        setBusy(true);
        try {
            const payload = { name, email, password };
            if (age) payload.age = Number(age);
            if (gender) payload.gender = (typeof gender === 'string' ? gender.toUpperCase() : gender);
            if (phone) payload.phone = phone;
            await apiService.register(payload);
            toast.success('Account created. Please sign in.');
            setAuthTab('login');
        } catch (err) {
            toast.error(err.message || 'Registration failed');
        } finally { setBusy(false); }
    };

    const doUpload = async () => {
        if (!token || !file) { toast.error('Select a file'); return; }
        setBusy(true);
        try {
            const fd = new FormData();
            fd.append('file', file);
            if (fileName && fileName.trim()) fd.append('display_name', fileName.trim());
            await apiService.uploadDocument(fd, token);
            toast.success('Uploaded!');
        } catch (err) {
            toast.error(err.message || 'Upload failed');
        } finally { setBusy(false); setFile(null); setFileName(''); }
    };

    const saveProfile = async () => {
        if (!token) { toast.error('Sign in first'); return; }
        setBusy(true);
        try {
            if (!profileExists) {
                await apiService.createMedicalProfile(profile, token);
            } else {
                // Compute only changed fields and send a PATCH
                const changes = {};
                Object.keys(profile).forEach((k) => {
                    if (profile[k] !== originalProfile[k]) {
                        changes[k] = profile[k];
                    }
                });
                if (Object.keys(changes).length > 0) {
                    await apiService.patchMedicalProfile(changes, token);
                }
            }

            // Re-fetch profile to ensure UI state matches server
            const pf = await apiService.getMedicalProfile(token);
            setProfile(pf || defaultProfile);
            setOriginalProfile(pf || defaultProfile);
            setProfileExists(Boolean(pf));
            toast.success('Profile saved');
            setView('profile');
        } catch (err) {
            toast.error(err.message || 'Save failed');
        } finally { setBusy(false); }
    };

    const [filesList, setFilesList] = useState([]);
    const [loadingProfile, setLoadingProfile] = useState(false);
    const [profileExists, setProfileExists] = useState(false);

    useEffect(() => {
        if (!isAuthenticated || (view !== 'profile' && view !== 'uploads' && view !== 'home')) return;
        let mounted = true;
        const load = async () => {
            setLoadingProfile(true);
            try {
                if (view === 'profile') {
                    try {
                        const meData = await apiService.getMe(token);
                        if (!mounted) return;
                        setMe(meData || user || null);
                    } catch (_err) {
                        // fallback to auth context user
                        setMe(user || null);
                    }

                    try {
                        const pf = await apiService.getMedicalProfile(token);
                        if (!mounted) return;
                        if (pf === null) {
                            // no profile yet
                            setProfile(defaultProfile);
                            setOriginalProfile(defaultProfile);
                            setProfileExists(false);
                        } else {
                            setProfile(pf);
                            setOriginalProfile(pf);
                            setProfileExists(true);
                        }
                    } catch (_err) {
                        // non-404 errors
                        setProfile(defaultProfile);
                        setOriginalProfile(defaultProfile);
                        setProfileExists(false);
                    }
                }

                try {
                    const files = await apiService.getFiles(token);
                    if (!mounted) return;
                    setFilesList(files || []);
                } catch (_err) {
                    setFilesList([]);
                }
            } finally {
                setLoadingProfile(false);
            }
        };
        load();
        return () => { mounted = false; };
    }, [isAuthenticated, view, token]);

    // Respond to child-triggered refresh events
    useEffect(() => {
        if (!isAuthenticated) return;
        const handler = async () => {
            try {
                const files = await apiService.getFiles(token);
                setFilesList(files || []);
            } catch {
                // ignore
            }
        };
        window.addEventListener('refresh-files', handler);
        return () => window.removeEventListener('refresh-files', handler);
    }, [isAuthenticated, token]);

    useEffect(() => {
        const onDoc = (e) => {
            if (!menuRef.current) return;
            if (!menuRef.current.contains(e.target)) setShowProfileMenu(false);
        };
        document.addEventListener('click', onDoc);
        return () => document.removeEventListener('click', onDoc);
    }, []);

    useEffect(() => {
        try {
            if (isAuthenticated) localStorage.setItem('view', view);
            else localStorage.removeItem('view');
        } catch (_err) { /* ignore storage error */ }
    }, [view, isAuthenticated]);

    useEffect(() => {
        if (!isAuthenticated) {
            setView('upload');
            try { localStorage.removeItem('view'); } catch (_err) { /* ignore storage error */ }
        }
    }, [isAuthenticated]);

    // Set CSS --vh variable to handle mobile browser chrome (100dvh issues)
    useEffect(() => {
        const setVh = () => {
            document.documentElement.style.setProperty('--vh', `${window.innerHeight * 0.01}px`);
        };
        setVh();
        window.addEventListener('resize', setVh);
        return () => window.removeEventListener('resize', setVh);
    }, []);

    // Refs for layout elements so we can compute the exact available height for the chat pane
    const headerRef = useRef(null);
    const mainRef = useRef(null);
    const footerRef = useRef(null);
    const [chatHeight, setChatHeight] = useState(null);

    // Compute available height for chat area and update on resize / layout changes
    useEffect(() => {
        const compute = () => {
            const vh = window.innerHeight;
            const headerH = headerRef.current?.offsetHeight || 0;
            const footerH = footerRef.current?.offsetHeight || 0;
            let paddingTop = 0, paddingBottom = 0;
            if (mainRef.current) {
                const cs = getComputedStyle(mainRef.current);
                paddingTop = parseFloat(cs.paddingTop) || 0;
                paddingBottom = parseFloat(cs.paddingBottom) || 0;
            }
            // small gap allowance for spacing (headers, margins)
            const gap = 16;
            const avail = Math.max(0, vh - headerH - footerH - paddingTop - paddingBottom - gap);
            setChatHeight(avail);
        };

        compute();
        window.addEventListener('resize', compute);
        window.addEventListener('orientationchange', compute);
        const ro = new ResizeObserver(compute);
        if (headerRef.current) ro.observe(headerRef.current);
        if (footerRef.current) ro.observe(footerRef.current);
        if (mainRef.current) ro.observe(mainRef.current);
        return () => {
            window.removeEventListener('resize', compute);
            window.removeEventListener('orientationchange', compute);
            ro.disconnect();
        };
    }, []);

    return (
        <div className="app-root relative flex flex-col bg-gradient-to-br from-indigo-50 via-white to-purple-50 overflow-x-hidden" style={{ height: 'calc(var(--vh, 1vh) * 100)' }}>
            <Toaster position="top-center" />

            {/* Header */}
            <div ref={headerRef} className="sticky top-0 z-10 border-b border-black/5 bg-white/70 backdrop-blur">
                <div ref={null} className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
                    <div className="flex items-center gap-2">
                        <div className="grid h-8 w-8 place-items-center rounded-lg bg-indigo-600 text-white shadow">
                            <UserIcon className="h-5 w-5" />
                        </div>
                        <span className="text-lg font-semibold tracking-tight text-gray-900">Pharma DPD</span>
                    </div>
                    <div className="flex items-center gap-2">
                        {isAuthenticated ? (
                            <>
                                <button onClick={() => { setView('home'); setShowProfileMenu(false); }} className="flex items-center gap-2 rounded-lg bg-white px-3 py-1.5 text-sm font-medium border border-gray-200 hover:bg-gray-50">Home</button>
                                <button onClick={() => { setView('schedule'); setShowProfileMenu(false); }} className="flex items-center gap-2 rounded-lg bg-white px-3 py-1.5 text-sm font-medium border border-gray-200 hover:bg-gray-50">Schedule</button>
                                <ProfileMenu
                                    isOpen={showProfileMenu}
                                    onToggle={setShowProfileMenu}
                                    onSelectProfile={() => setView('profile')}
                                    onSelectUploads={() => setView('uploads')}
                                    onLogout={logout}
                                />
                            </>
                        ) : null}
                    </div>
                </div>
            </div>

            {/* Content */}
            <main className="mx-auto max-w-6xl px-4 pt-10 pb-16 flex-1 w-full overflow-auto">
                {!isAuthenticated ? (
                    <div className="mx-auto max-w-lg">
                        <Card>
                            <div className="flex items-center gap-2">
                                <button onClick={() => setAuthTab('register')} className={`px-4 py-2 text-sm font-medium rounded-lg border ${authTab === 'register' ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'}`}>Register</button>
                                <button onClick={() => setAuthTab('login')} className={`px-4 py-2 text-sm font-medium rounded-lg border ${authTab === 'login' ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'}`}>Login</button>
                            </div>
                            {authTab === 'register' ? (
                                <div className="mt-6 space-y-4">
                                    <input className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500" placeholder="Full name" value={name} onChange={e => setName(e.target.value)} />
                                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 min-w-0">
                                        <input inputMode="numeric" pattern="[0-9]*" className="w-full max-w-full min-w-0 rounded-lg border border-gray-300 px-3 py-2 box-border focus:outline-none focus:ring-2 focus:ring-indigo-500" placeholder="Age" value={age} onChange={e => setAge(e.target.value.replace(/[^0-9]/g, ''))} />
                                        <CustomSelect
                                            value={gender}
                                            placeholder="Select gender"
                                            onChange={v => setGender(v)}
                                            options={[
                                                { value: 'male', label: 'Male' },
                                                { value: 'female', label: 'Female' },
                                                { value: 'other', label: 'Other' },
                                            ]}
                                        />
                                    </div>
                                    <input className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500" placeholder="Phone" value={phone} onChange={e => setPhone(e.target.value)} />
                                    <input className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} />
                                    <div className="relative">
                                        <input className="w-full rounded-lg border border-gray-300 pr-10 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500" placeholder="Password" type={showPassword ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)} />
                                                            <button
                                                                type="button"
                                                                aria-label="Show password"
                                                                onMouseDown={() => setShowPassword(true)}
                                                                onMouseUp={() => setShowPassword(false)}
                                                                onMouseLeave={() => setShowPassword(false)}
                                                                onTouchStart={() => setShowPassword(true)}
                                                                onTouchEnd={() => setShowPassword(false)}
                                                                onTouchCancel={() => setShowPassword(false)}
                                                                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-500 hover:text-gray-700"
                                                            >
                                                                {showPassword ? <EyeSlashIcon className="h-5 w-5" /> : <EyeIcon className="h-5 w-5" />}
                                                            </button>
                                    </div>
                                    <button disabled={busy || !canRegister} onClick={doRegister} className="w-full rounded-xl bg-indigo-600 px-4 py-2 font-semibold text-white hover:bg-indigo-500 disabled:opacity-50">{busy ? 'Creating...' : 'Create account'}</button>
                                </div>
                            ) : (
                                <div className="mt-6 space-y-4">
                                    <input className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} />
                                    <div className="relative">
                                        <input className="w-full rounded-lg border border-gray-300 pr-10 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500" placeholder="Password" type={showPassword ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)} />
                                                            <button
                                                                type="button"
                                                                aria-label="Show password"
                                                                onMouseDown={() => setShowPassword(true)}
                                                                onMouseUp={() => setShowPassword(false)}
                                                                onMouseLeave={() => setShowPassword(false)}
                                                                onTouchStart={() => setShowPassword(true)}
                                                                onTouchEnd={() => setShowPassword(false)}
                                                                onTouchCancel={() => setShowPassword(false)}
                                                                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-500 hover:text-gray-700"
                                                            >
                                                                {showPassword ? <EyeSlashIcon className="h-5 w-5" /> : <EyeIcon className="h-5 w-5" />}
                                                            </button>
                                    </div>
                                    <button disabled={busy || !canLogin} onClick={doLogin} className="w-full rounded-xl bg-gray-900 px-4 py-2 font-semibold text-white hover:bg-black disabled:opacity-50">{busy ? 'Signing in...' : 'Sign in'}</button>
                                </div>
                            )}
                        </Card>
                    </div>
                ) : (
                    <div>
                        <div className="mx-auto max-w-2xl">
                            {view === 'home' && (
                                <HomeView file={file} setFile={setFile} fileName={fileName} setFileName={setFileName} doUpload={doUpload} busy={busy} canUpload={canUpload} token={token} filesList={filesList} loadingProfile={loadingProfile} setFilesList={setFilesList} />
                            )}

                            {view === 'profile' && (
                                <ProfileView me={me} profile={profile} onEdit={() => setView('edit-medical')} />
                            )}

                            {view === 'edit-medical' && (
                                <EditMedicalView profile={profile} setProfile={setProfile} onSave={saveProfile} onCancel={() => setView('profile')} busy={busy} />
                            )}

                            {view === 'uploads' && (
                                <UploadsView filesList={filesList} loadingProfile={loadingProfile} token={token} />
                            )}
                            {view === 'schedule' && (
                                <ScheduleView token={token} />
                            )}
                            {view === 'chat' && (
                                <div className="flex flex-col" style={{ height: chatHeight ? `${chatHeight}px` : `calc(var(--vh, 1vh) * 100 - 220px)` }}>
                                    <Card className="flex flex-col h-full" allowOverflow>
                                        <div className="flex items-center justify-between">
                                            <h2 className="text-xl font-semibold text-gray-900">Assistant</h2>
                                            <div className="flex items-center gap-2">
                                                <button
                                                    onClick={() => {
                                                        if (chatMessages.length === 0) return;
                                                        if (window.confirm('Clear chat history?')) setChatMessages([]);
                                                    }}
                                                    aria-label="Clear chat"
                                                    className="text-sm text-gray-500 hover:text-gray-700 rounded-md px-2 py-1 border border-transparent hover:bg-gray-100"
                                                >
                                                    Clear
                                                </button>
                                            </div>
                                        </div>
                                        <div className="mt-4 flex-1 min-h-0 overflow-auto chat-scroll" style={{ maxHeight: chatHeight }}>
                                            <ChatView token={token} messages={chatMessages} setMessages={setChatMessages} />
                                        </div>
                                    </Card>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </main>

            {/* Footer */}
            <div ref={footerRef} className="border-t border-black/5 bg-white/60 py-8 text-center text-sm text-gray-500 backdrop-blur">
                Testing - Capstone Project
            </div>
            {/* Floating chat button */}
            <button
                onClick={() => setView(v => v === 'chat' ? 'upload' : 'chat')}
                aria-label={view === 'chat' ? 'Close chat' : 'Open chat'}
                className="fixed right-6 bottom-6 z-50 rounded-full bg-indigo-600 p-4 text-white shadow-lg hover:bg-indigo-500"
            >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.77 9.77 0 01-4-.8L3 21l1.8-4.2A7.97 7.97 0 013 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
            </button>
        </div>
    );
}
