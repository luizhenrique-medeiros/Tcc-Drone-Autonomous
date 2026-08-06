import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Brand } from '../src/components/Brand';

describe('marca DevCore', () => {
  it('usa a imagem original com alternativa acessível', () => {
    render(<Brand />);
    const logo = screen.getByRole('img', { name: /DevCore — drone de entregas/i });
    expect(logo).toHaveAttribute('src', '/devcore-logo-source.png');
    expect(screen.getByText('Centro de operações')).toBeInTheDocument();
  });
});
