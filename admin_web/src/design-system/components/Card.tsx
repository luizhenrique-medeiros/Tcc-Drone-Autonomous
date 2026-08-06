import type { HTMLAttributes, ReactNode } from 'react';

interface CardProps extends Omit<HTMLAttributes<HTMLElement>, 'title'> {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
}

export function Card({
  title,
  action,
  className = '',
  children,
  ...props
}: CardProps) {
  return (
    <section className={`card ${className}`.trim()} {...props}>
      {title || action ? (
        <header className="card__header">
          {typeof title === 'string' ? <h2>{title}</h2> : title}
          {action}
        </header>
      ) : null}
      <div className="card__body">{children}</div>
    </section>
  );
}
