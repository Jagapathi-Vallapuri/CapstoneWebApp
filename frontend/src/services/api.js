// API service to communicate with the FastAPI backend
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') || 'http://localhost:8000';

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
  // Get current user
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
  // User registration
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

  // User authentication
  login: async (email, password) => {
    // FastAPI OAuth2PasswordRequestForm expects application/x-www-form-urlencoded
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

  // Document upload
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

  // Get user's files
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

  // Get a presigned URL for viewing a file
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

  // Get user's medical profile
  getMedicalProfile: async (token) => {
    const response = await fetch(`${API_BASE_URL}/profile/medical-profile`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });
    // If the server returns 404 it means no profile exists yet — return null so callers can handle it explicitly
    if (response.status === 404) return null;

    if (!response.ok) {
      throw new Error(await parseError(response) || 'Failed to fetch medical profile');
    }

    return response.json();
  },

  // Create user's medical profile
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

  // Update user's medical profile
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
};