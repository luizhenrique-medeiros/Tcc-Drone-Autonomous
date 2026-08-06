import { Check, Download, ShieldAlert, Trash2 } from 'lucide-react';
import {
  Button,
  Card,
  Feedback,
  PageHeader,
  StatusBadge,
} from '../components';

const swatches = [
  ['Azul operacional', 'var(--color-brand-blue-700)', '#2867BD'],
  ['Laranja de ação crítica', 'var(--color-brand-orange-500)', '#FF7A00'],
  ['Tinta principal', 'var(--color-ink-950)', '#18243A'],
  ['Sucesso', 'var(--color-success-700)', '#157A5A'],
  ['Atenção', 'var(--color-warning-700)', '#9A6100'],
  ['Falha', 'var(--color-danger-700)', '#B52D3E'],
];

export function DesignSystemPage() {
  return (
    <>
      <PageHeader
        eyebrow="Somente desenvolvimento"
        title="Catálogo do design system"
        description="Tokens e componentes reutilizados pelo painel. Esta rota não é incluída na navegação de produção."
      />
      <div className="catalog-grid">
        <Card title="Cores semânticas" className="catalog-span-2">
          <div className="swatches">
            {swatches.map(([name, color, hex]) => (
              <article className="swatch" key={name}>
                <span style={{ background: color }} />
                <strong>{name}</strong>
                <small className="mono">{hex}</small>
              </article>
            ))}
          </div>
        </Card>
        <Card title="Botões">
          <div className="stack">
            <Button><Check size={17} /> Ação principal</Button>
            <Button variant="warning"><ShieldAlert size={17} /> Ação crítica</Button>
            <Button variant="secondary"><Download size={17} /> Secundária</Button>
            <Button variant="danger"><Trash2 size={17} /> Destrutiva</Button>
            <Button disabled>Indisponível</Button>
          </div>
        </Card>
        <Card title="Estados">
          <div className="stack">
            <StatusBadge status="PENDING_ADMIN_APPROVAL" />
            <StatusBadge status="READY_FOR_AUTHORIZATION" />
            <StatusBadge status="EXECUTING" />
            <StatusBadge status="COMPLETED" />
            <StatusBadge status="FAILED" />
            <StatusBadge status="ONLINE" />
          </div>
        </Card>
        <Card title="Mensagens" className="catalog-span-2">
          <div className="stack">
            <Feedback>Informação operacional neutra.</Feedback>
            <Feedback tone="success">Etapa concluída e auditada.</Feedback>
            <Feedback tone="warning">Confirmação humana necessária.</Feedback>
            <Feedback tone="error">Bloqueio que impede autorização.</Feedback>
          </div>
        </Card>
        <Card title="Formulário" className="catalog-span-2">
          <div className="catalog-form">
            <div className="field"><label htmlFor="catalog-text">Campo de texto</label><input className="input" id="catalog-text" placeholder="Conteúdo operacional" /></div>
            <div className="field"><label htmlFor="catalog-select">Seleção</label><select className="select" id="catalog-select"><option>Opção segura</option></select></div>
            <div className="field catalog-form__full"><label htmlFor="catalog-area">Área de texto</label><textarea className="textarea" id="catalog-area" placeholder="Justificativa auditável" /></div>
          </div>
        </Card>
      </div>
    </>
  );
}
