const isBrowser = (typeof window !== 'undefined' && window.location);
const host = isBrowser && window.location.hostname ? window.location.hostname : 'localhost';
const protocol = isBrowser && window.location.protocol ? window.location.protocol.replace(':', '') : 'http';
const defaultBackendPort = import.meta.env.VITE_API_PORT || '8000';
const rawEnvApi = import.meta.env.VITE_API_BASE_URL;

const parseEnvApi = (val) => {
    if (!val) return null;
    const v = String(val).trim();
    if (v === '' || v.toLowerCase() === 'auto') return null;
    if (v.startsWith('http://') || v.startsWith('https://')) return v;
    return `http://${v}`;
};

const API_BASE_URL = parseEnvApi(rawEnvApi) || `${protocol}://${host}:${defaultBackendPort}`;

if (isBrowser && window.console && typeof window.console.debug === 'function') {
    console.debug('[api] Resolved API_BASE_URL =', API_BASE_URL, ' (env:', rawEnvApi, ', port:', defaultBackendPort, ')');
}

export const getApiBase = () => API_BASE_URL;

const parseError = async (response) => {
    try {
        const data = await response.json();
        if (typeof data?.detail === 'string') return data.detail;
        if (typeof data?.error === 'string') return data.error;
        return JSON.stringify(data);
    } catch {
        return response.statusText || 'Request failed';
    }
};

export const apiService = {
    getMe: async (token) => {
        const response = await fetch(`${API_BASE_URL}/auth/me`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
        });
        if (!response.ok) {
            throw new Error(await parseError(response) || 'Failed to fetch current user');
        }
        return response.json();
    },
    register: async (userData) => {
        const response = await fetch(`${API_BASE_URL}/auth/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(userData),
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Registration failed');
        }

        return response.json();
    },

    login: async (email, password) => {
        const params = new URLSearchParams();
        params.append('username', email);
        params.append('password', password);

        const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: params.toString(),
        });

        if (!response.ok) {
            throw new Error(await parseError(response) || 'Login failed');
        }

        return response.json();
    },

    uploadDocument: async (formData, token) => {
        const response = await fetch(`${API_BASE_URL}/files/upload`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
            },
            body: formData,
        });

        if (!response.ok) {
            throw new Error(await parseError(response) || 'Document upload failed');
        }

        return response.json();
    },

    getFiles: async (token) => {
        const response = await fetch(`${API_BASE_URL}/files/`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
        });

        if (!response.ok) {
            throw new Error(await parseError(response) || 'Failed to fetch files');
        }

        return response.json();
    },

    presignFile: async (fileId, token) => {
        const response = await fetch(`${API_BASE_URL}/files/${fileId}/presign`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
        });

        if (!response.ok) {
            throw new Error(await parseError(response) || 'Failed to get presigned URL');
        }

        return response.json();
    },

    getMedicalProfile: async (token) => {
        const response = await fetch(`${API_BASE_URL}/profile/medical-profile`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
        });
        if (response.status === 404) return null;

        if (!response.ok) {
            throw new Error(await parseError(response) || 'Failed to fetch medical profile');
        }

        return response.json();
    },

    createMedicalProfile: async (profileData, token) => {
        const response = await fetch(`${API_BASE_URL}/profile/medical-profile`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(profileData),
        });

        if (!response.ok) {
            throw new Error(await parseError(response) || 'Failed to create medical profile');
        }

        return response.json();
    },

    updateMedicalProfile: async (profileData, token) => {
        const response = await fetch(`${API_BASE_URL}/profile/medical-profile`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(profileData),
        });

        if (!response.ok) {
            throw new Error(await parseError(response) || 'Failed to update medical profile');
        }

        return response.json();
    },

    patchMedicalProfile: async (partialData, token) => {
        const response = await fetch(`${API_BASE_URL}/profile/medical-profile`, {
            method: 'PATCH',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(partialData),
        });

        if (!response.ok) {
            throw new Error(await parseError(response) || 'Failed to patch medical profile');
        }

        return response.json();
    },

    getExtraction: async (fileId, token) => {
        const response = await fetch(`${API_BASE_URL}/files/${fileId}/extraction`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
        });
        if (!response.ok) {
            throw new Error(await parseError(response) || 'Failed to fetch extraction');
        }
        return response.json();
    },
    acceptExtraction: async (fileId, token, payload) => {
        const response = await fetch(`${API_BASE_URL}/files/${fileId}/extraction/accept`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload ? { payload } : {}),
        });
        if (!response.ok) {
            throw new Error(await parseError(response) || 'Failed to accept extraction');
        }
        return response.json();
    },
    retryExtraction: async (fileId, token) => {
        const response = await fetch(`${API_BASE_URL}/files/${fileId}/retry`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
        });
        if (!response.ok) {
            throw new Error(await parseError(response) || 'Failed to retry extraction');
        }
        return response.json();
    },
    deleteFile: async (fileId, token) => {
        const response = await fetch(`${API_BASE_URL}/files/${fileId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
        });
        if (!response.ok) {
            throw new Error(await parseError(response) || 'Failed to delete file');
        }
        return response.json();
    },
    getSchedule: async (token) => {
        const response = await fetch(`${API_BASE_URL}/files/schedule`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
        });
        if (!response.ok) {
            throw new Error(await parseError(response) || 'Failed to fetch schedule');
        }
        return response.json();
    },
};