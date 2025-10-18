import { createContext, useState, useContext, useEffect } from 'react';
import { apiService } from '../services/api';

const AuthContext = createContext();

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(null);
    const [loading, setLoading] = useState(true);
    // No auto-logout: keep tokens until explicit logout

    useEffect(() => {
        // Check if user is already logged in (from localStorage)
        const storedToken = localStorage.getItem('token');
        const storedUser = localStorage.getItem('user');

        if (storedToken && storedUser) {
            setToken(storedToken);
            // storedUser should be a plain email string. Support legacy JSON user objects too.
            try {
                let emailOnly;
                try {
                    const parsed = JSON.parse(storedUser);
                    emailOnly = parsed && typeof parsed === 'object' ? parsed.email : parsed;
                } catch (_err) {
                    emailOnly = storedUser;
                }
                setUser(emailOnly ? { email: emailOnly } : null);
            } catch (_err) {
                // failed to parse stored user, ignore
                setUser(null);
            }
        }

        setLoading(false);
    }, []);

    const login = async (email, password) => {
        try {
            const tokenData = await apiService.login(email, password);
            const { access_token } = tokenData;

            // Fetch current user details
            let userObject = { email };
            try {
                const me = await apiService.getMe(access_token);
                userObject = me || userObject;
            } catch (_err) {
                console.warn('[Auth] Unable to fetch /auth/me, using minimal user object');
            }

            setToken(access_token);
            setUser(userObject);
            localStorage.setItem('token', access_token);
            // persist only the email address as a plain string
            const emailToStore = userObject?.email || '';
            localStorage.setItem('user', emailToStore);
            return tokenData;
        } catch (error) {
            console.error('[Auth] Login failed:', error);
            throw new Error(error?.message || 'Login failed. Please check your credentials.');
        }
    };

    const logout = () => {
        console.warn('[Auth] Logging out – clearing token and user from localStorage');
        setToken(null);
        setUser(null);
        localStorage.removeItem('token');
        localStorage.removeItem('user');
    };

    const value = {
        user,
        token,
        login,
        logout,
        isAuthenticated: !!token,
    };

    return (
        <AuthContext.Provider value={value}>
            {!loading && children}
        </AuthContext.Provider>
    );
};