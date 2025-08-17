import { UserIcon } from '@heroicons/react/24/outline';
import { useRef, useEffect } from 'react';

export default function ProfileMenu({ isOpen, onToggle, onSelectProfile, onSelectUploads, onLogout }) {
  const ref = useRef(null);

  useEffect(() => {
    const onDoc = (e) => { if (!ref.current) return; if (!ref.current.contains(e.target)) onToggle(false); };
    document.addEventListener('click', onDoc);
    return () => document.removeEventListener('click', onDoc);
  }, [onToggle]);

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => onToggle(s => !s)} className="flex items-center gap-2 rounded-lg bg-white px-3 py-1.5 text-sm font-medium border border-gray-200 hover:bg-gray-50">
        <UserIcon className="h-4 w-4 text-gray-700" />
        <span className="text-sm text-gray-700">Profile</span>
      </button>

      {isOpen && (
        <div className="absolute right-0 z-30 mt-2 w-48 rounded-md border border-gray-100 bg-white shadow-lg">
          <button onClick={() => { onSelectProfile(); onToggle(false); }} className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50">Profile details</button>
          <button onClick={() => { onSelectUploads(); onToggle(false); }} className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50">Uploaded documents</button>
          <div className="border-t border-gray-100" />
          <button onClick={() => { onToggle(false); onLogout(); }} className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-gray-50">Logout</button>
        </div>
      )}
    </div>
  );
}
