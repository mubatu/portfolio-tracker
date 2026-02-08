import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { analyzePortfolio, getPortfolioBySlug } from '@/services/portfolioService';

export function PortfolioAnalyze() {
  const { slug } = useParams<{ slug: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();

  const {
    data: portfolio,
    isLoading: isPortfolioLoading,
  } = useQuery({
    queryKey: ['portfolio', slug],
    queryFn: () => getPortfolioBySlug(slug!),
    enabled: !!slug,
  });

  const {
    data: analysis,
    isLoading: isAnalysisLoading,
  } = useQuery({
    queryKey: ['portfolio-analysis', portfolio?.id],
    queryFn: () => analyzePortfolio(portfolio!.id),
    enabled: !!portfolio?.id,
  });

  const isLoading = isPortfolioLoading || isAnalysisLoading;

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Back button */}
      <Button
        variant="ghost"
        size="sm"
        className="gap-1 mb-6"
        onClick={() => navigate('/dashboard')}
      >
        <ArrowLeft className="h-4 w-4" />
        {t('dashboard.backToDashboard')}
      </Button>

      <h1 className="text-3xl font-bold mb-2">
        {portfolio?.name
          ? t('dashboard.analysisTitle', { name: portfolio.name })
          : t('dashboard.title')}
      </h1>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : (
        <div
          className="rounded-xl border p-8 mt-6 text-center"
          style={{
            borderColor: 'hsl(var(--border))',
            backgroundColor: 'hsl(var(--card))',
          }}
        >
          <p style={{ color: 'hsl(var(--muted-foreground))' }}>
            {analysis?.message ?? t('dashboard.analysisPlaceholder')}
          </p>
        </div>
      )}
    </div>
  );
}
