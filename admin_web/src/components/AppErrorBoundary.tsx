import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';

interface State {
  hasError: boolean;
}

export class AppErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (import.meta.env.DEV) console.error('Erro não tratado na interface', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="fatal-error">
          <AlertTriangle size={42} />
          <h1>O painel encontrou um erro inesperado</h1>
          <p>Nenhuma ação crítica foi reenviada automaticamente.</p>
          <button className="button" type="button" onClick={() => window.location.reload()}>
            Recarregar o painel
          </button>
        </main>
      );
    }
    return this.props.children;
  }
}
