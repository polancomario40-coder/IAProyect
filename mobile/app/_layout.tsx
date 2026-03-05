import { ThemeProvider, DefaultTheme } from '@react-navigation/native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Colors } from '../constants/Colors';
import { AuthProvider } from '../context/AuthContext';
import { View } from 'react-native';

export default function RootLayout() {
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

  return (
    <AuthProvider>
      <ThemeProvider value={customTheme}>
        <Stack
          screenOptions={{
            headerStyle: { backgroundColor: Colors.light.primary },
            headerTintColor: '#FFF',
            headerTitleStyle: { fontWeight: 'bold' },
            headerShadowVisible: false,
            contentStyle: { backgroundColor: Colors.light.background },
          }}
        >
          <Stack.Screen name="index" options={{ title: 'Seleccionar Empresa', headerShown: false }} />
          <Stack.Screen name="login" options={{ title: 'Iniciar Sesión', headerShown: false }} />
          <Stack.Screen name="dashboard" options={{ title: 'Dashboard', headerLeft: () => <View /> }} />
          <Stack.Screen name="suplidores" options={{ title: 'Suplidores' }} />
          <Stack.Screen name="factura" options={{ title: 'Nueva Factura' }} />
          <Stack.Screen name="confirmacion" options={{ title: 'Éxito', headerShown: false }} />
        </Stack>
        <StatusBar style="light" backgroundColor={Colors.light.primary} />
      </ThemeProvider>
    </AuthProvider>
  );
}
