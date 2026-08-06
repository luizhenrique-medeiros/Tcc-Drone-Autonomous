import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { AuthContext, type AuthContextValue } from '../src/features/auth/auth-context';
import { RequireAdmin } from '../src/routes/RequireAdmin';

const renderRoute = (value: AuthContextValue) =>
  render(
    <MemoryRouter initialEntries={['/orders']}>
      <AuthContext.Provider value={value}>
        <Routes>
          <Route path="/login" element={<h1>Entrar</h1>} />
          <Route element={<RequireAdmin />}>
            <Route path="/orders" element={<h1>Fila protegida</h1>} />
          </Route>
        </Routes>
      </AuthContext.Provider>
    </MemoryRouter>,
  );

const baseContext: AuthContextValue = {
  user: null,
  isLoading: false,
  login: vi.fn(),
  logout: vi.fn(),
};

describe('proteção de rotas administrativas', () => {
  it('redireciona uma sessão ausente para o login', () => {
    renderRoute(baseContext);
    expect(screen.getByRole('heading', { name: 'Entrar' })).toBeInTheDocument();
    expect(screen.queryByText('Fila protegida')).not.toBeInTheDocument();
  });

  it('permite somente uma sessão ADMIN', () => {
    renderRoute({
      ...baseContext,
      user: {
        id: 'admin-1',
        name: 'Admin Teste',
        email: 'admin@example.local',
        role: 'ADMIN',
      },
    });
    expect(screen.getByRole('heading', { name: 'Fila protegida' })).toBeInTheDocument();
  });
});
