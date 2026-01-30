import { useTranslation } from 'react-i18next';
import { Header } from '@/components/layout';

export function RegisterPage() {
  const { t } = useTranslation();

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 flex items-center justify-center">
        <div className="w-full max-w-md p-8">
          <h1 className="text-2xl font-bold text-center mb-6">{t('auth.register.title')}</h1>
          <p className="text-center" style={{ color: 'hsl(var(--muted-foreground))' }}>
            {t('auth.register.placeholder')}
          </p>
        </div>
      </main>
    </div>
  );
}
