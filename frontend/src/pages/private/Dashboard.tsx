import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { BarChart3, ChevronDown, Loader2, Briefcase } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getPortfolios, type Portfolio } from '@/services/portfolioService';

export function Dashboard() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<number | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const {
    data: portfolios = [],
    isLoading,
  } = useQuery({
    queryKey: ['portfolios'],
    queryFn: getPortfolios,
  });

  const selectedPortfolio = portfolios.find((p) => p.id === selectedPortfolioId) ?? null;

  const handleSelect = (portfolio: Portfolio) => {
    setSelectedPortfolioId(portfolio.id);
    setDropdownOpen(false);
  };

  const handleAnalyze = () => {
    if (!selectedPortfolio) return;
    navigate(`/portfolio/${selectedPortfolio.slug}/analyze`);
  };

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold">{t('dashboard.title')}</h1>
        <p
          className="text-sm mt-1"
          style={{ color: 'hsl(var(--muted-foreground))' }}
        >
          {t('dashboard.subtitle')}
        </p>
      </div>

      {/* Portfolio Selector Card */}
      <div
        className="rounded-xl border p-6 shadow-sm"
        style={{
          borderColor: 'hsl(var(--border))',
          backgroundColor: 'hsl(var(--card))',
        }}
      >
        <h2 className="text-lg font-semibold mb-4">{t('dashboard.selectPortfolio')}</h2>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
          </div>
        ) : portfolios.length === 0 ? (
          /* Empty state */
          <div
            className="rounded-lg border-2 border-dashed p-8 text-center"
            style={{ borderColor: 'hsl(var(--border))' }}
          >
            <div
              className="mx-auto w-12 h-12 rounded-full flex items-center justify-center mb-3"
              style={{ backgroundColor: 'hsl(var(--primary) / 0.1)' }}
            >
              <Briefcase className="h-6 w-6 text-primary" />
            </div>
            <p
              className="text-sm mb-4"
              style={{ color: 'hsl(var(--muted-foreground))' }}
            >
              {t('dashboard.noPortfolios')}
            </p>
            <Button
              size="sm"
              onClick={() => navigate('/my-portfolios')}
            >
              {t('dashboard.goToPortfolios')}
            </Button>
          </div>
        ) : (
          /* Selector + Analyze */
          <div className="flex flex-col sm:flex-row gap-4">
            {/* Custom dropdown */}
            <div className="relative flex-1">
              <button
                type="button"
                onClick={() => setDropdownOpen((o) => !o)}
                className="flex w-full items-center justify-between rounded-lg border px-4 py-2.5 text-sm transition-colors hover:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
                style={{
                  borderColor: 'hsl(var(--border))',
                  backgroundColor: 'hsl(var(--background))',
                }}
              >
                <span
                  style={{
                    color: selectedPortfolio
                      ? 'hsl(var(--foreground))'
                      : 'hsl(var(--muted-foreground))',
                  }}
                >
                  {selectedPortfolio
                    ? selectedPortfolio.name
                    : t('dashboard.dropdownPlaceholder')}
                </span>
                <ChevronDown
                  className={`h-4 w-4 ml-2 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`}
                  style={{ color: 'hsl(var(--muted-foreground))' }}
                />
              </button>

              {dropdownOpen && (
                <ul
                  className="absolute z-10 mt-1 w-full rounded-lg border shadow-lg overflow-hidden"
                  style={{
                    borderColor: 'hsl(var(--border))',
                    backgroundColor: 'hsl(var(--popover))',
                  }}
                >
                  {portfolios.map((p) => (
                    <li key={p.id}>
                      <button
                        type="button"
                        onClick={() => handleSelect(p)}
                        className="flex w-full items-center gap-3 px-4 py-2.5 text-sm transition-colors hover:bg-accent"
                        style={{
                          backgroundColor:
                            p.id === selectedPortfolioId
                              ? 'hsl(var(--accent))'
                              : undefined,
                        }}
                      >
                        <Briefcase className="h-4 w-4 text-primary shrink-0" />
                        <span className="truncate">{p.name}</span>
                        <span
                          className="ml-auto text-xs"
                          style={{ color: 'hsl(var(--muted-foreground))' }}
                        >
                          {p.transaction_count ?? 0} {t('dashboard.txns')}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Analyze button */}
            <Button
              onClick={handleAnalyze}
              disabled={!selectedPortfolio}
              className="gap-2"
            >
              <BarChart3 className="h-4 w-4" />
              {t('dashboard.analyze')}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
