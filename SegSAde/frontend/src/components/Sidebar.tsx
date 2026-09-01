import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { 
  Users, 
  UserSquare2, 
  ShieldCheck, 
  History, 
  Home, 
  ChevronLeft, 
  ChevronRight, 
  LogOut, 
  Building2,
  LockKeyhole
} from 'lucide-react';

const Sidebar: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const menuItems = [
    { name: 'Inicio', path: '/', icon: <Home size={18} /> },
    { name: 'Usuarios', path: '/users', icon: <UserSquare2 size={18} /> },
    { name: 'Grupos', path: '/groups', icon: <Users size={18} /> },
    { name: 'Matriz Permisos', path: '/permissions', icon: <ShieldCheck size={18} /> },
    { name: 'Logs Auditoría', path: '/logs', icon: <History size={18} /> },
  ];

  return (
    <div 
      style={{
        width: collapsed ? '70px' : '260px',
        backgroundColor: 'var(--bg-secondary)',
        borderRight: '1px solid var(--border)',
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        position: 'sticky',
        top: 0,
        transition: 'width 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        flexShrink: 0,
        zIndex: 100
      }}
    >
      {/* Sidebar Header */}
      <div 
        style={{
          padding: '24px 20px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          position: 'relative'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
          <div 
            style={{
              backgroundColor: 'rgba(59, 130, 246, 0.1)',
              color: '#3B82F6',
              padding: '8px',
              borderRadius: '10px',
              border: '1px solid rgba(59, 130, 246, 0.2)',
              flexShrink: 0
            }}
          >
            <LockKeyhole size={20} />
          </div>
          {!collapsed && (
            <span style={{ fontSize: '18px', fontWeight: 700, letterSpacing: '-0.5px', whiteSpace: 'nowrap' }}>
              SADE Security
            </span>
          )}
        </div>
        
        {/* Toggle Button */}
        <button 
          onClick={() => setCollapsed(!collapsed)}
          style={{
            position: 'absolute',
            right: '-12px',
            top: '32px',
            width: '24px',
            height: '24px',
            borderRadius: '50%',
            backgroundColor: 'var(--bg-tertiary)',
            border: '1px solid var(--border)',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
            zIndex: 110
          }}
        >
          {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
        </button>
      </div>

      {/* Company Name Banner */}
      {!collapsed && user?.companyName && (
        <div 
          style={{
            margin: '16px 20px 8px',
            padding: '12px 14px',
            backgroundColor: 'rgba(255, 255, 255, 0.02)',
            border: '1px solid var(--border)',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px'
          }}
        >
          <Building2 size={16} style={{ color: '#3B82F6', flexShrink: 0 }} />
          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {user.companyName}
          </span>
        </div>
      )}

      {/* Menu Items */}
      <div style={{ flexGrow: 1, padding: '16px 10px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {menuItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <div 
              key={item.path}
              onClick={() => navigate(item.path)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '12px 14px',
                borderRadius: '8px',
                cursor: 'pointer',
                backgroundColor: isActive ? 'rgba(59, 130, 246, 0.08)' : 'transparent',
                color: isActive ? '#3B82F6' : 'var(--text-secondary)',
                fontWeight: isActive ? 600 : 400,
                transition: 'all 0.2s',
                overflow: 'hidden'
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.02)';
                  e.currentTarget.style.color = 'var(--text-primary)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.backgroundColor = 'transparent';
                  e.currentTarget.style.color = 'var(--text-secondary)';
                }
              }}
            >
              <div style={{ flexShrink: 0, color: isActive ? '#3B82F6' : 'inherit' }}>
                {item.icon}
              </div>
              {!collapsed && (
                <span style={{ fontSize: '14px', whiteSpace: 'nowrap' }}>{item.name}</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Sidebar Footer (User Info & Logout) */}
      <div 
        style={{
          padding: '16px',
          borderTop: '1px solid var(--border)',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px'
        }}
      >
        {!collapsed && (
          <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: '0 4px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user?.fullName || user?.username}
            </span>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginTop: '2px' }}>
              Nivel: {user?.nivel} • {user?.username}
            </span>
          </div>
        )}
        
        <button 
          onClick={handleLogout}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            gap: '12px',
            padding: '12px 14px',
            borderRadius: '8px',
            backgroundColor: 'rgba(239, 68, 68, 0.05)',
            border: '1px solid rgba(239, 68, 68, 0.1)',
            color: '#EF4444',
            cursor: 'pointer',
            fontFamily: 'var(--font-family)',
            fontSize: '14px',
            fontWeight: 500,
            transition: 'all 0.2s',
            width: '100%'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
            e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.2)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.05)';
            e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.1)';
          }}
        >
          <LogOut size={16} style={{ flexShrink: 0 }} />
          {!collapsed && <span>Cerrar Sesión</span>}
        </button>
      </div>
    </div>
  );
};

export default Sidebar;
