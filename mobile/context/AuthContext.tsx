import React, { createContext, useState, useEffect } from 'react';
import storageService from '../services/storage';

export type AuthStatus = 'LOADING' | 'UNAUTHENTICATED' | 'AUTHENTICATED_NO_COMPANY' | 'READY';

interface AuthContextType {
    token: string | null;
    empresa: any | null;
    usuario: any | null;
    status: AuthStatus;
    login: (token: string, usuarioData: any) => Promise<void>;
    selectEmpresa: (empresaData: any) => Promise<void>;
    logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType>({
    token: null,
    empresa: null,
    usuario: null,
    status: 'LOADING',
    login: async () => { },
    selectEmpresa: async () => { },
    logout: async () => { },
});

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
    const [token, setToken] = useState<string | null>(null);
    const [empresa, setEmpresa] = useState<any | null>(null);
    const [usuario, setUsuario] = useState<any | null>(null);
    const [status, setStatus] = useState<AuthStatus>('LOADING');

    useEffect(() => {
        const loadStorageData = async () => {
            try {
                const storedToken = await storageService.getItem('jwt_token');
                const storedEmpresa = await storageService.getItem('empresa');
                const storedUsuario = await storageService.getItem('usuario');

                if (storedToken) {
                    setToken(storedToken);
                    if (storedUsuario) setUsuario(JSON.parse(storedUsuario));

                    if (storedEmpresa) {
                        setEmpresa(JSON.parse(storedEmpresa));
                        setStatus('READY');
                    } else {
                        setStatus('AUTHENTICATED_NO_COMPANY');
                    }
                } else {
                    setStatus('UNAUTHENTICATED');
                }
            } catch (error) {
                console.error('Error reading storage', error);
                setStatus('UNAUTHENTICATED');
            }
        };
        loadStorageData();
    }, []);

    const login = async (newToken: string, usuarioData: any) => {
        setToken(newToken);
        setUsuario(usuarioData);
        setStatus('AUTHENTICATED_NO_COMPANY');

        await storageService.setItem('jwt_token', newToken);
        await storageService.setItem('usuario', JSON.stringify(usuarioData));
    };

    const selectEmpresa = async (empresaData: any) => {
        setEmpresa(empresaData);
        setStatus('READY');
        await storageService.setItem('empresa', JSON.stringify(empresaData));
    };

    const logout = async () => {
        setToken(null);
        setUsuario(null);
        setEmpresa(null);
        setStatus('UNAUTHENTICATED');
        await storageService.removeItem('jwt_token');
        await storageService.removeItem('empresa');
        await storageService.removeItem('usuario');
    };

    return (
        <AuthContext.Provider value={{ token, empresa, usuario, status, login, selectEmpresa, logout }}>
            {children}
        </AuthContext.Provider>
    );
};
