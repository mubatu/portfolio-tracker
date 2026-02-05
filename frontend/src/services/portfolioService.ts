import { supabase } from '@/lib/supabase';
import { type Market } from '@/config';

export interface Portfolio {
  id: number;
  user_id: string;
  name: string;
  created_at: string;
  transaction_count?: number;
}

export interface Transaction {
  id: number;
  portfolio_id: number;
  ticker: string;
  operation: 'buy' | 'sell';
  market: Market;
  quantity: number;
  price: number;
  date: string;
  created_at: string;
}

export interface CreatePortfolioInput {
  name: string;
}

export interface CreateTransactionInput {
  portfolio_id: number;
  ticker: string;
  operation: 'buy' | 'sell';
  market: Market;
  quantity: number;
  price: number;
  date: string;
}

// Portfolio CRUD operations
export async function getPortfolios(): Promise<Portfolio[]> {
  const { data: { user } } = await supabase.auth.getUser();
  
  if (!user) {
    throw new Error('User not authenticated');
  }

  // Get portfolios with transaction count
  const { data: portfolios, error } = await supabase
    .from('portfolios')
    .select(`
      *,
      transactions:transactions(count)
    `)
    .eq('user_id', user.id)
    .order('created_at', { ascending: false });

  if (error) {
    throw new Error(error.message);
  }

  // Transform the data to include transaction_count
  return (portfolios || []).map((p: any) => ({
    ...p,
    transaction_count: p.transactions?.[0]?.count || 0,
  }));
}

export async function getPortfolio(id: number): Promise<Portfolio | null> {
  const { data: { user } } = await supabase.auth.getUser();
  
  if (!user) {
    throw new Error('User not authenticated');
  }

  const { data, error } = await supabase
    .from('portfolios')
    .select('*')
    .eq('id', id)
    .eq('user_id', user.id)
    .single();

  if (error) {
    if (error.code === 'PGRST116') {
      return null; // Not found
    }
    throw new Error(error.message);
  }

  return data;
}

export async function createPortfolio(input: CreatePortfolioInput): Promise<Portfolio> {
  const { data: { user } } = await supabase.auth.getUser();
  
  if (!user) {
    throw new Error('User not authenticated');
  }

  const { data, error } = await supabase
    .from('portfolios')
    .insert({
      name: input.name,
      user_id: user.id,
    })
    .select()
    .single();

  if (error) {
    throw new Error(error.message);
  }

  return data;
}

export async function deletePortfolio(id: number): Promise<void> {
  const { data: { user } } = await supabase.auth.getUser();
  
  if (!user) {
    throw new Error('User not authenticated');
  }

  const { error } = await supabase
    .from('portfolios')
    .delete()
    .eq('id', id)
    .eq('user_id', user.id);

  if (error) {
    throw new Error(error.message);
  }
}

// Transaction CRUD operations
export async function getTransactions(portfolioId: number): Promise<Transaction[]> {
  const { data: { user } } = await supabase.auth.getUser();
  
  if (!user) {
    throw new Error('User not authenticated');
  }

  // First verify the portfolio belongs to the user
  const portfolio = await getPortfolio(portfolioId);
  if (!portfolio) {
    throw new Error('Portfolio not found');
  }

  const { data, error } = await supabase
    .from('transactions')
    .select('*')
    .eq('portfolio_id', portfolioId)
    .order('date', { ascending: false });

  if (error) {
    throw new Error(error.message);
  }

  return data || [];
}

export async function createTransaction(input: CreateTransactionInput): Promise<Transaction> {
  const { data: { user } } = await supabase.auth.getUser();
  
  if (!user) {
    throw new Error('User not authenticated');
  }

  // First verify the portfolio belongs to the user
  const portfolio = await getPortfolio(input.portfolio_id);
  if (!portfolio) {
    throw new Error('Portfolio not found');
  }

  const { data, error } = await supabase
    .from('transactions')
    .insert({
      portfolio_id: input.portfolio_id,
      ticker: input.ticker.toUpperCase(),
      operation: input.operation,
      market: input.market,
      quantity: input.quantity,
      price: input.price,
      date: input.date,
    })
    .select()
    .single();

  if (error) {
    throw new Error(error.message);
  }

  return data;
}

export async function deleteTransaction(id: number): Promise<void> {
  const { data: { user } } = await supabase.auth.getUser();
  
  if (!user) {
    throw new Error('User not authenticated');
  }

  // Get the transaction to verify ownership through portfolio
  const { data: transaction, error: fetchError } = await supabase
    .from('transactions')
    .select('portfolio_id')
    .eq('id', id)
    .single();

  if (fetchError) {
    throw new Error(fetchError.message);
  }

  // Verify the portfolio belongs to the user
  const portfolio = await getPortfolio(transaction.portfolio_id);
  if (!portfolio) {
    throw new Error('Transaction not found');
  }

  const { error } = await supabase
    .from('transactions')
    .delete()
    .eq('id', id);

  if (error) {
    throw new Error(error.message);
  }
}
