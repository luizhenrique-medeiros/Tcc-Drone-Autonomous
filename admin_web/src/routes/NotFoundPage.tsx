import { Compass } from 'lucide-react';
import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <div className="not-found">
      <span><Compass size={30} /></span>
      <h1>Página não encontrada</h1>
      <p>O endereço não pertence ao centro de operações.</p>
      <Link className="button" to="/">Voltar à visão geral</Link>
    </div>
  );
}
