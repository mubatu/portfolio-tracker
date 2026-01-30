import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

export function PortfolioDetail() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  
  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">{t('portfolio.title')}</h1>
      <p style={{ color: 'hsl(var(--muted-foreground))' }}>
        {t('portfolio.viewing', { id })}
      </p>
    </div>
  );
}
