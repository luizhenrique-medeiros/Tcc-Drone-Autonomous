import {
  Activity,
  BookOpen,
  ChevronDown,
  ClipboardList,
  Gauge,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  Radio,
  X,
} from 'lucide-react';
import { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { appConfig } from '../services';
import { Brand } from './Brand';
import { useAuth } from '../features/auth/use-auth';

const navItems = [
  { to: '/', label: 'Visão geral', icon: LayoutDashboard, end: true },
  { to: '/orders', label: 'Fila de pedidos', icon: ClipboardList },
  { to: '/vehicles', label: 'Saúde do veículo', icon: Gauge },
  { to: '/operations', label: 'Operação ao vivo', icon: Radio },
  { to: '/history', label: 'Histórico e eventos', icon: History },
];

const pageLabels: Record<string, string> = {
  '/': 'Visão geral',
  '/orders': 'Fila de pedidos',
  '/vehicles': 'Saúde do veículo',
  '/operations': 'Operação ao vivo',
  '/history': 'Histórico e eventos',
  '/design-system': 'Catálogo visual',
};

export function AdminShell() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const currentLabel = location.pathname.startsWith('/orders/')
    ? 'Detalhe do pedido'
    : location.pathname.startsWith('/missions/')
      ? 'Missão e autorização'
      : (pageLabels[location.pathname] ?? 'Centro de operações');

  return (
    <div className="admin-app">
      {appConfig.demoMode ? (
        <div className="demo-banner" role="status">
          <Activity size={16} aria-hidden="true" />
          <strong>Modo demonstração</strong>
          <span>Dados locais — nenhum comando é enviado ao veículo.</span>
        </div>
      ) : null}

      <aside className={`sidebar ${menuOpen ? 'sidebar--open' : ''}`}>
        <div className="sidebar__brand">
          <Brand compact />
          <button
            className="icon-button sidebar__close"
            type="button"
            aria-label="Fechar menu"
            onClick={() => setMenuOpen(false)}
          >
            <X size={21} />
          </button>
        </div>
        <div className="sidebar__context">
          <span>Workspace</span>
          <strong>Operação acadêmica</strong>
          <small>Ambiente controlado</small>
        </div>
        <nav className="sidebar__nav" aria-label="Navegação principal">
          <span className="sidebar__section-label">Operação</span>
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                `sidebar__link ${isActive ? 'sidebar__link--active' : ''}`
              }
            >
              <Icon size={19} aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
          {import.meta.env.DEV ? (
            <>
              <span className="sidebar__section-label sidebar__section-label--spaced">
                Desenvolvimento
              </span>
              <NavLink
                to="/design-system"
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) =>
                  `sidebar__link ${isActive ? 'sidebar__link--active' : ''}`
                }
              >
                <BookOpen size={19} aria-hidden="true" />
                <span>Design system</span>
              </NavLink>
            </>
          ) : null}
        </nav>
        <div className="sidebar__safety">
          <span className="sidebar__safety-icon"><Activity size={18} /></span>
          <div>
            <strong>Segurança operacional</strong>
            <small>Revisão e autorização são etapas independentes.</small>
          </div>
        </div>
      </aside>

      {menuOpen ? (
        <button
          className="sidebar-scrim"
          type="button"
          aria-label="Fechar menu"
          onClick={() => setMenuOpen(false)}
        />
      ) : null}

      <div className="admin-main">
        <header className="topbar">
          <div className="cluster">
            <button
              className="icon-button topbar__menu"
              type="button"
              aria-label="Abrir menu"
              onClick={() => setMenuOpen(true)}
            >
              <Menu size={22} />
            </button>
            <div>
              <span className="topbar__eyebrow">DevCore Admin</span>
              <strong className="topbar__title">{currentLabel}</strong>
            </div>
          </div>
          <div className="topbar__actions">
            <span className="api-status">
              <span aria-hidden="true" />
              {appConfig.demoMode ? 'Demo local' : 'API configurada'}
            </span>
            <div className="user-menu">
              <button
                className="user-menu__trigger"
                type="button"
                onClick={() => setUserMenuOpen((current) => !current)}
                aria-expanded={userMenuOpen}
              >
                <span className="user-avatar" aria-hidden="true">
                  {user?.name.charAt(0).toUpperCase()}
                </span>
                <span className="user-menu__identity">
                  <strong>{user?.name}</strong>
                  <small>Administrador</small>
                </span>
                <ChevronDown size={16} aria-hidden="true" />
              </button>
              {userMenuOpen ? (
                <div className="user-menu__popover">
                  <span>{user?.email}</span>
                  <button type="button" onClick={logout}>
                    <LogOut size={17} aria-hidden="true" /> Sair com segurança
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </header>
        <main className="page-content" id="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
