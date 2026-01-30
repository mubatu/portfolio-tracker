import { useTranslation } from 'react-i18next';

export function Dashboard() {
  const { t } = useTranslation();

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">{t('dashboard.title')}</h1>
      <p style={{ color: 'hsl(var(--muted-foreground))' }}>
        {t('dashboard.placeholder')}
      </p>
    </div>
  );
}
