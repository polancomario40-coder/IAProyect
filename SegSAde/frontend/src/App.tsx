import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Sidebar from './components/Sidebar';
import Login from './pages/Login';
import AuthCallback from './pages/AuthCallback';
import Dashboard from './pages/Dashboard';
import AdminUsers from './pages/AdminUsers';
import AdminGroups from './pages/AdminGroups';
import AdminPermissions from './pages/AdminPermissions';
import AuditLogs from './pages/AuditLogs';

// Helper component to guard paths that require active company context
const CompanyRouteGuard: React.FC<{ children: React.ReactElement }> = ({ children }) => {
  const { user, token, loading } = useAuth();

  if (loading) {
    return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', backgroundColor: 'var(--bg-primary)', color: 'var(--text-secondary)' }}>Cargando sesión...</div>;
  }

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  if (!user?.companyId) {
    return <Navigate to="/login" replace />;
  }

  return children;
};


// Main Layout wrapping sidebar and content
const MainLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--bg-primary)' }}>
      <Sidebar />
      <div style={{ flexGrow: 1, overflowY: 'auto', height: '100vh', display: 'flex' }}>
        {children}
      </div>
    </div>
  );
};

const AppContent: React.FC = () => {
  return (
    <Routes>
      {/* Public Login Route */}
      <Route path="/login" element={<Login />} />

      <Route path="/auth-callback" element={<AuthCallback />} />

      {/* Core ERP Pages Guarded by Active Selected Company */}
      <Route 
        path="/" 
        element={
          <CompanyRouteGuard>
            <MainLayout>
              <Dashboard />
            </MainLayout>
          </CompanyRouteGuard>
        } 
      />

      <Route 
        path="/users" 
        element={
          <CompanyRouteGuard>
            <MainLayout>
              <AdminUsers />
            </MainLayout>
          </CompanyRouteGuard>
        } 
      />

      <Route 
        path="/groups" 
        element={
          <CompanyRouteGuard>
            <MainLayout>
              <AdminGroups />
            </MainLayout>
          </CompanyRouteGuard>
        } 
      />

      <Route 
        path="/permissions" 
        element={
          <CompanyRouteGuard>
            <MainLayout>
              <AdminPermissions />
            </MainLayout>
          </CompanyRouteGuard>
        } 
      />

      <Route 
        path="/logs" 
        element={
          <CompanyRouteGuard>
            <MainLayout>
              <AuditLogs />
            </MainLayout>
          </CompanyRouteGuard>
        } 
      />

      {/* Catch-all Redirect */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

const App: React.FC = () => {
  return (
    <Router>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </Router>
  );
};

export default App;
