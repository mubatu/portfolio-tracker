import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  Plus,
  Loader2,
  Trash2,
  Pencil,
  TrendingUp,
  TrendingDown,
  Calendar,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Modal } from '@/components/ui/Modal';
import {
  getPortfolio,
  getTransactions,
  createTransaction,
  updateTransaction,
  deleteTransaction,
  type Transaction,
} from '@/services/portfolioService';
import {
  MARKETS,
  getMarketCurrency,
  getLocale,
  type Market,
} from '@/config';

export function PortfolioDetail() {
  const { t, i18n } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const portfolioId = Number(id);

  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState<Transaction | null>(null);
  const [addError, setAddError] = useState('');
  const [editError, setEditError] = useState('');

  // Form state for new transaction
  const [ticker, setTicker] = useState('');
  const [operation, setOperation] = useState<'buy' | 'sell'>('buy');
  const [market, setMarket] = useState<Market>('BIST');
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);

  // Fetch portfolio details
  const {
    data: portfolio,
    isLoading: portfolioLoading,
    error: portfolioError,
  } = useQuery({
    queryKey: ['portfolio', portfolioId],
    queryFn: () => getPortfolio(portfolioId),
    enabled: !isNaN(portfolioId),
  });

  // Fetch transactions
  const {
    data: transactions = [],
    isLoading: transactionsLoading,
    error: transactionsError,
  } = useQuery({
    queryKey: ['transactions', portfolioId],
    queryFn: () => getTransactions(portfolioId),
    enabled: !isNaN(portfolioId) && !!portfolio,
  });

  // Create transaction mutation
  const createMutation = useMutation({
    mutationFn: createTransaction,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions', portfolioId] });
      queryClient.invalidateQueries({ queryKey: ['portfolios'] });
      closeAddModal();
    },
    onError: (error: Error) => {
      setAddError(error.message);
    },
  });

  // Delete transaction mutation
  const deleteMutation = useMutation({
    mutationFn: deleteTransaction,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions', portfolioId] });
      queryClient.invalidateQueries({ queryKey: ['portfolios'] });
    },
  });

  // Update transaction mutation
  const updateMutation = useMutation({
    mutationFn: updateTransaction,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions', portfolioId] });
      queryClient.invalidateQueries({ queryKey: ['portfolios'] });
      closeEditModal();
    },
    onError: (error: Error) => {
      setEditError(error.message);
    },
  });

  const closeAddModal = () => {
    setIsAddModalOpen(false);
    setTicker('');
    setOperation('buy');
    setMarket('BIST');
    setQuantity('');
    setPrice('');
    setDate(new Date().toISOString().split('T')[0]);
    setAddError('');
  };

  const openEditModal = (transaction: Transaction) => {
    setEditingTransaction(transaction);
    setTicker(transaction.ticker);
    setOperation(transaction.operation);
    setMarket(transaction.market);
    setQuantity(String(transaction.quantity));
    setPrice(String(transaction.price));
    setDate(transaction.date);
    setIsEditModalOpen(true);
  };

  const closeEditModal = () => {
    setIsEditModalOpen(false);
    setEditingTransaction(null);
    setTicker('');
    setOperation('buy');
    setMarket('BIST');
    setQuantity('');
    setPrice('');
    setDate(new Date().toISOString().split('T')[0]);
    setEditError('');
  };

  const handleAddSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (ticker && quantity && price && date) {
      createMutation.mutate({
        portfolio_id: portfolioId,
        ticker: ticker.toUpperCase(),
        operation,
        market,
        quantity: parseFloat(quantity),
        price: parseFloat(price),
        date,
      });
    }
  };

  const handleDeleteTransaction = (transactionId: number) => {
    deleteMutation.mutate(transactionId);
  };

  const handleEditSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (editingTransaction && ticker && quantity && price && date) {
      updateMutation.mutate({
        id: editingTransaction.id,
        ticker: ticker.toUpperCase(),
        operation,
        market,
        quantity: parseFloat(quantity),
        price: parseFloat(price),
        date,
      });
    }
  };

  const formatCurrency = (value: number, currency: string = 'TRY') => {
    return new Intl.NumberFormat(getLocale(i18n.language), {
      style: 'currency',
      currency,
    }).format(value);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const isLoading = portfolioLoading || transactionsLoading;
  const error = portfolioError || transactionsError;

  // Not found state
  if (!isLoading && !portfolio) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Button
          variant="ghost"
          onClick={() => navigate('/my-portfolios')}
          className="gap-2 mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('portfolio.back')}
        </Button>
        <div
          className="rounded-lg border p-8 text-center"
          style={{ borderColor: 'hsl(var(--border))' }}
        >
          <p style={{ color: 'hsl(var(--muted-foreground))' }}>
            Portfolio not found
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Back Button */}
      <Button
        variant="ghost"
        onClick={() => navigate('/my-portfolios')}
        className="gap-2 mb-6"
      >
        <ArrowLeft className="h-4 w-4" />
        {t('portfolio.back')}
      </Button>

      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      )}

      {/* Error State */}
      {error && (
        <div
          className="rounded-lg border p-4 text-center"
          style={{
            borderColor: 'hsl(var(--destructive))',
            backgroundColor: 'hsl(var(--destructive) / 0.1)',
          }}
        >
          <p style={{ color: 'hsl(var(--destructive))' }}>
            {t('common.error')}: {(error as Error).message}
          </p>
        </div>
      )}

      {/* Portfolio Content */}
      {!isLoading && portfolio && (
        <>
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
            <div>
              <h1 className="text-3xl font-bold">{portfolio.name}</h1>
              <p
                className="text-sm mt-1 flex items-center gap-2"
                style={{ color: 'hsl(var(--muted-foreground))' }}
              >
                <Calendar className="h-4 w-4" />
                Created {formatDate(portfolio.created_at)}
              </p>
            </div>
            <Button onClick={() => setIsAddModalOpen(true)} className="gap-2">
              <Plus className="h-4 w-4" />
              {t('portfolio.addTransaction')}
            </Button>
          </div>

          {/* Transactions Section */}
          <div>
            <h2 className="text-xl font-semibold mb-4">
              {t('portfolio.transactions.title')}
            </h2>

            {/* Empty State */}
            {transactions.length === 0 && (
              <div
                className="rounded-lg border-2 border-dashed p-8 text-center"
                style={{ borderColor: 'hsl(var(--border))' }}
              >
                <div
                  className="mx-auto w-12 h-12 rounded-full flex items-center justify-center mb-3"
                  style={{ backgroundColor: 'hsl(var(--primary) / 0.1)' }}
                >
                  <TrendingUp className="h-6 w-6 text-primary" />
                </div>
                <h3 className="font-semibold mb-1">
                  {t('portfolio.transactions.empty.title')}
                </h3>
                <p
                  className="text-sm mb-4 max-w-sm mx-auto"
                  style={{ color: 'hsl(var(--muted-foreground))' }}
                >
                  {t('portfolio.transactions.empty.description')}
                </p>
                <Button
                  onClick={() => setIsAddModalOpen(true)}
                  className="gap-2"
                >
                  <Plus className="h-4 w-4" />
                  {t('portfolio.addTransaction')}
                </Button>
              </div>
            )}

            {/* Transactions Table */}
            {transactions.length > 0 && (
              <div
                className="rounded-lg border overflow-hidden"
                style={{ borderColor: 'hsl(var(--border))' }}
              >
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr
                        style={{
                          backgroundColor: 'hsl(var(--muted) / 0.5)',
                        }}
                      >
                        <th className="text-left px-4 py-3 text-sm font-medium">
                          {t('portfolio.transactions.ticker')}
                        </th>
                        <th className="text-left px-4 py-3 text-sm font-medium">
                          {t('portfolio.transactions.market')}
                        </th>
                        <th className="text-left px-4 py-3 text-sm font-medium">
                          {t('portfolio.transactions.operation')}
                        </th>
                        <th className="text-right px-4 py-3 text-sm font-medium">
                          {t('portfolio.transactions.quantity')}
                        </th>
                        <th className="text-right px-4 py-3 text-sm font-medium">
                          {t('portfolio.transactions.price')}
                        </th>
                        <th className="text-right px-4 py-3 text-sm font-medium">
                          {t('portfolio.transactions.total')}
                        </th>
                        <th className="text-left px-4 py-3 text-sm font-medium">
                          {t('portfolio.transactions.date')}
                        </th>
                        <th className="px-4 py-3 text-sm font-medium w-10"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {transactions.map((transaction) => (
                        <tr
                          key={transaction.id}
                          className="border-t transition-colors hover:bg-muted/50"
                          style={{ borderColor: 'hsl(var(--border))' }}
                        >
                          <td className="px-4 py-3">
                            <span className="font-semibold">
                              {transaction.ticker}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                              style={{
                                backgroundColor: 'hsl(var(--muted))',
                              }}
                            >
                              {transaction.market}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
                              style={{
                                backgroundColor:
                                  transaction.operation === 'buy'
                                    ? 'hsl(142 76% 36% / 0.1)'
                                    : 'hsl(0 84% 60% / 0.1)',
                                color:
                                  transaction.operation === 'buy'
                                    ? 'hsl(142 76% 36%)'
                                    : 'hsl(0 84% 60%)',
                              }}
                            >
                              {transaction.operation === 'buy' ? (
                                <TrendingUp className="h-3 w-3" />
                              ) : (
                                <TrendingDown className="h-3 w-3" />
                              )}
                              {t(`portfolio.transactions.${transaction.operation}`)}
                            </span>
                          </td>
                          <td className="text-right px-4 py-3">
                            {Number(transaction.quantity).toLocaleString()}
                          </td>
                          <td className="text-right px-4 py-3">
                            {formatCurrency(Number(transaction.price), getMarketCurrency(transaction.market))}
                          </td>
                          <td className="text-right px-4 py-3 font-medium">
                            {formatCurrency(
                              Number(transaction.quantity) *
                                Number(transaction.price),
                              getMarketCurrency(transaction.market)
                            )}
                          </td>
                          <td
                            className="px-4 py-3 text-sm"
                            style={{ color: 'hsl(var(--muted-foreground))' }}
                          >
                            {formatDate(transaction.date)}
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-1">
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={() => openEditModal(transaction)}
                              >
                                <Pencil
                                  className="h-4 w-4"
                                  style={{ color: 'hsl(var(--muted-foreground))' }}
                                />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={() =>
                                  handleDeleteTransaction(transaction.id)
                                }
                                disabled={deleteMutation.isPending}
                              >
                                <Trash2
                                  className="h-4 w-4"
                                  style={{ color: 'hsl(var(--destructive))' }}
                                />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* Add Transaction Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={closeAddModal}
        title={t('portfolio.addTransactionModal.title')}
        footer={
          <>
            <Button variant="outline" onClick={closeAddModal}>
              {t('common.cancel')}
            </Button>
            <Button
              onClick={handleAddSubmit}
              disabled={
                !ticker ||
                !quantity ||
                !price ||
                !date ||
                createMutation.isPending
              }
            >
              {createMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                t('common.save')
              )}
            </Button>
          </>
        }
      >
        <form onSubmit={handleAddSubmit} className="space-y-4">
          {/* Market */}
          <div>
            <label htmlFor="market" className="block text-sm font-medium mb-2">
              {t('portfolio.addTransactionModal.marketLabel')}
            </label>
            <select
              id="market"
              value={market}
              onChange={(e) => setMarket(e.target.value as Market)}
              className="w-full px-3 py-2 rounded-md border bg-transparent"
              style={{ borderColor: 'hsl(var(--input))' }}
            >
              {MARKETS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          {/* Ticker */}
          <div>
            <label htmlFor="ticker" className="block text-sm font-medium mb-2">
              {t('portfolio.addTransactionModal.tickerLabel')}
            </label>
            <input
              id="ticker"
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder={t('portfolio.addTransactionModal.tickerPlaceholder')}
              autoFocus
              className="w-full px-3 py-2 rounded-md border bg-transparent uppercase"
              style={{ borderColor: 'hsl(var(--input))' }}
            />
          </div>

          {/* Operation */}
          <div>
            <label className="block text-sm font-medium mb-2">
              {t('portfolio.addTransactionModal.operationLabel')}
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setOperation('buy')}
                className="flex-1 py-2 px-4 rounded-md border text-sm font-medium transition-colors"
                style={{
                  borderColor:
                    operation === 'buy'
                      ? 'hsl(142 76% 36%)'
                      : 'hsl(var(--input))',
                  backgroundColor:
                    operation === 'buy'
                      ? 'hsl(142 76% 36% / 0.1)'
                      : 'transparent',
                  color:
                    operation === 'buy'
                      ? 'hsl(142 76% 36%)'
                      : 'hsl(var(--foreground))',
                }}
              >
                {t('portfolio.transactions.buy')}
              </button>
              <button
                type="button"
                onClick={() => setOperation('sell')}
                className="flex-1 py-2 px-4 rounded-md border text-sm font-medium transition-colors"
                style={{
                  borderColor:
                    operation === 'sell'
                      ? 'hsl(0 84% 60%)'
                      : 'hsl(var(--input))',
                  backgroundColor:
                    operation === 'sell'
                      ? 'hsl(0 84% 60% / 0.1)'
                      : 'transparent',
                  color:
                    operation === 'sell'
                      ? 'hsl(0 84% 60%)'
                      : 'hsl(var(--foreground))',
                }}
              >
                {t('portfolio.transactions.sell')}
              </button>
            </div>
          </div>

          {/* Quantity & Price */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label
                htmlFor="quantity"
                className="block text-sm font-medium mb-2"
              >
                {t('portfolio.addTransactionModal.quantityLabel')}
              </label>
              <input
                id="quantity"
                type="number"
                step="any"
                min="0"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder={t(
                  'portfolio.addTransactionModal.quantityPlaceholder'
                )}
                className="w-full px-3 py-2 rounded-md border bg-transparent"
                style={{ borderColor: 'hsl(var(--input))' }}
              />
            </div>
            <div>
              <label htmlFor="price" className="block text-sm font-medium mb-2">
                {t('portfolio.addTransactionModal.priceLabel')}
              </label>
              <input
                id="price"
                type="number"
                step="any"
                min="0"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder={t('portfolio.addTransactionModal.pricePlaceholder')}
                className="w-full px-3 py-2 rounded-md border bg-transparent"
                style={{ borderColor: 'hsl(var(--input))' }}
              />
            </div>
          </div>

          {/* Date */}
          <div>
            <label htmlFor="date" className="block text-sm font-medium mb-2">
              {t('portfolio.addTransactionModal.dateLabel')}
            </label>
            <input
              id="date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full px-3 py-2 rounded-md border bg-transparent"
              style={{ borderColor: 'hsl(var(--input))' }}
            />
          </div>

          {addError && (
            <p className="text-sm" style={{ color: 'hsl(var(--destructive))' }}>
              {addError}
            </p>
          )}
        </form>
      </Modal>

      {/* Edit Transaction Modal */}
      <Modal
        isOpen={isEditModalOpen}
        onClose={closeEditModal}
        title={t('portfolio.editTransactionModal.title')}
        footer={
          <>
            <Button variant="outline" onClick={closeEditModal}>
              {t('common.cancel')}
            </Button>
            <Button
              onClick={handleEditSubmit}
              disabled={
                !ticker ||
                !quantity ||
                !price ||
                !date ||
                updateMutation.isPending
              }
            >
              {updateMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                t('common.save')
              )}
            </Button>
          </>
        }
      >
        <form onSubmit={handleEditSubmit} className="space-y-4">
          {/* Market */}
          <div>
            <label htmlFor="edit-market" className="block text-sm font-medium mb-2">
              {t('portfolio.addTransactionModal.marketLabel')}
            </label>
            <select
              id="edit-market"
              value={market}
              onChange={(e) => setMarket(e.target.value as Market)}
              className="w-full px-3 py-2 rounded-md border bg-transparent"
              style={{ borderColor: 'hsl(var(--input))' }}
            >
              {MARKETS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          {/* Ticker */}
          <div>
            <label htmlFor="edit-ticker" className="block text-sm font-medium mb-2">
              {t('portfolio.addTransactionModal.tickerLabel')}
            </label>
            <input
              id="edit-ticker"
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder={t('portfolio.addTransactionModal.tickerPlaceholder')}
              className="w-full px-3 py-2 rounded-md border bg-transparent uppercase"
              style={{ borderColor: 'hsl(var(--input))' }}
            />
          </div>

          {/* Operation */}
          <div>
            <label className="block text-sm font-medium mb-2">
              {t('portfolio.addTransactionModal.operationLabel')}
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setOperation('buy')}
                className="flex-1 py-2 px-4 rounded-md border text-sm font-medium transition-colors"
                style={{
                  borderColor:
                    operation === 'buy'
                      ? 'hsl(142 76% 36%)'
                      : 'hsl(var(--input))',
                  backgroundColor:
                    operation === 'buy'
                      ? 'hsl(142 76% 36% / 0.1)'
                      : 'transparent',
                  color:
                    operation === 'buy'
                      ? 'hsl(142 76% 36%)'
                      : 'hsl(var(--foreground))',
                }}
              >
                {t('portfolio.transactions.buy')}
              </button>
              <button
                type="button"
                onClick={() => setOperation('sell')}
                className="flex-1 py-2 px-4 rounded-md border text-sm font-medium transition-colors"
                style={{
                  borderColor:
                    operation === 'sell'
                      ? 'hsl(0 84% 60%)'
                      : 'hsl(var(--input))',
                  backgroundColor:
                    operation === 'sell'
                      ? 'hsl(0 84% 60% / 0.1)'
                      : 'transparent',
                  color:
                    operation === 'sell'
                      ? 'hsl(0 84% 60%)'
                      : 'hsl(var(--foreground))',
                }}
              >
                {t('portfolio.transactions.sell')}
              </button>
            </div>
          </div>

          {/* Quantity & Price */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label
                htmlFor="edit-quantity"
                className="block text-sm font-medium mb-2"
              >
                {t('portfolio.addTransactionModal.quantityLabel')}
              </label>
              <input
                id="edit-quantity"
                type="number"
                step="any"
                min="0"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder={t(
                  'portfolio.addTransactionModal.quantityPlaceholder'
                )}
                className="w-full px-3 py-2 rounded-md border bg-transparent"
                style={{ borderColor: 'hsl(var(--input))' }}
              />
            </div>
            <div>
              <label htmlFor="edit-price" className="block text-sm font-medium mb-2">
                {t('portfolio.addTransactionModal.priceLabel')}
              </label>
              <input
                id="edit-price"
                type="number"
                step="any"
                min="0"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder={t('portfolio.addTransactionModal.pricePlaceholder')}
                className="w-full px-3 py-2 rounded-md border bg-transparent"
                style={{ borderColor: 'hsl(var(--input))' }}
              />
            </div>
          </div>

          {/* Date */}
          <div>
            <label htmlFor="edit-date" className="block text-sm font-medium mb-2">
              {t('portfolio.addTransactionModal.dateLabel')}
            </label>
            <input
              id="edit-date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full px-3 py-2 rounded-md border bg-transparent"
              style={{ borderColor: 'hsl(var(--input))' }}
            />
          </div>

          {editError && (
            <p className="text-sm" style={{ color: 'hsl(var(--destructive))' }}>
              {editError}
            </p>
          )}
        </form>
      </Modal>
    </div>
  );
}

