import { Eye, EyeOff, LockKeyhole, Mail, ShieldCheck } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Brand } from '../../components/Brand';
import { Button, Feedback } from '../../design-system/components';
import { appConfig, getErrorMessage } from '../../services';
import { useAuth } from './use-auth';

interface LocationState {
  from?: { pathname?: string };
}

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState(
    appConfig.demoMode ? 'admin@devcore.local' : '',
  );
  const [password, setPassword] = useState(
    appConfig.demoMode ? 'demo-admin' : '',
  );
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  if (user?.role === 'ADMIN') return <Navigate to="/" replace />;

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      await login({ email: email.trim(), password });
      const state = location.state as LocationState | null;
      navigate(state?.from?.pathname ?? '/', { replace: true });
    } catch (submitError) {
      setError(getErrorMessage(submitError));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="login-page">
      <section className="login-visual" aria-label="Centro administrativo DevCore">
        <div className="login-visual__glow login-visual__glow--one" />
        <div className="login-visual__glow login-visual__glow--two" />
        <Brand />
        <div className="login-visual__copy">
          <span className="login-kicker">Operação acadêmica controlada</span>
          <h1>Decisões humanas em cada etapa crítica do voo.</h1>
          <p>
            Analise o ponto de entrega, revise a missão e autorize o voo em etapas
            independentes e auditáveis.
          </p>
        </div>
        <div className="login-safety">
          <ShieldCheck size={22} aria-hidden="true" />
          <span>
            Este painel não arma o veículo automaticamente e nunca substitui o
            operador responsável.
          </span>
        </div>
      </section>

      <section className="login-form-panel">
        <div className="login-form-wrap">
          <div className="login-mobile-brand"><Brand compact /></div>
          <header className="login-form-header">
            <span className="login-form-icon"><LockKeyhole size={24} /></span>
            <h2>Acesso administrativo</h2>
            <p>Entre com uma conta que possua a função ADMIN.</p>
          </header>

          {appConfig.demoMode ? (
            <Feedback tone="warning">
              <strong>Modo demonstração ativo.</strong>
              <p>Dados locais; nenhuma ação alcança backend, gateway ou drone.</p>
            </Feedback>
          ) : null}
          {error ? <Feedback tone="error">{error}</Feedback> : null}

          <form className="login-form" onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="email">E-mail administrativo</label>
              <div className="input-wrap">
                <Mail size={20} aria-hidden="true" />
                <input
                  className="input"
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="username"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="admin@exemplo.local"
                />
              </div>
            </div>
            <div className="field">
              <label htmlFor="password">Senha</label>
              <div className="input-wrap password-input">
                <LockKeyhole size={20} aria-hidden="true" />
                <input
                  className="input"
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Digite sua senha"
                />
                <button
                  className="password-toggle"
                  type="button"
                  onClick={() => setShowPassword((current) => !current)}
                  aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                >
                  {showPassword ? <EyeOff size={19} /> : <Eye size={19} />}
                </button>
              </div>
            </div>
            <Button type="submit" fullWidth loading={isSubmitting}>
              Entrar no centro de operações
            </Button>
          </form>
          <p className="login-footnote">
            Não existe cadastro público de administradores. Solicite acesso ao
            responsável pelo ambiente.
          </p>
        </div>
      </section>
    </main>
  );
}
