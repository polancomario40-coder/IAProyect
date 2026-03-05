import React, { createContext, useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../services/api';

interface AuthContextType {
    token: string | null;
    empresa: any | null;
    usuario: any | null;
    login: (token: string, usuarioData: any, empresaData: any) => Promise<void>;
    logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType>({
    token: null,
    empresa: null,
    usuario: null,
    login: async () => { },
    logout: async () => { },
});

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
    const [token, setToken] = useState<string | null>(null);
    const [empresa, setEmpresa] = useState<any | null>(null);
    const [usuario, setUsuario] = useState<any | null>(null);

    useEffect(() => {
        const loadStorageData = async () => {
            try {
                const storedToken = await AsyncStorage.getItem('jwt_token');
                const storedEmpresa = await AsyncStorage.getItem('empresa');
                const storedUsuario = await AsyncStorage.getItem('usuario');

                if (storedToken && storedEmpresa) {
                    setToken(storedToken);
                    setEmpresa(JSON.parse(storedEmpresa));
                    if (storedUsuario) setUsuario(JSON.parse(storedUsuario));
                }
            } catch (error) {
                console.error('Error reading storage', error);
            }
        };
        loadStorageData();
    }, []);

    const login = async (newToken: string, usuarioData: any, empresaData: any) => {
        setToken(newToken);
        setUsuario(usuarioData);
        setEmpresa(empresaData);

        await AsyncStorage.setItem('jwt_token', newToken);
        await AsyncStorage.setItem('empresa', JSON.stringify(empresaData));
        await AsyncStorage.setItem('usuario', JSON.stringify(usuarioData));
    };

    const logout = async () => {
        setToken(null);
        setUsuario(null);
        setEmpresa(null);
        await AsyncStorage.removeItem('jwt_token');
        await AsyncStorage.removeItem('empresa');
        await AsyncStorage.removeItem('usuario');
    };

    return (
        <AuthContext.Provider value={{ token, empresa, usuario, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
};
