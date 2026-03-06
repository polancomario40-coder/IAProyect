import { useEffect, useContext } from 'react';
import { ThemeProvider, DefaultTheme } from '@react-navigation/native';
import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Colors } from '../constants/Colors';
import { AuthProvider, AuthContext } from '../context/AuthContext';
import { View, ActivityIndicator } from 'react-native';

const customTheme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    background: Colors.light.background,
    primary: Colors.light.primary,
    text: Colors.light.text,
    card: Colors.light.card,
    border: Colors.light.border,
  },
};

function RootLayoutNav() {
  const { status } = useContext(AuthContext);
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (status === 'LOADING') return;

    const inAuthGroup = segments[0] === 'login';

    if (status === 'UNAUTHENTICATED' && !inAuthGroup) {
      router.replace('/login');
    } else if (status === 'AUTHENTICATED_NO_COMPANY' && segments[0] !== 'empresa-selector') {
      router.replace('/empresa-selector');
    } else if (status === 'READY') {
      if (segments[0] === 'login' || segments[0] === 'empresa-selector' || !segments[0] || segments[0] === 'index') {
        router.replace('/dashboard');
      }
    }
  }, [status, segments]);

  if (status === 'LOADING') {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: Colors.light.background }}>
        <ActivityIndicator size="large" color={Colors.light.primary} />
      </View>
    );
  }

  return (
    <ThemeProvider value={customTheme}>
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: Colors.light.primary },
          headerTintColor: '#FFF',
          headerTitleStyle: { fontWeight: 'bold' },
          headerShadowVisible: false,
          contentStyle: { backgroundColor: Colors.light.background },
        }}
        initialRouteName="index"
      >
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="login" options={{ title: 'Iniciar Sesión', headerShown: false }} />
        <Stack.Screen name="empresa-selector" options={{ title: 'Seleccionar Empresa', headerShown: false }} />
        <Stack.Screen name="dashboard" options={{ title: 'Dashboard', headerLeft: () => <View /> }} />
        <Stack.Screen name="suplidores" options={{ title: 'Suplidores' }} />
        <Stack.Screen name="factura" options={{ title: 'Nueva Factura' }} />
        <Stack.Screen name="confirmacion" options={{ title: 'Éxito', headerShown: false }} />
      </Stack>
      <StatusBar style="light" backgroundColor={Colors.light.primary} />
    </ThemeProvider>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <RootLayoutNav />
    </AuthProvider>
  );
}
