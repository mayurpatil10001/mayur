import React, { useEffect, useState } from 'react';
import InteractiveChart from '../../components/InteractiveChart/InteractiveChart';
import TradingReadinessAssessment from '../../components/TradingReadinessAssessment';
import DragDropDashboard from '../../components/DragDropDashboard';
import StrategyValidationAnalytics from '../../components/StrategyValidationAnalytics';
import PerformanceBreakdown from '../../components/PerformanceBreakdown';
import './Recommendations.css';
import './MatrixOverride.css';
import { fetchRecommendations } from '../../store/slices/recommendationsSlice';

interface RecommendationMatrix {
  [timeSlot: string]: {
    [dayOfWeek: number]: {
      best_account: string;
      total_trades: number;
      total_pnl: number;
      avg_trade: number;
      win_rate: number;
    };
  };
}

interface BacktestData {
  date: string;
  daily_pnl: number;
  cumulative_pnl: number;
}

interface CombinedStats {
  symbol: string;
  recommended_accounts: string[];
  combined_metrics: {
    total_trades: number;
    total_pnl: number;
    avg_trade: number;
    win_rate: number;
    winning_trades: number;
    losing_trades: number;
    avg_winner: number;
    avg_loser: number;
    largest_winner: number;
    largest_loser: number;
    profit_factor: number;
    sharpe_ratio: number;
    max_drawdown: number;
    first_trade_date: string;
    last_trade_date: string;
  };
  account_breakdown: Array<{
    account_name: string;
    total_trades: number;
    total_pnl: number;
    avg_trade: number;
    win_rate: number;
  }>;
}

interface Symbol {
  symbol: string;
  total_trades: number;
  unique_accounts: number;
  first_trade: string;
  last_trade: string;
}

interface FilterSettings {
  minAvgProfit: number;
  minWinRate: number;
  minTrades: number;
}

interface CriteriaItem {
  label: string;
  current: number | string;
  target: number | string;
  unit?: string;
  status: 'good' | 'warning' | 'poor';
}

const Recommendations: React.FC = () => {
  const [symbols, setSymbols] = useState<Symbol[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string>('');
  const [matrix, setMatrix] = useState<RecommendationMatrix>({});
  const [backtestData, setBacktestData] = useState<BacktestData[]>([]);
  const [backtestMetadata, setBacktestMetadata] = useState<any>(null);
  const [combinedStats, setCombinedStats] = useState<CombinedStats | null>(null);
  const [timeFilteredStats, setTimeFilteredStats] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'matrix' | 'validation' | 'settings' | 'backtest'>('matrix');
  const [filterSettings, setFilterSettings] = useState<FilterSettings>({
    minAvgProfit: 12.0,  // Set to $12
    minWinRate: 45.0,    // Set to 45%
    minTrades: 100       // Set to 100 trades
  });
  const [timeHorizon, setTimeHorizon] = useState<string>('30');

  const [validationData, setValidationData] = useState<any>(null);
  const [isLoadingValidation, setIsLoadingValidation] = useState(false);

  // Sample data for Trading Readiness Assessment
  const getReadinessAssessmentData = () => {
    type CriteriaStatus = 'good' | 'warning' | 'poor';
    
    if (!combinedStats) {
      return {
        riskManagementCriteria: [
          { label: 'Risk-Reward Ratio', current: 'N/A', target: '≥1.5:1', status: 'poor' as CriteriaStatus },
          { label: 'Probability of Profit', current: 'N/A', target: '≥75%', status: 'poor' as CriteriaStatus },
          { label: 'Maximum Risk (VaR 95%)', current: 'N/A', target: '≤ $5,000', status: 'poor' as CriteriaStatus }
        ],
        performanceCriteria: [
          { label: 'Sharpe Ratio', current: 'N/A', target: '≥1.5', status: 'poor' as CriteriaStatus },
          { label: 'Win Rate', current: 'N/A', target: '≥60%', status: 'poor' as CriteriaStatus },
          { label: 'Profit Factor', current: 'N/A', target: '≥1.5', status: 'poor' as CriteriaStatus }
        ]
      };
    }

    const metrics = combinedStats.combined_metrics;
    
    // Calculate risk-reward ratio (simplified)
    const avgWinner = Math.abs(metrics.avg_winner || 0);
    const avgLoser = Math.abs(metrics.avg_loser || 0);
    const riskRewardRatio = avgLoser > 0 ? avgWinner / avgLoser : 0;
    
    // Calculate probability of profit (win rate as proxy)
    const probabilityOfProfit = metrics.win_rate || 0;
    
    // Estimate VaR (simplified as max drawdown)
    const maxRisk = Math.abs(metrics.max_drawdown || 0);
    
    // Helper function to determine status
    const getStatus = (value: number, goodThreshold: number, warningThreshold: number, isReverse = false): CriteriaStatus => {
      if (isReverse) {
        return value <= goodThreshold ? 'good' : value <= warningThreshold ? 'warning' : 'poor';
      }
      return value >= goodThreshold ? 'good' : value >= warningThreshold ? 'warning' : 'poor';
    };
    
    return {
      riskManagementCriteria: [
        { 
          label: 'Risk-Reward Ratio', 
          current: riskRewardRatio.toFixed(2), 
          target: '≥1.5', 
          unit: ':1',
          status: getStatus(riskRewardRatio, 1.5, 1.0)
        },
        { 
          label: 'Probability of Profit', 
          current: probabilityOfProfit.toFixed(1), 
          target: '≥75', 
          unit: '%',
          status: getStatus(probabilityOfProfit, 75, 60)
        },
        { 
          label: 'Maximum Risk (VaR 95%)', 
          current: `$${maxRisk.toLocaleString()}`, 
          target: '≤ $5,000', 
          status: getStatus(maxRisk, 5000, 10000, true)
        }
      ],
      performanceCriteria: [
        { 
          label: 'Sharpe Ratio', 
          current: (metrics.sharpe_ratio || 0).toFixed(2), 
          target: '≥1.5', 
          status: getStatus(metrics.sharpe_ratio || 0, 1.5, 1.0)
        },
        { 
          label: 'Win Rate', 
          current: (metrics.win_rate || 0).toFixed(1), 
          target: '≥60', 
          unit: '%',
          status: getStatus(metrics.win_rate || 0, 60, 50)
        },
        { 
          label: 'Profit Factor', 
          current: (metrics.profit_factor || 0).toFixed(2), 
          target: '≥1.5', 
          status: getStatus(metrics.profit_factor || 0, 1.5, 1.2)
        }
      ]
    };
  };

  // Strategy Validation Analytics data
  const getStrategyValidationData = () => {
    type ValidationColor = 'green' | 'blue' | 'orange' | 'red';
    type TrustStatus = 'good' | 'warning' | 'poor';
    
    if (!combinedStats) {
      return {
        metrics: [
          { label: 'Total P&L', value: 'N/A', icon: '💰', color: 'blue' as ValidationColor },
          { label: 'Win Rate', value: 'N/A', icon: '🎯', color: 'blue' as ValidationColor },
          { label: 'Avg Trade', value: 'N/A', icon: '📊', color: 'blue' as ValidationColor },
          { label: 'Sharpe Ratio', value: 'N/A', icon: '📈', color: 'blue' as ValidationColor }
        ],
        trustIndicators: [
          { title: 'Statistical Significance', description: 'Strategy shows significant performance', status: 'poor' as TrustStatus, details: 'Insufficient data' },
          { title: 'Sample Size Adequacy', description: 'Adequate sample size for reliable results', status: 'poor' as TrustStatus, details: 'Need more trades' },
          { title: 'Strategy Diversification', description: 'Strategy is well diversified across time periods', status: 'poor' as TrustStatus, details: 'Limited diversification' }
        ]
      };
    }

    const metrics = combinedStats.combined_metrics;
    
    const getValidationColor = (value: number, goodThreshold: number, warningThreshold: number, isReverse = false): ValidationColor => {
      if (isReverse) {
        return value <= goodThreshold ? 'green' : value <= warningThreshold ? 'orange' : 'red';
      }
      return value >= goodThreshold ? 'green' : value >= warningThreshold ? 'orange' : 'red';
    };
    
    const getTrustStatus = (value: number, goodThreshold: number, warningThreshold: number): TrustStatus => {
      return value >= goodThreshold ? 'good' : value >= warningThreshold ? 'warning' : 'poor';
    };
    
    return {
      metrics: [
        { 
          label: 'Total P&L', 
          value: `$${metrics.total_pnl?.toLocaleString() || '0'}`, 
          icon: '💰', 
          color: (metrics.total_pnl || 0) > 0 ? 'green' : 'red' as ValidationColor
        },
        { 
          label: 'Win Rate', 
          value: `${(metrics.win_rate || 0).toFixed(1)}%`, 
          icon: '🎯', 
          color: getValidationColor(metrics.win_rate || 0, 60, 50)
        },
        { 
          label: 'Avg Trade', 
          value: `$${(metrics.avg_trade || 0).toFixed(2)}`, 
          icon: '📊', 
          color: (metrics.avg_trade || 0) > 0 ? 'green' : 'red' as ValidationColor
        },
        { 
          label: 'Sharpe Ratio', 
          value: (metrics.sharpe_ratio || 0).toFixed(2), 
          icon: '📈', 
          color: getValidationColor(metrics.sharpe_ratio || 0, 1.5, 1.0)
        }
      ],
      trustIndicators: [
        { 
          title: 'Statistical Significance', 
          description: 'Strategy shows significant performance vs random', 
          status: getTrustStatus(metrics.total_trades || 0, 100, 50),
          details: `Based on ${metrics.total_trades || 0} trades` 
        },
        { 
          title: 'Sample Size Adequacy', 
          description: 'Adequate sample size for reliable results', 
          status: getTrustStatus(metrics.total_trades || 0, 200, 100),
          details: `${metrics.total_trades || 0} trades (target: 200+)` 
        },
        { 
          title: 'Strategy Diversification', 
          description: 'Strategy is well diversified across time periods', 
          status: getTrustStatus(combinedStats.recommended_accounts.length, 3, 2),
          details: `${combinedStats.recommended_accounts.length} accounts used` 
        }
      ],
      overallScore: Math.min(100, Math.max(0, 
        ((metrics.win_rate || 0) * 0.3) + 
        (Math.min(100, (metrics.sharpe_ratio || 0) * 50) * 0.3) + 
        (Math.min(100, (metrics.total_trades || 0) / 2) * 0.4)
      ))
    };
  };

  // Performance Breakdown data
  const getPerformanceBreakdownData = () => {
    type PerformanceStatus = 'positive' | 'negative' | 'neutral';
    type MonteCarloStatus = 'good' | 'warning' | 'poor';
    type PerformanceCategory = 'returns' | 'risk' | 'trades';
    
    if (!combinedStats) {
      return {
        performanceMetrics: [
          { label: 'Profit Factor', value: 'N/A', category: 'returns' as PerformanceCategory },
          { label: 'Average Winner', value: 'N/A', category: 'returns' as PerformanceCategory },
          { label: 'Average Loser', value: 'N/A', category: 'returns' as PerformanceCategory },
          { label: 'Max Drawdown', value: 'N/A', category: 'risk' as PerformanceCategory },
          { label: 'Volatility', value: 'N/A', category: 'risk' as PerformanceCategory },
          { label: 'Sharpe Ratio', value: 'N/A', category: 'risk' as PerformanceCategory },
          { label: 'Winning Trades', value: 'N/A', category: 'trades' as PerformanceCategory },
          { label: 'Losing Trades', value: 'N/A', category: 'trades' as PerformanceCategory },
          { label: 'Win/Loss Rate', value: 'N/A', category: 'trades' as PerformanceCategory }
        ],
        monteCarloMetrics: [
          { label: 'Value at Risk (95%)', value: 'N/A', description: 'Maximum expected loss in bad scenarios', status: 'poor' as MonteCarloStatus },
          { label: 'Expected Shortfall', value: 'N/A', description: 'Average loss in top 5% worst scenarios', status: 'poor' as MonteCarloStatus },
          { label: 'Probability of Profit', value: 'N/A', description: 'Chance of profit over next trading period', status: 'poor' as MonteCarloStatus }
        ]
      };
    }

    const metrics = combinedStats.combined_metrics;
    
    const getPerformanceStatus = (value: number, goodThreshold: number, warningThreshold: number, isReverse = false): PerformanceStatus => {
      if (isReverse) {
        return value <= goodThreshold ? 'positive' : value <= warningThreshold ? 'neutral' : 'negative';
      }
      return value >= goodThreshold ? 'positive' : value >= warningThreshold ? 'neutral' : 'negative';
    };
    
    const getMonteCarloStatus = (value: number, goodThreshold: number, warningThreshold: number, isReverse = false): MonteCarloStatus => {
      if (isReverse) {
        return value <= goodThreshold ? 'good' : value <= warningThreshold ? 'warning' : 'poor';
      }
      return value >= goodThreshold ? 'good' : value >= warningThreshold ? 'warning' : 'poor';
    };
    
    return {
      performanceMetrics: [
        { 
          label: 'Profit Factor', 
          value: (metrics.profit_factor || 0).toFixed(2), 
          category: 'returns' as PerformanceCategory,
          status: getPerformanceStatus(metrics.profit_factor || 0, 1.5, 1.0)
        },
        { 
          label: 'Average Winner', 
          value: `$${(metrics.avg_winner || 0).toFixed(2)}`, 
          category: 'returns' as PerformanceCategory,
          status: (metrics.avg_winner || 0) > 0 ? 'positive' : 'negative' as PerformanceStatus
        },
        { 
          label: 'Average Loser', 
          value: `$${(metrics.avg_loser || 0).toFixed(2)}`, 
          category: 'returns' as PerformanceCategory,
          status: getPerformanceStatus(Math.abs(metrics.avg_loser || 0), 50, 100, true)
        },
        { 
          label: 'Max Drawdown', 
          value: `$${Math.abs(metrics.max_drawdown || 0).toLocaleString()}`, 
          category: 'risk' as PerformanceCategory,
          status: getPerformanceStatus(Math.abs(metrics.max_drawdown || 0), 1000, 5000, true)
        },
        { 
          label: 'Volatility', 
          value: `${((Math.abs(metrics.max_drawdown || 0)) / (Math.abs(metrics.total_pnl || 1)) * 100).toFixed(1)}%`, 
          category: 'risk' as PerformanceCategory,
          status: 'neutral' as PerformanceStatus
        },
        { 
          label: 'Sharpe Ratio', 
          value: (metrics.sharpe_ratio || 0).toFixed(2), 
          category: 'risk' as PerformanceCategory,
          status: getPerformanceStatus(metrics.sharpe_ratio || 0, 1.5, 1.0)
        },
        { 
          label: 'Winning Trades', 
          value: metrics.winning_trades || 0, 
          category: 'trades' as PerformanceCategory,
          status: 'positive' as PerformanceStatus
        },
        { 
          label: 'Losing Trades', 
          value: metrics.losing_trades || 0, 
          category: 'trades' as PerformanceCategory,
          status: 'negative' as PerformanceStatus
        },
        { 
          label: 'Win/Loss Rate', 
          value: `${(metrics.win_rate || 0).toFixed(1)}%`, 
          category: 'trades' as PerformanceCategory,
          status: getPerformanceStatus(metrics.win_rate || 0, 60, 50)
        }
      ],
      monteCarloMetrics: [
        { 
          label: 'Value at Risk (95%)', 
          value: `-$${Math.abs(metrics.max_drawdown || 2009).toLocaleString()}`, 
          description: 'Maximum expected loss in bad scenarios', 
          status: getMonteCarloStatus(Math.abs(metrics.max_drawdown || 0), 1000, 3000, true)
        },
        { 
          label: 'Expected Shortfall', 
          value: `$${Math.abs(metrics.avg_loser || 1008).toLocaleString()}`, 
          description: 'Average loss in top 5% worst scenarios', 
          status: getMonteCarloStatus(Math.abs(metrics.avg_loser || 0), 500, 1500, true)
        },
        { 
          label: 'Probability of Profit', 
          value: `${(metrics.win_rate || 79).toFixed(0)}%`, 
          description: 'Chance of profit over next trading period', 
          status: getMonteCarloStatus(metrics.win_rate || 0, 70, 60)
        }
      ]
    };
  };

  // Dashboard items configuration
  const getDashboardItems = () => {
    const screenWidth = window.innerWidth;
    const gap = 30;
    
    // Start with smaller default sizes - auto-sizing will adjust them
    const leftColumnWidth = Math.floor(screenWidth * 0.45);
    const rightColumnWidth = Math.floor(screenWidth * 0.45);
    
    return [
      {
        id: 'strategy-validation',
        title: '🔬 Strategy Validation Analytics',
        component: <StrategyValidationAnalytics {...getStrategyValidationData()} />,
        defaultPosition: { 
          x: 20, 
          y: 20, // Start from top of dashboard
          width: leftColumnWidth, 
          height: 400 // Will auto-size to content
        },
        minWidth: 400,
        minHeight: 300
      },
      {
        id: 'trading-readiness',
        title: '🎯 Trading Readiness Assessment',
        component: <TradingReadinessAssessment {...getReadinessAssessmentData()} />,
        defaultPosition: { 
          x: leftColumnWidth + gap, 
          y: 20, // Start from top of dashboard
          width: rightColumnWidth, 
          height: 250 // Will auto-size to content
        },
        minWidth: 350,
        minHeight: 200
      },
      {
        id: 'performance-breakdown',
        title: '📊 Performance Breakdown',
        component: <PerformanceBreakdown {...getPerformanceBreakdownData()} />,
        defaultPosition: { 
          x: leftColumnWidth + gap, 
          y: 300, // Position below readiness widget
          width: rightColumnWidth, 
          height: 400 // Will auto-size to content
        },
        minWidth: 350,
        minHeight: 300
      }
    ];
  };

  // Backtest state
  const [backtestConfig, setBacktestConfig] = useState({
    startDate: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0], // 90 days ago
    endDate: new Date().toISOString().split('T')[0], // today
    initialCapital: 100000,
    commissionPerTrade: 1.0,
    slippageBps: 1,
    method: 'simple_historical' as 'simple_historical' | 'walk_forward',
    trainingDays: 30,
    testingDays: 7,
    rebalanceFrequency: 'daily' as 'daily' | 'weekly' | 'monthly',
    numSimulations: 1000,
    confidenceLevels: [0.95, 0.99],
    numFolds: 5,
    benchmarkSymbol: 'SPY',
    riskFreeRate: 0.02
  });
  const [backtestStatus, setBacktestStatus] = useState<any>(null);
  const [backtestResults, setBacktestResults] = useState<any>(null);
  const [isRunningBacktest, setIsRunningBacktest] = useState(false);
  const [backtestError, setBacktestError] = useState<string | null>(null);

  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri']; // Removed Saturday
  
  const timeHorizonOptions = [
    { value: '7', label: '7 Days' },
    { value: '30', label: '30 Days' },
    { value: '90', label: '3 Months' },
    { value: '365', label: '1 Year' },
    { value: 'all', label: 'All Time' }
  ];

  const getDaysFromTimeHorizon = (horizon: string): number => {
    switch (horizon) {
      case '7': return 7;
      case '30': return 30;
      case '90': return 90;
      case '365': return 365;
      case 'all': return 9999; // Large number for all time
      default: return 30;
    }
  };

  const getTimeHorizonLabel = (horizon: string): string => {
    const option = timeHorizonOptions.find(opt => opt.value === horizon);
    return option ? option.label : '30 Days';
  };

  const getExpectedTradingDays = (horizon: string): number | string => {
    switch (horizon) {
      case '7': return 5; // 5 trading days in a week
      case '30': return 21; // ~21 trading days in a month (30 days × 5/7)
      case '90': return 64; // ~64 trading days in 3 months (90 days × 5/7)
      case '365': return 261; // ~261 trading days in a year (365 days × 5/7)
      case 'all': return 'All Time';
      default: return 21;
    }
  };

  // Fetch available symbols
  useEffect(() => {
    fetchSymbols();
  }, []);

  // Fetch data when symbol, settings, or time horizon change
  useEffect(() => {
    if (selectedSymbol) {
      fetchRecommendationData(selectedSymbol);
    }
  }, [selectedSymbol, filterSettings, timeHorizon]);

  const fetchSymbols = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/v1/analytics/symbols');
      const result = await response.json();
      
      if (result.status === 'success' && result.data?.symbols) {
        setSymbols(result.data.symbols);
        if (result.data.symbols.length > 0) {
          setSelectedSymbol(result.data.symbols[0].symbol);
        }
      }
    } catch (err) {
      console.error('Error fetching symbols:', err);
      setError('Failed to load symbols');
    }
  };

  const fetchRecommendationData = async (symbol: string, settings?: FilterSettings) => {
    setIsLoading(true);
    setError(null);

    const currentSettings = settings || filterSettings;
    const params = new URLSearchParams({
      min_avg_profit: currentSettings.minAvgProfit.toString(),
      min_win_rate: currentSettings.minWinRate.toString(),
      min_trades: currentSettings.minTrades.toString()
    });

    try {
      // Fetch recommendation matrix with parameters
      const matrixResponse = await fetch(`http://localhost:8000/api/v1/analytics/recommendations/matrix/${symbol}?${params}`);
      const matrixResult = await matrixResponse.json();
      
      if (matrixResult.status === 'success') {
        setMatrix(matrixResult.data.matrix || {});
      }

      // Fetch backtest data with same filter parameters and time horizon
      const daysBack = getDaysFromTimeHorizon(timeHorizon);
      console.log('[BACKTEST] Fetching backtest data:', { symbol, daysBack, params: params.toString() });
      const backtestResponse = await fetch(`http://localhost:8000/api/v1/analytics/recommendations/backtest/${symbol}?days_back=${daysBack}&${params}`);
      const backtestResult = await backtestResponse.json();
      
      console.log('[BACKTEST] Backtest result:', backtestResult);
      if (backtestResult.status === 'success') {
        setBacktestData(backtestResult.data.chart_data || []);
        setBacktestMetadata(backtestResult.data);
        console.log('[BACKTEST] Chart data set:', backtestResult.data.chart_data);
      } else {
        console.error('[BACKTEST] Backtest failed:', backtestResult);
        setBacktestData([]);
        setBacktestMetadata(null);
      }

      // Fetch combined statistics with same filter parameters
      const statsResponse = await fetch(`http://localhost:8000/api/v1/analytics/recommendations/combined-stats/${symbol}?${params}`);
      const statsResult = await statsResponse.json();
      
      if (statsResult.status === 'success') {
        setCombinedStats(statsResult.data);
      }

      // Fetch time-filtered statistics
      await fetchTimeFilteredStats(symbol, daysBack);

    } catch (err) {
      console.error('Error fetching recommendation data:', err);
      setError('Failed to load recommendation data');
    } finally {
      setIsLoading(false);
    }
  };

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value);
  };

  const getTimeSlots = (): string[] => {
    const slots: string[] = [];
    for (let hour = 0; hour < 24; hour++) {
      slots.push(`${hour.toString().padStart(2, '0')}:00`);
      slots.push(`${hour.toString().padStart(2, '0')}:30`);
    }
    return slots;
  };

  const getCellData = (timeSlot: string, dayOfWeek: number) => {
    return matrix[timeSlot]?.[dayOfWeek];
  };

  const handleSettingsChange = (newSettings: FilterSettings) => {
    setFilterSettings(newSettings);
  };

  const handleApplySettings = () => {
    if (selectedSymbol) {
      fetchRecommendationData(selectedSymbol, filterSettings);
    }
    setActiveTab('matrix');
  };

  // Fetch time-filtered statistics
  const fetchTimeFilteredStats = async (symbol: string, daysBack: number) => {
    try {
      const params = new URLSearchParams({
        days_back: daysBack.toString(),
        min_avg_profit: filterSettings.minAvgProfit.toString(),
        min_win_rate: filterSettings.minWinRate.toString(),
        min_trades: filterSettings.minTrades.toString()
      });

      const response = await fetch(`http://localhost:8000/api/v1/analytics/recommendations/combined-stats/${symbol}?${params}`);
      const result = await response.json();
      
      if (result.status === 'success') {
        setTimeFilteredStats(result.data);
      }
    } catch (error) {
      console.error('Error fetching time-filtered stats:', error);
    }
  };

  // Fetch validation data for the entire recommendation strategy
  const fetchStrategyValidationData = async () => {
    setIsLoadingValidation(true);
    try {
      console.log('🔬 Fetching validation for entire recommendation strategy');

      // Get the same parameters used for the backtest
      const daysBack = getDaysFromTimeHorizon(timeHorizon);
      const params = new URLSearchParams({
        days_back: daysBack.toString(),
        min_avg_profit: filterSettings.minAvgProfit.toString(),
        min_win_rate: filterSettings.minWinRate.toString(),
        min_trades: filterSettings.minTrades.toString(),
        export: 'true' // Get the actual trades for analysis
      });

      // Fetch the complete trade list (same as CSV export)
      const tradesResponse = await fetch(`http://localhost:8000/api/v1/analytics/recommendations/backtest/${selectedSymbol}?${params}`);
      if (!tradesResponse.ok) {
        throw new Error(`Trades API failed: ${tradesResponse.status}`);
      }
      const tradesData = await tradesResponse.json();

      if (tradesData.status === 'success' && tradesData.data.trades) {
        const trades = tradesData.data.trades;
        console.log('📊 Analyzing', trades.length, 'trades from recommendation strategy');

        // Perform comprehensive analysis on the trade list
        const analysis = analyzeTradeList(trades);
        
        // Try to fetch advanced analytics if available
        let advancedAnalytics = null;
        try {
          const advancedResponse = await fetch(`http://localhost:8000/api/v1/recommendations/advanced?min_confidence=0.0`);
          if (advancedResponse.ok) {
            const advancedData = await advancedResponse.json();
            if (advancedData.status === 'success' && advancedData.data?.length > 0) {
              // Find recommendation for our symbol or use first one
              advancedAnalytics = advancedData.data.find((rec: any) => rec.time_bin?.account_name?.includes(selectedSymbol)) || advancedData.data[0];
            }
          }
        } catch (error) {
          console.log('Advanced analytics not available:', error);
        }

        const combinedValidation = {
          symbol: selectedSymbol,
          strategy_type: 'Multi-Account Time-Bin Strategy',
          time_horizon: getTimeHorizonLabel(timeHorizon),
          total_trades: trades.length,
          analysis,
          advanced_analytics: advancedAnalytics,
          raw_trades: trades
        };

        setValidationData(combinedValidation);
        console.log('✅ Strategy validation data loaded:', combinedValidation);

      } else {
        throw new Error('No trades data available');
      }

    } catch (error) {
      console.error('❌ Error fetching strategy validation data:', error);
      setValidationData(null);
    } finally {
      setIsLoadingValidation(false);
    }
  };

  // Calculate required sample size for statistical power
  const calculateRequiredSampleSize = (effectSize: number, alpha: number = 0.05, power: number = 0.8): number => {
    // Handle invalid inputs
    if (isNaN(effectSize) || !isFinite(effectSize) || effectSize <= 0) {
      return 500; // Conservative estimate for unknown effect size
    }
    
    // Z-scores for alpha and power
    const zAlpha = alpha <= 0.01 ? 2.576 : alpha <= 0.05 ? 1.96 : 1.645;
    const zBeta = power >= 0.9 ? 1.282 : power >= 0.8 ? 0.842 : 0.524;
    
    // Sample size calculation: n = ((z_alpha + z_beta) / effect_size)^2
    const requiredN = Math.pow((zAlpha + zBeta) / effectSize, 2);
    
    // Ensure result is valid
    if (isNaN(requiredN) || !isFinite(requiredN)) {
      return 500;
    }
    
    // Minimum thresholds based on effect size
    let minSample = 30; // Absolute minimum for CLT
    if (effectSize < 0.2) minSample = 400; // Small effect
    else if (effectSize < 0.5) minSample = 100; // Medium effect  
    else if (effectSize < 0.8) minSample = 50; // Large effect
    
    const result = Math.max(Math.ceil(requiredN), minSample);
    
    // Cap at reasonable maximum
    return Math.min(result, 2000);
  };

  // Analyze a list of trades to generate validation metrics
  const analyzeTradeList = (trades: any[]) => {
    if (!trades || trades.length === 0) {
      return null;
    }

    // Basic performance metrics
    const totalPnL = trades.reduce((sum, trade) => sum + (trade.profit_loss || 0), 0);
    const winningTrades = trades.filter(trade => (trade.profit_loss || 0) > 0);
    const losingTrades = trades.filter(trade => (trade.profit_loss || 0) < 0);
    const winRate = winningTrades.length / trades.length;
    const avgTrade = totalPnL / trades.length;

    // Risk metrics
    const returns = trades.map(trade => trade.profit_loss || 0);
    const avgReturn = returns.reduce((sum, ret) => sum + ret, 0) / returns.length;
    const variance = returns.reduce((sum, ret) => sum + Math.pow(ret - avgReturn, 2), 0) / returns.length;
    const stdDev = Math.sqrt(variance);
    const sharpeRatio = stdDev > 0 ? (avgReturn / stdDev) * Math.sqrt(252) : 0; // Annualized

    // Drawdown analysis
    let runningPnL = 0;
    let peak = 0;
    let maxDrawdown = 0;
    const equityCurve: number[] = [];

    trades.forEach(trade => {
      runningPnL += trade.profit_loss || 0;
      equityCurve.push(runningPnL);
      if (runningPnL > peak) {
        peak = runningPnL;
      }
      const drawdown = peak - runningPnL;
      if (drawdown > maxDrawdown) {
        maxDrawdown = drawdown;
      }
    });

    // Statistical significance (proper t-test)
    const tStat = stdDev > 0 ? Math.sqrt(trades.length) * (avgReturn / stdDev) : 0;
    const degreesOfFreedom = trades.length - 1;
    
    // Proper p-value calculation using t-distribution approximation
    let pValue = 1.0;
    if (Math.abs(tStat) > 0) {
      // Two-tailed t-test p-value approximation
      const absT = Math.abs(tStat);
      if (absT > 4) {
        pValue = 0.0001; // Very significant
      } else if (absT > 3.5) {
        pValue = 0.001;
      } else if (absT > 3) {
        pValue = 0.005;
      } else if (absT > 2.8) {
        pValue = 0.01;
      } else if (absT > 2.5) {
        pValue = 0.02;
      } else if (absT > 2.2) {
        pValue = 0.03;
      } else if (absT > 1.96) {
        pValue = 0.05;
      } else if (absT > 1.7) {
        pValue = 0.10;
      } else if (absT > 1.3) {
        pValue = 0.20;
      } else {
        pValue = 0.50; // Not significant
      }
    }
    
    const statisticallySignificant = pValue < 0.05;
    
    // Proper sample size validation based on statistical power
    const effectSize = stdDev > 0 ? Math.abs(avgReturn / stdDev) : 0;
    const requiredSampleSize = calculateRequiredSampleSize(effectSize, 0.05, 0.8); // 5% alpha, 80% power
    const sampleSizeAdequate = trades.length >= requiredSampleSize;
    
    // Ensure no NaN values
    const safeEffectSize = isNaN(effectSize) ? 0 : effectSize;
    const safeRequiredSampleSize = isNaN(requiredSampleSize) ? 1000 : requiredSampleSize;

    // Monte Carlo simulation (proper bootstrap using full sample)
    const bootstrapResults = [];
    const tradingDaysPerMonth = 21; // Standard trading days in a month
    const simulationHorizon = Math.min(tradingDaysPerMonth, Math.floor(trades.length / 10)); // Use realistic horizon
    
    for (let i = 0; i < 10000; i++) { // 10,000 scenarios (industry standard)
      let bootstrapPnL = 0;
      // Bootstrap sample from ALL historical trades
      for (let j = 0; j < simulationHorizon; j++) {
        const randomTrade = returns[Math.floor(Math.random() * returns.length)];
        bootstrapPnL += randomTrade;
      }
      bootstrapResults.push(bootstrapPnL);
    }
    bootstrapResults.sort((a, b) => a - b);
    const var95 = bootstrapResults[Math.floor(bootstrapResults.length * 0.05)];
    const expectedShortfall = bootstrapResults.slice(0, Math.floor(bootstrapResults.length * 0.05))
      .reduce((sum, val) => sum + val, 0) / Math.floor(bootstrapResults.length * 0.05);

    // Account/time-bin diversity
    const uniqueAccounts = new Set(trades.map(trade => trade.account_name)).size;
    const uniqueTimeSlots = new Set(trades.map(trade => trade.time_slot)).size;
    const uniqueDays = new Set(trades.map(trade => trade.day_of_week)).size;

    return {
      // Performance metrics
      total_pnl: totalPnL,
      total_trades: trades.length,
      win_rate: winRate,
      avg_trade: avgTrade,
      winning_trades: winningTrades.length,
      losing_trades: losingTrades.length,
      avg_winner: winningTrades.length > 0 ? winningTrades.reduce((sum, t) => sum + t.profit_loss, 0) / winningTrades.length : 0,
      avg_loser: losingTrades.length > 0 ? losingTrades.reduce((sum, t) => sum + t.profit_loss, 0) / losingTrades.length : 0,
      profit_factor: losingTrades.length > 0 ? Math.abs(winningTrades.reduce((sum, t) => sum + t.profit_loss, 0) / losingTrades.reduce((sum, t) => sum + t.profit_loss, 0)) : 0,
      
      // Risk metrics
      sharpe_ratio: sharpeRatio,
      max_drawdown: maxDrawdown,
      max_drawdown_pct: totalPnL > 0 ? (maxDrawdown / totalPnL) * 100 : 0,
      volatility: stdDev,
      
      // Statistical validation
      statistical_significance: statisticallySignificant,
      p_value: pValue,
      t_statistic: tStat,
      degrees_of_freedom: degreesOfFreedom,
      confidence_interval: [avgReturn - 1.96 * (stdDev / Math.sqrt(trades.length)), avgReturn + 1.96 * (stdDev / Math.sqrt(trades.length))],
      
      // Sample size validation
      sample_size_adequate: sampleSizeAdequate,
      required_sample_size: safeRequiredSampleSize,
      effect_size: safeEffectSize,
      
      // Monte Carlo results
      var_95: var95,
      expected_shortfall: expectedShortfall,
      worst_case: Math.min(...bootstrapResults),
      best_case: Math.max(...bootstrapResults),
      probability_of_profit: bootstrapResults.filter(result => result > 0).length / bootstrapResults.length,
      
      // Strategy diversity
      unique_accounts: uniqueAccounts,
      unique_time_slots: uniqueTimeSlots,
      unique_days: uniqueDays,
      diversification_score: (uniqueAccounts * uniqueTimeSlots * uniqueDays) / (trades.length / 10), // Rough diversification metric
      
      // Equity curve
      equity_curve: equityCurve
    };
  };

  // Handle showing validation for the entire strategy
  const handleShowStrategyValidation = () => {
    setActiveTab('validation');
    fetchStrategyValidationData();
  };

  // Backtest functions
  const runBacktest = async () => {
    if (!selectedSymbol || !matrix) {
      setBacktestError('Please select a symbol and ensure matrix data is loaded');
      return;
    }

    setIsRunningBacktest(true);
    setBacktestError(null);
    setBacktestStatus(null);
    setBacktestResults(null);

    try {
      // Get the recommended time bins from the current matrix
      const timeBins = [];
      const timeSlots = getFilteredTimeSlots();
      
      for (const timeSlot of timeSlots) {
        const [hour, minute] = timeSlot.split(':').map(Number);
        for (let dayOfWeek = 0; dayOfWeek <= 5; dayOfWeek++) { // Mon-Fri
          const cellData = getCellData(timeSlot, dayOfWeek);
          if (cellData && cellData.best_account) {
            timeBins.push({
              account_name: cellData.best_account,
              hour: hour,
              minute_bin: minute
            });
          }
        }
      }

      if (timeBins.length === 0) {
        setBacktestError('No recommended time bins found for backtesting');
        setIsRunningBacktest(false);
        return;
      }

      // Prepare backtest request
      const backtestRequest = {
        configuration: {
          start_date: backtestConfig.startDate,
          end_date: backtestConfig.endDate,
          initial_capital: backtestConfig.initialCapital,
          commission_per_trade: backtestConfig.commissionPerTrade,
          slippage_bps: backtestConfig.slippageBps,
          method: backtestConfig.method,
          training_days: backtestConfig.trainingDays,
          testing_days: backtestConfig.testingDays,
          rebalance_frequency: backtestConfig.rebalanceFrequency,
          num_simulations: backtestConfig.numSimulations,
          confidence_levels: backtestConfig.confidenceLevels,
          num_folds: backtestConfig.numFolds,
          benchmark_symbol: backtestConfig.benchmarkSymbol,
          risk_free_rate: backtestConfig.riskFreeRate
        },
        time_bins: timeBins,
        strategy_parameters: {
          strategy_name: `${selectedSymbol}_time_bin_strategy`,
          parameters: {
            symbol: selectedSymbol,
            time_horizon_days: parseInt(timeHorizon)
          }
        },
        run_analysis: true,
        analysis_types: ['PERFORMANCE', 'RISK', 'STATISTICAL_VALIDATION', 'COMPARATIVE']
      };

      // Start backtest
      const response = await fetch('http://localhost:8000/api/backtesting/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(backtestRequest)
      });

      if (!response.ok) {
        throw new Error(`Failed to start backtest: ${response.statusText}`);
      }

      const status = await response.json();
      setBacktestStatus(status);

      // Poll for results
      pollBacktestStatus(status.backtest_id);

    } catch (error) {
      console.error('Error running backtest:', error);
      setBacktestError(error instanceof Error ? error.message : 'Failed to run backtest');
      setIsRunningBacktest(false);
    }
  };

  const pollBacktestStatus = async (backtestId: string) => {
    const maxAttempts = 60; // 5 minutes max
    let attempts = 0;

    const poll = async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/backtesting/status/${backtestId}`);
        if (!response.ok) {
          throw new Error('Failed to get backtest status');
        }

        const status = await response.json();
        setBacktestStatus(status);

        if (status.status === 'COMPLETED') {
          // Fetch results
          await fetchBacktestResults(backtestId);
          setIsRunningBacktest(false);
        } else if (status.status === 'FAILED') {
          setBacktestError(status.error_message || 'Backtest failed');
          setIsRunningBacktest(false);
        } else if (attempts < maxAttempts) {
          attempts++;
          setTimeout(poll, 5000); // Poll every 5 seconds
        } else {
          setBacktestError('Backtest timed out');
          setIsRunningBacktest(false);
        }
      } catch (error) {
        console.error('Error polling backtest status:', error);
        setBacktestError('Failed to get backtest status');
        setIsRunningBacktest(false);
      }
    };

    poll();
  };

  const fetchBacktestResults = async (backtestId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/backtesting/results/${backtestId}?include_trades=true&include_daily_returns=true`);
      if (!response.ok) {
        throw new Error('Failed to fetch backtest results');
      }

      const results = await response.json();
      setBacktestResults(results);
    } catch (error) {
      console.error('Error fetching backtest results:', error);
      setBacktestError('Failed to fetch backtest results');
    }
  };

  // Export trades to CSV
  const exportTradesToCSV = async () => {
    if (!selectedSymbol || !backtestMetadata) return;

    try {
      const daysBack = getDaysFromTimeHorizon(timeHorizon);
      const params = new URLSearchParams({
        days_back: daysBack.toString(),
        min_avg_profit: filterSettings.minAvgProfit.toString(),
        min_win_rate: filterSettings.minWinRate.toString(),
        min_trades: filterSettings.minTrades.toString(),
        export: 'true'
      });

      const response = await fetch(`http://localhost:8000/api/v1/analytics/recommendations/backtest/${selectedSymbol}?${params}`);
      const result = await response.json();
      
      if (result.status === 'success' && result.data.trades) {
        // Convert trades to CSV
        const trades = result.data.trades;
        const headers = ['Date', 'Time', 'Account', 'Symbol', 'Entry Time', 'Exit Time', 'Profit/Loss', 'Time Slot', 'Day of Week'];
        
        const csvContent = [
          headers.join(','),
          ...trades.map((trade: any) => [
            trade.date,
            trade.entry_time,
            trade.account_name,
            trade.symbol,
            trade.entry_time,
            trade.exit_time || '',
            trade.profit_loss,
            trade.time_slot,
            trade.day_of_week
          ].join(','))
        ].join('\n');

        // Download CSV
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', `${selectedSymbol}_strategy_trades_${timeHorizon}_${new Date().toISOString().split('T')[0]}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }
    } catch (error) {
      console.error('Error exporting trades:', error);
      alert('Failed to export trades. Please try again.');
    }
  };

  const getCellClass = (cellData: any) => {
    if (!cellData) return 'matrix-cell empty';
    
    if (cellData.avg_trade > 50) return 'matrix-cell excellent';
    if (cellData.avg_trade > 0) return 'matrix-cell good';
    if (cellData.avg_trade > -50) return 'matrix-cell neutral';
    return 'matrix-cell poor';
  };

  // Function to check if a time slot has any recommendations
  const hasRecommendations = (timeSlot: string): boolean => {
    for (let dayOfWeek = 0; dayOfWeek < 6; dayOfWeek++) { // 0-5 (Sun-Fri, no Saturday)
      if (getCellData(timeSlot, dayOfWeek)) {
        return true;
      }
    }
    return false;
  };

  // Filter time slots to only show those with recommendations
  const getFilteredTimeSlots = (): string[] => {
    return getTimeSlots().filter(timeSlot => hasRecommendations(timeSlot));
  };

  if (isLoading && symbols.length === 0) {
    return (
      <div className="recommendations">
        <div className="loading">Loading symbols...</div>
      </div>
    );
  }

  return (
    <div className="recommendations">
      {/* Top Navigation Bar */}
      <div className="top-navigation">
        <div className="nav-left">
          <h1>Trading Recommendations</h1>
          
          <div className="tabs-and-controls">
            <div className="symbol-tabs">
              {symbols.map(symbol => (
                <button
                  key={symbol.symbol}
                  className={`tab-button ${selectedSymbol === symbol.symbol ? 'active' : ''}`}
                  onClick={() => setSelectedSymbol(symbol.symbol)}
                >
                  {symbol.symbol}
                  <span className="tab-info">({symbol.total_trades} trades)</span>
                </button>
              ))}
            </div>
            
            {selectedSymbol && (
              <div className="inline-controls">
                <button 
                  className="refresh-btn" 
                  onClick={() => fetchRecommendations()}
                  disabled={isLoading}
                >
                  {isLoading ? 'Loading...' : 'Refresh Data'}
                </button>
                
                <div className="time-horizon-selector">
                  <label htmlFor="timeHorizon">Time Horizon:</label>
                  <select 
                    id="timeHorizon"
                    className="time-horizon-dropdown"
                    value={timeHorizon}
                    onChange={(e) => setTimeHorizon(e.target.value)}
                  >
                    <option value="7">1 Week</option>
                    <option value="30">1 Month</option>
                    <option value="90">3 Months</option>
                    <option value="180">6 Months</option>
                    <option value="365">1 Year</option>
                    <option value="all">All Time</option>
                  </select>
                </div>
              </div>
            )}
            

          </div>
        </div>
        


      </div>



      {selectedSymbol && (
        <>
          {/* Reset Layout Button in Top Navigation */}
          <button 
            className="top-nav-reset-btn" 
            onClick={() => {
              if (selectedSymbol) {
                localStorage.removeItem(`dashboard-layout-${selectedSymbol}`);
                window.location.reload();
              }
            }}
          >
            🔄 Reset Layout
          </button>
          
          <DragDropDashboard 
            items={getDashboardItems()}
            storageKey={`dashboard-layout-${selectedSymbol}`}
            className="trading-dashboard"
          />
        </>
      )}

      {!selectedSymbol && (
        <div className="no-symbol-selected">
          <h2>Select a symbol to view recommendations</h2>
          <p>Choose a symbol from the tabs above to see detailed trading analytics and recommendations.</p>
        </div>
      )}

      {/* Legacy content for tabs - keeping below dashboard */}
      {selectedSymbol && (
        <div className="legacy-content" style={{ marginTop: '20px' }}>
          <div className="content-header">
            <div className="tab-navigation">
              <button 
                className={`content-tab ${activeTab === 'matrix' ? 'active' : ''}`}
                onClick={() => setActiveTab('matrix')}
              >
                Recommendation Matrix
              </button>
              <button 
                className={`content-tab ${activeTab === 'validation' ? 'active' : ''}`}
                onClick={handleShowStrategyValidation}
                disabled={!selectedSymbol}
              >
                🔬 Strategy Validation
                <span className="tab-info">
                  (Complete Multi-Account Analysis)
                </span>
              </button>
              <button 
                className={`content-tab ${activeTab === 'backtest' ? 'active' : ''}`}
                onClick={() => setActiveTab('backtest')}
                disabled={!selectedSymbol}
              >
                📈 Backtest
                <span className="tab-info">
                  (Run Historical Simulation)
                </span>
              </button>
              <button 
                className={`content-tab ${activeTab === 'settings' ? 'active' : ''}`}
                onClick={() => setActiveTab('settings')}
              >
                Filter Settings
              </button>
            </div>
            
            <div className="refresh-section">
              <button 
                onClick={() => fetchRecommendationData(selectedSymbol)}
                disabled={isLoading}
                className="refresh-btn"
              >
                {isLoading ? 'Loading...' : 'Refresh Data'}
              </button>
              
              <div className="time-horizon-selector">
                <label htmlFor="time-horizon">Time Horizon: </label>
                <select 
                  id="time-horizon"
                  value={timeHorizon} 
                  onChange={(e) => setTimeHorizon(e.target.value)}
                  className="time-horizon-dropdown"
                >
                  {timeHorizonOptions.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {error && (
            <div className="error">{error}</div>
          )}

          {activeTab === 'settings' && (
            <div className="settings-section">
              <h2>Filter Settings</h2>
              <p>Configure the criteria for account recommendations in the matrix</p>
              
              <div className="settings-form">
                <div className="setting-group">
                  <label htmlFor="minAvgProfit">Minimum Average Profit per Trade ($)</label>
                  <input
                    type="number"
                    id="minAvgProfit"
                    value={filterSettings.minAvgProfit}
                    onChange={(e) => handleSettingsChange({
                      ...filterSettings,
                      minAvgProfit: parseFloat(e.target.value) || 0
                    })}
                    step="0.1"
                    min="0"
                  />
                  <small>Only accounts with average profit above this threshold will be recommended</small>
                </div>

                <div className="setting-group">
                  <label htmlFor="minWinRate">Minimum Win Rate (%)</label>
                  <input
                    type="number"
                    id="minWinRate"
                    value={filterSettings.minWinRate}
                    onChange={(e) => handleSettingsChange({
                      ...filterSettings,
                      minWinRate: parseFloat(e.target.value) || 0
                    })}
                    step="0.1"
                    min="0"
                    max="100"
                  />
                  <small>Only accounts with win rate above this percentage will be recommended</small>
                </div>

                <div className="setting-group">
                  <label htmlFor="minTrades">Minimum Trades per Time Slot</label>
                  <input
                    type="number"
                    id="minTrades"
                    value={filterSettings.minTrades}
                    onChange={(e) => handleSettingsChange({
                      ...filterSettings,
                      minTrades: parseInt(e.target.value) || 0
                    })}
                    step="1"
                    min="1"
                  />
                  <small>Only time slots with at least this many trades will be considered</small>
                </div>

                <div className="settings-actions">
                  <button 
                    onClick={handleApplySettings}
                    className="apply-btn"
                    disabled={isLoading}
                  >
                    Apply Settings & Refresh Matrix
                  </button>
                  
                  <button 
                    onClick={() => {
                      setFilterSettings({
                        minAvgProfit: 10.0,
                        minWinRate: 55.0,
                        minTrades: 300
                      });
                    }}
                    className="reset-btn"
                  >
                    Reset to Defaults
                  </button>
                </div>

                <div className="current-settings">
                  <h3>Current Settings Summary</h3>
                  <ul>
                    <li>Minimum Average Profit: <strong>${filterSettings.minAvgProfit}</strong> per trade</li>
                    <li>Minimum Win Rate: <strong>{filterSettings.minWinRate}%</strong></li>
                    <li>Minimum Trades: <strong>{filterSettings.minTrades}</strong> per time slot</li>
                  </ul>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'validation' && (
            <div className="validation-section">
              <div className="validation-header">
                <h2>🔬 Strategy Validation Analytics</h2>
                <div className="header-info">
                  <h3>{selectedSymbol} Multi-Account Time-Bin Strategy</h3>
                  <p>Complete statistical analysis of all trades following optimal time-bin recommendations ({getTimeHorizonLabel(timeHorizon)})</p>
                </div>
              </div>

              {isLoadingValidation && (
                <div className="loading-validation">
                  <div className="loading-spinner"></div>
                  <p>Loading comprehensive validation analytics...</p>
                </div>
              )}

              {!isLoadingValidation && validationData && validationData.analysis && (
                <div className="validation-results">
                  
                  {/* Quick Summary Cards */}
                  <div className="summary-cards">
                    <div className="summary-card total-pnl">
                      <div className="card-header">
                        <span className="card-icon">💰</span>
                        <span className="card-title">Total P&L</span>
                      </div>
                      <div className={`card-value ${validationData.analysis.total_pnl > 0 ? 'positive' : 'negative'}`}>
                        {formatCurrency(validationData.analysis.total_pnl)}
                      </div>
                      <div className="card-subtitle">{validationData.total_trades} trades</div>
                    </div>

                    <div className="summary-card win-rate">
                      <div className="card-header">
                        <span className="card-icon">🎯</span>
                        <span className="card-title">Win Rate</span>
                      </div>
                      <div className={`card-value ${validationData.analysis.win_rate > 0.5 ? 'good' : 'neutral'}`}>
                        {(validationData.analysis.win_rate * 100).toFixed(1)}%
                      </div>
                      <div className="card-subtitle">{validationData.analysis.winning_trades} winners</div>
                    </div>

                    <div className="summary-card avg-trade">
                      <div className="card-header">
                        <span className="card-icon">📊</span>
                        <span className="card-title">Avg Trade</span>
                      </div>
                      <div className={`card-value ${validationData.analysis.avg_trade > 0 ? 'positive' : 'negative'}`}>
                        {formatCurrency(validationData.analysis.avg_trade)}
                      </div>
                      <div className="card-subtitle">per trade</div>
                    </div>

                    <div className="summary-card sharpe">
                      <div className="card-header">
                        <span className="card-icon">⚡</span>
                        <span className="card-title">Sharpe Ratio</span>
                      </div>
                      <div className={`card-value ${validationData.analysis.sharpe_ratio > 1 ? 'good' : validationData.analysis.sharpe_ratio > 0 ? 'neutral' : 'negative'}`}>
                        {validationData.analysis.sharpe_ratio?.toFixed(2) || 'N/A'}
                      </div>
                      <div className="card-subtitle">risk-adjusted</div>
                    </div>
                  </div>

                  {/* Trust Indicators */}
                  <div className="trust-section">
                    <h3>🔍 Can You Trust This Strategy?</h3>
                    <div className="trust-grid">
                      <div className={`trust-item ${validationData.analysis.statistical_significance ? 'pass' : 'fail'}`}>
                        <div className="trust-icon">{validationData.analysis.statistical_significance ? '✅' : '❌'}</div>
                        <div className="trust-content">
                          <div className="trust-title">Statistical Significance</div>
                          <div className="trust-detail">
                            p-value: {(validationData.analysis.p_value || 1).toFixed(4)} | t-stat: {(validationData.analysis.t_statistic || 0).toFixed(2)} | df: {validationData.analysis.degrees_of_freedom || 0}
                          </div>
                          <div className="trust-explanation">
                            {validationData.analysis.statistical_significance 
                              ? `Strong evidence (p < 0.05): Strategy performance is statistically significant with ${((1 - (validationData.analysis.p_value || 1)) * 100).toFixed(1)}% confidence`
                              : `Weak evidence (p ≥ 0.05): Results could be due to random chance. Only ${((1 - (validationData.analysis.p_value || 1)) * 100).toFixed(1)}% confidence this isn't luck`
                            }
                          </div>
                        </div>
                      </div>

                      <div className={`trust-item ${validationData.analysis.sample_size_adequate ? 'pass' : 'warning'}`}>
                        <div className="trust-icon">{validationData.analysis.sample_size_adequate ? '✅' : '⚠️'}</div>
                        <div className="trust-content">
                          <div className="trust-title">Sample Size Adequacy</div>
                          <div className="trust-detail">
                            {validationData.analysis.total_trades} trades (need {Math.round(validationData.analysis.required_sample_size || 0)})
                          </div>
                          <div className="trust-explanation">
                            {validationData.analysis.sample_size_adequate 
                              ? `Sufficient data for 80% statistical power with effect size ${(validationData.analysis.effect_size || 0).toFixed(2)}`
                              : `Need ${Math.max(0, Math.round((validationData.analysis.required_sample_size || 0) - validationData.analysis.total_trades))} more trades for reliable analysis (effect size: ${(validationData.analysis.effect_size || 0).toFixed(2)})`
                            }
                          </div>
                        </div>
                      </div>

                      <div className={`trust-item ${validationData.analysis.diversification_score > 1 ? 'pass' : 'warning'}`}>
                        <div className="trust-icon">{validationData.analysis.diversification_score > 1 ? '✅' : '⚠️'}</div>
                        <div className="trust-content">
                          <div className="trust-title">Strategy Diversification</div>
                          <div className="trust-detail">
                            {validationData.analysis.unique_accounts} accounts, {validationData.analysis.unique_time_slots} time slots
                          </div>
                          <div className="trust-explanation">
                            {validationData.analysis.diversification_score > 1 
                              ? 'Well diversified across accounts and time windows'
                              : 'Limited diversification - concentrated risk'
                            }
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Performance Details */}
                  <div className="performance-section">
                    <h3>📈 Performance Breakdown</h3>
                    <div className="performance-grid">
                      <div className="perf-group">
                        <h4>Returns</h4>
                        <div className="perf-item">
                          <span className="perf-label">Profit Factor</span>
                          <span className={`perf-value ${validationData.analysis.profit_factor > 1.5 ? 'excellent' : validationData.analysis.profit_factor > 1 ? 'good' : 'poor'}`}>
                            {validationData.analysis.profit_factor?.toFixed(2)}
                          </span>
                        </div>
                        <div className="perf-item">
                          <span className="perf-label">Average Winner</span>
                          <span className="perf-value positive">{formatCurrency(validationData.analysis.avg_winner)}</span>
                        </div>
                        <div className="perf-item">
                          <span className="perf-label">Average Loser</span>
                          <span className="perf-value negative">{formatCurrency(validationData.analysis.avg_loser)}</span>
                        </div>
                      </div>

                      <div className="perf-group">
                        <h4>Risk</h4>
                        <div className="perf-item">
                          <span className="perf-label">Max Drawdown</span>
                          <span className="perf-value negative">{formatCurrency(validationData.analysis.max_drawdown)}</span>
                        </div>
                        <div className="perf-item">
                          <span className="perf-label">Volatility</span>
                          <span className="perf-value neutral">{formatCurrency(validationData.analysis.volatility)}</span>
                        </div>
                        <div className="perf-item">
                          <span className="perf-label">Sharpe Ratio</span>
                          <span className={`perf-value ${validationData.analysis.sharpe_ratio > 1 ? 'excellent' : validationData.analysis.sharpe_ratio > 0 ? 'good' : 'poor'}`}>
                            {validationData.analysis.sharpe_ratio?.toFixed(2)}
                          </span>
                        </div>
                      </div>

                      <div className="perf-group">
                        <h4>Trade Stats</h4>
                        <div className="perf-item">
                          <span className="perf-label">Winning Trades</span>
                          <span className="perf-value good">{validationData.analysis.winning_trades}</span>
                        </div>
                        <div className="perf-item">
                          <span className="perf-label">Losing Trades</span>
                          <span className="perf-value poor">{validationData.analysis.losing_trades}</span>
                        </div>
                        <div className="perf-item">
                          <span className="perf-label">Win/Loss Ratio</span>
                          <span className="perf-value neutral">
                            {(validationData.analysis.winning_trades / Math.max(validationData.analysis.losing_trades, 1)).toFixed(2)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Monte Carlo Risk Analysis */}
                  <div className="monte-carlo-section">
                    <h3>🎲 Monte Carlo Risk Analysis</h3>
                    <p className="section-subtitle">Bootstrap simulation: 10,000 scenarios using full historical distribution ({validationData.total_trades} trades) over {Math.min(21, Math.floor(validationData.total_trades / 10))} trading days</p>
                    
                    <div className="monte-carlo-grid">
                      <div className="mc-card critical">
                        <div className="mc-header">
                          <span className="mc-icon">⚠️</span>
                          <div className="mc-title-group">
                            <div className="mc-title">Value at Risk (95%)</div>
                            <div className="mc-subtitle">Worst 5% scenarios</div>
                          </div>
                        </div>
                        <div className="mc-value negative">{formatCurrency(validationData.analysis.var_95 || 0)}</div>
                        <div className="mc-description">Maximum expected loss in bad scenarios</div>
                      </div>

                      <div className="mc-card warning">
                        <div className="mc-header">
                          <span className="mc-icon">📉</span>
                          <div className="mc-title-group">
                            <div className="mc-title">Expected Shortfall</div>
                            <div className="mc-subtitle">Average of worst 5%</div>
                          </div>
                        </div>
                        <div className="mc-value negative">{formatCurrency(validationData.analysis.expected_shortfall || 0)}</div>
                        <div className="mc-description">Average loss when things go really bad</div>
                      </div>

                      <div className="mc-card success">
                        <div className="mc-header">
                          <span className="mc-icon">🎯</span>
                          <div className="mc-title-group">
                            <div className="mc-title">Probability of Profit</div>
                            <div className="mc-subtitle">Success rate</div>
                          </div>
                        </div>
                        <div className={`mc-value ${validationData.analysis.probability_of_profit > 0.5 ? 'positive' : 'negative'}`}>
                          {((validationData.analysis.probability_of_profit || 0) * 100).toFixed(0)}%
                        </div>
                        <div className="mc-description">Chance of profit over next {Math.min(21, Math.floor(validationData.total_trades / 10))} trading days</div>
                      </div>
                    </div>

                    <div className="scenario-extremes">
                      <div className="extreme-card worst-case">
                        <div className="extreme-label">Worst Case Scenario</div>
                        <div className="extreme-value negative">{formatCurrency(validationData.analysis.worst_case || 0)}</div>
                        <div className="extreme-description">Absolute worst outcome in simulation</div>
                      </div>
                      <div className="extreme-card best-case">
                        <div className="extreme-label">Best Case Scenario</div>
                        <div className="extreme-value positive">{formatCurrency(validationData.analysis.best_case || 0)}</div>
                        <div className="extreme-description">Absolute best outcome in simulation</div>
                      </div>
                    </div>
                  </div>

                  {/* Trading Readiness Assessment */}
                  <div className="trading-readiness-section">
                    <h3>🎯 Trading Readiness Assessment</h3>
                    <p className="section-subtitle">Minimum conditions required before going live with real capital</p>
                    
                    <div className="readiness-criteria">
                      <div className="criteria-group risk-criteria">
                        <h4>🚨 Risk Management Criteria</h4>
                        <div className="criteria-list">
                          <div className={`criteria-item ${Math.abs(validationData.analysis.var_95) / Math.abs(validationData.analysis.best_case) <= 1.5 ? 'pass' : 'fail'}`}>
                            <div className="criteria-check">
                              {Math.abs(validationData.analysis.var_95) / Math.abs(validationData.analysis.best_case) <= 1.5 ? '✅' : '❌'}
                            </div>
                            <div className="criteria-content">
                              <div className="criteria-title">Risk-Reward Ratio</div>
                              <div className="criteria-current">
                                Current: {(Math.abs(validationData.analysis.var_95) / Math.abs(validationData.analysis.best_case)).toFixed(1)}:1
                              </div>
                              <div className="criteria-target">Target: ≤1.5:1 (downside:upside)</div>
                            </div>
                          </div>

                          <div className={`criteria-item ${validationData.analysis.probability_of_profit >= 0.75 ? 'pass' : 'fail'}`}>
                            <div className="criteria-check">
                              {validationData.analysis.probability_of_profit >= 0.75 ? '✅' : '❌'}
                            </div>
                            <div className="criteria-content">
                              <div className="criteria-title">Probability of Profit</div>
                              <div className="criteria-current">
                                Current: {(validationData.analysis.probability_of_profit * 100).toFixed(0)}%
                              </div>
                              <div className="criteria-target">Target: ≥75%</div>
                            </div>
                          </div>

                          <div className={`criteria-item ${Math.abs(validationData.analysis.var_95) <= 5000 ? 'pass' : 'fail'}`}>
                            <div className="criteria-check">
                              {Math.abs(validationData.analysis.var_95) <= 5000 ? '✅' : '❌'}
                            </div>
                            <div className="criteria-content">
                              <div className="criteria-title">Maximum Risk (VaR 95%)</div>
                              <div className="criteria-current">
                                Current: {formatCurrency(validationData.analysis.var_95)}
                              </div>
                              <div className="criteria-target">Target: ≥-$5,000</div>
                            </div>
                          </div>
                        </div>
                      </div>

                      <div className="criteria-group performance-criteria">
                        <h4>📈 Performance Criteria</h4>
                        <div className="criteria-list">
                          <div className={`criteria-item ${validationData.analysis.sharpe_ratio >= 1.5 ? 'pass' : 'fail'}`}>
                            <div className="criteria-check">
                              {validationData.analysis.sharpe_ratio >= 1.5 ? '✅' : '❌'}
                            </div>
                            <div className="criteria-content">
                              <div className="criteria-title">Sharpe Ratio</div>
                              <div className="criteria-current">
                                Current: {validationData.analysis.sharpe_ratio?.toFixed(2) || 'N/A'}
                              </div>
                              <div className="criteria-target">Target: ≥1.5</div>
                            </div>
                          </div>

                          <div className={`criteria-item ${validationData.analysis.win_rate >= 0.6 ? 'pass' : 'fail'}`}>
                            <div className="criteria-check">
                              {validationData.analysis.win_rate >= 0.6 ? '✅' : '❌'}
                            </div>
                            <div className="criteria-content">
                              <div className="criteria-title">Win Rate</div>
                              <div className="criteria-current">
                                Current: {(validationData.analysis.win_rate * 100).toFixed(1)}%
                              </div>
                              <div className="criteria-target">Target: ≥60%</div>
                            </div>
                          </div>

                          <div className={`criteria-item ${validationData.analysis.profit_factor >= 1.5 ? 'pass' : 'fail'}`}>
                            <div className="criteria-check">
                              {validationData.analysis.profit_factor >= 1.5 ? '✅' : '❌'}
                            </div>
                            <div className="criteria-content">
                              <div className="criteria-title">Profit Factor</div>
                              <div className="criteria-current">
                                Current: {validationData.analysis.profit_factor?.toFixed(2) || 'N/A'}
                              </div>
                              <div className="criteria-target">Target: ≥1.5</div>
                            </div>
                          </div>
                        </div>
                      </div>

                      <div className="criteria-group statistical-criteria">
                        <h4>🔬 Statistical Criteria</h4>
                        <div className="criteria-list">
                          <div className={`criteria-item ${validationData.analysis.statistical_significance ? 'pass' : 'fail'}`}>
                            <div className="criteria-check">
                              {validationData.analysis.statistical_significance ? '✅' : '❌'}
                            </div>
                            <div className="criteria-content">
                              <div className="criteria-title">Statistical Significance</div>
                              <div className="criteria-current">
                                Current: p = {validationData.analysis.p_value?.toFixed(4) || 'N/A'}
                              </div>
                              <div className="criteria-target">Target: p &lt; 0.01</div>
                            </div>
                          </div>

                          <div className={`criteria-item ${validationData.analysis.sample_size_adequate ? 'pass' : 'fail'}`}>
                            <div className="criteria-check">
                              {validationData.analysis.sample_size_adequate ? '✅' : '❌'}
                            </div>
                            <div className="criteria-content">
                              <div className="criteria-title">Sample Size Adequacy</div>
                              <div className="criteria-current">
                                Current: {validationData.analysis.total_trades} trades
                              </div>
                              <div className="criteria-target">Target: Adequate for 80% power</div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="readiness-summary">
                      <div className="readiness-score">
                        <div className="score-label">Trading Readiness Score</div>
                        <div className={`score-value ${(() => {
                          const criteria = [
                            Math.abs(validationData.analysis.var_95) / Math.abs(validationData.analysis.best_case) <= 1.5,
                            validationData.analysis.probability_of_profit >= 0.75,
                            Math.abs(validationData.analysis.var_95) <= 5000,
                            validationData.analysis.sharpe_ratio >= 1.5,
                            validationData.analysis.win_rate >= 0.6,
                            validationData.analysis.profit_factor >= 1.5,
                            validationData.analysis.statistical_significance,
                            validationData.analysis.sample_size_adequate
                          ];
                          const passedCriteria = criteria.filter(Boolean).length;
                          const totalCriteria = criteria.length;
                          const score = (passedCriteria / totalCriteria) * 100;
                          return score >= 80 ? 'excellent' : score >= 60 ? 'good' : score >= 40 ? 'warning' : 'poor';
                        })()}`}>
                          {(() => {
                            const criteria = [
                              Math.abs(validationData.analysis.var_95) / Math.abs(validationData.analysis.best_case) <= 1.5,
                              validationData.analysis.probability_of_profit >= 0.75,
                              Math.abs(validationData.analysis.var_95) <= 5000,
                              validationData.analysis.sharpe_ratio >= 1.5,
                              validationData.analysis.win_rate >= 0.6,
                              validationData.analysis.profit_factor >= 1.5,
                              validationData.analysis.statistical_significance,
                              validationData.analysis.sample_size_adequate
                            ];
                            const passedCriteria = criteria.filter(Boolean).length;
                            const totalCriteria = criteria.length;
                            return Math.round((passedCriteria / totalCriteria) * 100);
                          })()}%
                        </div>
                        <div className="score-breakdown">
                          {(() => {
                            const criteria = [
                              Math.abs(validationData.analysis.var_95) / Math.abs(validationData.analysis.best_case) <= 1.5,
                              validationData.analysis.probability_of_profit >= 0.75,
                              Math.abs(validationData.analysis.var_95) <= 5000,
                              validationData.analysis.sharpe_ratio >= 1.5,
                              validationData.analysis.win_rate >= 0.6,
                              validationData.analysis.profit_factor >= 1.5,
                              validationData.analysis.statistical_significance,
                              validationData.analysis.sample_size_adequate
                            ];
                            const passedCriteria = criteria.filter(Boolean).length;
                            const totalCriteria = criteria.length;
                            return `${passedCriteria}/${totalCriteria} criteria met`;
                          })()}
                        </div>
                      </div>

                      <div className="readiness-recommendation">
                        <div className="recommendation-icon">
                          {(() => {
                            const criteria = [
                              Math.abs(validationData.analysis.var_95) / Math.abs(validationData.analysis.best_case) <= 1.5,
                              validationData.analysis.probability_of_profit >= 0.75,
                              Math.abs(validationData.analysis.var_95) <= 5000,
                              validationData.analysis.sharpe_ratio >= 1.5,
                              validationData.analysis.win_rate >= 0.6,
                              validationData.analysis.profit_factor >= 1.5,
                              validationData.analysis.statistical_significance,
                              validationData.analysis.sample_size_adequate
                            ];
                            const passedCriteria = criteria.filter(Boolean).length;
                            const totalCriteria = criteria.length;
                            const score = (passedCriteria / totalCriteria) * 100;
                            return score >= 80 ? '🟢' : score >= 60 ? '🟡' : '🔴';
                          })()}
                        </div>
                        <div className="recommendation-content">
                          <div className="recommendation-title">
                            {(() => {
                              const criteria = [
                                Math.abs(validationData.analysis.var_95) / Math.abs(validationData.analysis.best_case) <= 1.5,
                                validationData.analysis.probability_of_profit >= 0.75,
                                Math.abs(validationData.analysis.var_95) <= 5000,
                                validationData.analysis.sharpe_ratio >= 1.5,
                                validationData.analysis.win_rate >= 0.6,
                                validationData.analysis.profit_factor >= 1.5,
                                validationData.analysis.statistical_significance,
                                validationData.analysis.sample_size_adequate
                              ];
                              const passedCriteria = criteria.filter(Boolean).length;
                              const totalCriteria = criteria.length;
                              const score = (passedCriteria / totalCriteria) * 100;
                              
                              if (score >= 80) return 'READY FOR LIVE TRADING';
                              if (score >= 60) return 'PAPER TRADE FIRST';
                              return 'NOT READY - DO NOT TRADE';
                            })()}
                          </div>
                          <div className="recommendation-text">
                            {(() => {
                              const criteria = [
                                Math.abs(validationData.analysis.var_95) / Math.abs(validationData.analysis.best_case) <= 1.5,
                                validationData.analysis.probability_of_profit >= 0.75,
                                Math.abs(validationData.analysis.var_95) <= 5000,
                                validationData.analysis.sharpe_ratio >= 1.5,
                                validationData.analysis.win_rate >= 0.6,
                                validationData.analysis.profit_factor >= 1.5,
                                validationData.analysis.statistical_significance,
                                validationData.analysis.sample_size_adequate
                              ];
                              const passedCriteria = criteria.filter(Boolean).length;
                              const totalCriteria = criteria.length;
                              const score = (passedCriteria / totalCriteria) * 100;
                              
                              if (score >= 80) return 'All critical criteria met. Strategy is ready for live trading with proper position sizing.';
                              if (score >= 60) return 'Some criteria met. Test with paper trading for 30 days before risking real capital.';
                              return 'Too many criteria failed. Improve strategy performance before considering live trading.';
                            })()}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Walk-Forward Validation */}
                  <div className="walk-forward-section">
                    <h3>🚶 Walk-Forward Validation</h3>
                    <p className="section-subtitle">Strategy robustness testing - does it work on unseen future data?</p>
                    
                    <div className="walk-forward-notice">
                      <div className="notice-icon">ℹ️</div>
                      <div className="notice-content">
                        <div className="notice-title">Simulated Walk-Forward Analysis</div>
                        <div className="notice-text">
                          This shows estimated robustness based on historical performance patterns. 
                          Full walk-forward testing requires time-series splitting of your trade data.
                        </div>
                      </div>
                    </div>

                    <div className="walk-forward-metrics">
                      <div className="wf-metric">
                        <div className="wf-label">Strategy Robustness</div>
                        <div className="wf-value-container">
                          <div className={`wf-value ${validationData.analysis.sharpe_ratio > 1 ? 'excellent' : validationData.analysis.sharpe_ratio > 0.5 ? 'good' : 'poor'}`}>
                            {validationData.analysis.sharpe_ratio > 1 ? '85%' : validationData.analysis.sharpe_ratio > 0.5 ? '65%' : '35%'}
                          </div>
                          <div className="wf-bar">
                            <div 
                              className={`wf-bar-fill ${validationData.analysis.sharpe_ratio > 1 ? 'excellent' : validationData.analysis.sharpe_ratio > 0.5 ? 'good' : 'poor'}`}
                              style={{width: `${validationData.analysis.sharpe_ratio > 1 ? 85 : validationData.analysis.sharpe_ratio > 0.5 ? 65 : 35}%`}}
                            ></div>
                          </div>
                        </div>
                        <div className="wf-description">
                          {validationData.analysis.sharpe_ratio > 1 
                            ? 'Highly robust - likely to work on future data'
                            : validationData.analysis.sharpe_ratio > 0.5 
                            ? 'Moderately robust - some risk of degradation'
                            : 'Low robustness - high risk of failure on new data'
                          }
                        </div>
                      </div>

                      <div className="wf-metric">
                        <div className="wf-label">Out-of-Sample Performance</div>
                        <div className="wf-value-container">
                          <div className={`wf-value ${validationData.analysis.avg_trade > 0 ? 'positive' : 'negative'}`}>
                            {validationData.analysis.avg_trade > 0 ? '+' : ''}{((validationData.analysis.avg_trade || 0) * 0.8).toFixed(0)}%
                          </div>
                          <div className="wf-description-inline">of in-sample performance</div>
                        </div>
                        <div className="wf-description">
                          Estimated performance on unseen data (typically 70-90% of historical performance)
                        </div>
                      </div>

                      <div className="wf-metric">
                        <div className="wf-label">Performance Decay Risk</div>
                        <div className="wf-value-container">
                          <div className={`wf-value ${validationData.analysis.volatility < 50 ? 'good' : 'warning'}`}>
                            {validationData.analysis.volatility < 50 ? 'Low' : 'Medium'}
                          </div>
                        </div>
                        <div className="wf-description">
                          {validationData.analysis.volatility < 50 
                            ? 'Strategy shows consistent performance patterns'
                            : 'Strategy performance varies significantly - higher decay risk'
                          }
                        </div>
                      </div>
                    </div>

                    <div className="walk-forward-recommendation">
                      <div className="wf-rec-icon">
                        {validationData.analysis.sharpe_ratio > 1 ? '✅' : validationData.analysis.sharpe_ratio > 0.5 ? '⚠️' : '❌'}
                      </div>
                      <div className="wf-rec-content">
                        <div className="wf-rec-title">Walk-Forward Recommendation</div>
                        <div className="wf-rec-text">
                          {validationData.analysis.sharpe_ratio > 1 
                            ? 'Strategy appears robust and likely to continue working on future data. Proceed with confidence.'
                            : validationData.analysis.sharpe_ratio > 0.5 
                            ? 'Strategy shows moderate robustness. Monitor performance closely and consider position sizing adjustments.'
                            : 'Strategy shows low robustness. High risk of failure on new data. Consider additional validation or strategy refinement.'
                          }
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Walk-Forward Validation */}
                  {validationData.walk_forward && (
                    <div className="walk-forward-section">
                      <h4>🚶 Walk-Forward Validation</h4>
                      <div className="validation-metrics">
                        <div className="validation-card">
                          <div className="validation-label">Out-of-Sample Performance</div>
                          <div className={`validation-value ${validationData.walk_forward.out_of_sample_performance > 0 ? 'good' : 'bad'}`}>
                            {(validationData.walk_forward.out_of_sample_performance * 100).toFixed(1)}%
                          </div>
                          <div className="validation-help">Performance on unseen data</div>
                        </div>
                        <div className="validation-card">
                          <div className="validation-label">Strategy Robustness</div>
                          <div className={`validation-value ${validationData.walk_forward.robustness_score > 0.7 ? 'good' : 'warning'}`}>
                            {(validationData.walk_forward.robustness_score * 100).toFixed(0)}%
                          </div>
                          <div className="validation-help">Consistency across time periods</div>
                        </div>
                        <div className="validation-card">
                          <div className="validation-label">Performance Decay</div>
                          <div className={`validation-value ${validationData.walk_forward.performance_decay < 0.1 ? 'good' : 'warning'}`}>
                            {(validationData.walk_forward.performance_decay * 100).toFixed(1)}%
                          </div>
                          <div className="validation-help">Strategy degradation rate</div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Market Correlation */}
                  {validationData.market_correlation && (
                    <div className="correlation-section">
                      <h4>📊 Market Correlation Analysis</h4>
                      <div className="correlation-grid">
                        <div className="correlation-card">
                          <div className="correlation-label">SPY Correlation</div>
                          <div className={`correlation-value ${Math.abs(validationData.market_correlation.correlation_spy) < 0.3 ? 'good' : 'warning'}`}>
                            {validationData.market_correlation.correlation_spy?.toFixed(3) || 'N/A'}
                          </div>
                        </div>
                        <div className="correlation-card">
                          <div className="correlation-label">QQQ Correlation</div>
                          <div className={`correlation-value ${Math.abs(validationData.market_correlation.correlation_qqq) < 0.3 ? 'good' : 'warning'}`}>
                            {validationData.market_correlation.correlation_qqq?.toFixed(3) || 'N/A'}
                          </div>
                        </div>
                        <div className="correlation-card">
                          <div className="correlation-label">Beta Coefficient</div>
                          <div className="correlation-value">
                            {validationData.market_correlation.beta_spy?.toFixed(3) || 'N/A'}
                          </div>
                        </div>
                        <div className="correlation-card">
                          <div className="correlation-label">Alpha Generation</div>
                          <div className={`correlation-value ${validationData.market_correlation.alpha > 0 ? 'good' : 'bad'}`}>
                            {(validationData.market_correlation.alpha * 100).toFixed(2)}%
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Recommendation Summary */}
                  <div className="recommendation-summary">
                    <h4>💡 Validation Summary</h4>
                    <div className="summary-content">
                      {validationData.analysis?.statistical_significance ? (
                        <div className="summary-item good">
                          ✅ This time-bin shows statistically significant performance (p &lt; 0.05)
                        </div>
                      ) : (
                        <div className="summary-item bad">
                          ❌ This time-bin lacks statistical significance - results may be due to chance
                        </div>
                      )}
                      
                      {validationData.walk_forward?.robustness_score > 0.7 ? (
                        <div className="summary-item good">
                          ✅ Strategy shows high robustness in walk-forward testing
                        </div>
                      ) : (
                        <div className="summary-item warning">
                          ⚠️ Strategy shows moderate robustness - monitor performance closely
                        </div>
                      )}
                      
                      {validationData.market_correlation && Math.abs(validationData.market_correlation.correlation_spy) < 0.3 ? (
                        <div className="summary-item good">
                          ✅ Strategy appears market-neutral (low correlation with SPY)
                        </div>
                      ) : (
                        <div className="summary-item warning">
                          ⚠️ Strategy may be correlated with market movements
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {!isLoadingValidation && !validationData && selectedSymbol && (
                <div className="no-validation-data">
                  <h4>⚠️ Validation Data Unavailable</h4>
                  <p>Unable to load validation analytics for this time-bin. This may be due to:</p>
                  <ul>
                    <li>Insufficient historical data for statistical analysis</li>
                    <li>API endpoints not fully configured</li>
                    <li>Time-bin specific analysis still processing</li>
                  </ul>
                  <button 
                    onClick={() => fetchStrategyValidationData()}
                    className="retry-btn"
                  >
                    🔄 Retry Analysis
                  </button>
                </div>
              )}
            </div>
          )}

          {activeTab === 'backtest' && (
            <div className="backtest-section">
              <div className="backtest-header">
                <h2>📈 Historical Backtest</h2>
                <p>Run a comprehensive backtest using the recommended time bins from the matrix</p>
              </div>

              <div className="backtest-config">
                <div className="config-section">
                  <h3>Backtest Configuration</h3>
                  
                  <div className="config-grid">
                    <div className="config-group">
                      <label>Start Date</label>
                      <input
                        type="date"
                        value={backtestConfig.startDate}
                        onChange={(e) => setBacktestConfig(prev => ({...prev, startDate: e.target.value}))}
                      />
                    </div>
                    
                    <div className="config-group">
                      <label>End Date</label>
                      <input
                        type="date"
                        value={backtestConfig.endDate}
                        onChange={(e) => setBacktestConfig(prev => ({...prev, endDate: e.target.value}))}
                      />
                    </div>
                    
                    <div className="config-group">
                      <label>Initial Capital ($)</label>
                      <input
                        type="number"
                        value={backtestConfig.initialCapital}
                        onChange={(e) => setBacktestConfig(prev => ({...prev, initialCapital: parseFloat(e.target.value) || 100000}))}
                        min="1000"
                        step="1000"
                      />
                    </div>
                    
                    <div className="config-group">
                      <label>Commission per Trade ($)</label>
                      <input
                        type="number"
                        value={backtestConfig.commissionPerTrade}
                        onChange={(e) => setBacktestConfig(prev => ({...prev, commissionPerTrade: parseFloat(e.target.value) || 1.0}))}
                        min="0"
                        step="0.1"
                      />
                    </div>
                    
                    <div className="config-group">
                      <label>Slippage (bps)</label>
                      <input
                        type="number"
                        value={backtestConfig.slippageBps}
                        onChange={(e) => setBacktestConfig(prev => ({...prev, slippageBps: parseInt(e.target.value) || 1}))}
                        min="0"
                        max="100"
                      />
                    </div>
                    
                    <div className="config-group">
                      <label>Method</label>
                      <select
                        value={backtestConfig.method}
                        onChange={(e) => setBacktestConfig(prev => ({...prev, method: e.target.value as 'simple_historical' | 'walk_forward'}))}
                      >
                        <option value="simple_historical">Simple Historical</option>
                        <option value="walk_forward">Walk Forward</option>
                      </select>
                    </div>
                  </div>

                  {backtestConfig.method === 'walk_forward' && (
                    <div className="walk-forward-config">
                      <h4>Walk-Forward Parameters</h4>
                      <div className="config-grid">
                        <div className="config-group">
                          <label>Training Days</label>
                          <input
                            type="number"
                            value={backtestConfig.trainingDays}
                            onChange={(e) => setBacktestConfig(prev => ({...prev, trainingDays: parseInt(e.target.value) || 30}))}
                            min="7"
                          />
                        </div>
                        
                        <div className="config-group">
                          <label>Testing Days</label>
                          <input
                            type="number"
                            value={backtestConfig.testingDays}
                            onChange={(e) => setBacktestConfig(prev => ({...prev, testingDays: parseInt(e.target.value) || 7}))}
                            min="1"
                          />
                        </div>
                        
                        <div className="config-group">
                          <label>Rebalance Frequency</label>
                          <select
                            value={backtestConfig.rebalanceFrequency}
                            onChange={(e) => setBacktestConfig(prev => ({...prev, rebalanceFrequency: e.target.value as 'daily' | 'weekly' | 'monthly'}))}
                          >
                            <option value="daily">Daily</option>
                            <option value="weekly">Weekly</option>
                            <option value="monthly">Monthly</option>
                          </select>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                <div className="backtest-actions">
                  <button
                    className="run-backtest-btn"
                    onClick={runBacktest}
                    disabled={isRunningBacktest || !selectedSymbol}
                  >
                    {isRunningBacktest ? '⏳ Running Backtest...' : '🚀 Run Backtest'}
                  </button>
                  
                  {backtestStatus && (
                    <div className="backtest-progress">
                      <div className="progress-info">
                        <span>Status: {backtestStatus.status}</span>
                        <span>Progress: {(backtestStatus.progress * 100).toFixed(1)}%</span>
                      </div>
                      <div className="progress-bar">
                        <div 
                          className="progress-fill" 
                          style={{width: `${backtestStatus.progress * 100}%`}}
                        ></div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {backtestError && (
                <div className="backtest-error">
                  <h4>❌ Backtest Error</h4>
                  <p>{backtestError}</p>
                </div>
              )}

              {backtestResults && (
                <div className="backtest-results">
                  <div className="results-header">
                    <h3>📊 Backtest Results</h3>
                    <div className="results-summary">
                      <span>Period: {backtestResults.configuration.start_date} to {backtestResults.configuration.end_date}</span>
                      <span>Method: {backtestResults.method}</span>
                    </div>
                  </div>

                  <div className="results-metrics">
                    <div className="metric-card">
                      <div className="metric-label">Total Return</div>
                      <div className={`metric-value ${backtestResults.overall_result.total_return > 0 ? 'positive' : 'negative'}`}>
                        {formatCurrency(backtestResults.overall_result.total_return)}
                      </div>
                    </div>
                    
                    <div className="metric-card">
                      <div className="metric-label">Total Trades</div>
                      <div className="metric-value">{backtestResults.overall_result.total_trades}</div>
                    </div>
                    
                    <div className="metric-card">
                      <div className="metric-label">Win Rate</div>
                      <div className={`metric-value ${backtestResults.overall_result.win_rate > 0.5 ? 'good' : 'neutral'}`}>
                        {(backtestResults.overall_result.win_rate * 100).toFixed(1)}%
                      </div>
                    </div>
                    
                    <div className="metric-card">
                      <div className="metric-label">Sharpe Ratio</div>
                      <div className={`metric-value ${backtestResults.overall_result.sharpe_ratio > 1 ? 'good' : 'neutral'}`}>
                        {backtestResults.overall_result.sharpe_ratio?.toFixed(2) || 'N/A'}
                      </div>
                    </div>
                    
                    <div className="metric-card">
                      <div className="metric-label">Max Drawdown</div>
                      <div className="metric-value negative">
                        {(backtestResults.overall_result.max_drawdown * 100).toFixed(2)}%
                      </div>
                    </div>
                    
                    <div className="metric-card">
                      <div className="metric-label">Profit Factor</div>
                      <div className={`metric-value ${backtestResults.overall_result.profit_factor > 1.5 ? 'excellent' : backtestResults.overall_result.profit_factor > 1 ? 'good' : 'poor'}`}>
                        {backtestResults.overall_result.profit_factor?.toFixed(2) || 'N/A'}
                      </div>
                    </div>
                  </div>

                  {backtestResults.overall_result.daily_returns && backtestResults.overall_result.daily_returns.length > 0 && (
                    <div className="equity-curve">
                      <h4>Equity Curve</h4>
                      <InteractiveChart
                        data={backtestResults.overall_result.daily_returns.map((ret: any, index: number) => ({
                          date: new Date(Date.now() - (backtestResults.overall_result.daily_returns.length - index) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
                          daily_pnl: ret.daily_return * backtestConfig.initialCapital,
                          cumulative_pnl: ret.cumulative_return * backtestConfig.initialCapital
                        }))}
                        formatCurrency={formatCurrency}
                      />
                    </div>
                  )}

                  {backtestResults.period_results && backtestResults.period_results.length > 0 && (
                    <div className="period-results">
                      <h4>Period Breakdown</h4>
                      <div className="period-table">
                        <table>
                          <thead>
                            <tr>
                              <th>Period</th>
                              <th>Return</th>
                              <th>Trades</th>
                              <th>Win Rate</th>
                              <th>Sharpe</th>
                              <th>Max DD</th>
                            </tr>
                          </thead>
                          <tbody>
                            {backtestResults.period_results.map((period: any, index: number) => (
                              <tr key={index}>
                                <td>{period.start_date} - {period.end_date}</td>
                                <td className={period.total_return > 0 ? 'positive' : 'negative'}>
                                  {formatCurrency(period.total_return)}
                                </td>
                                <td>{period.total_trades}</td>
                                <td>{(period.win_rate * 100).toFixed(1)}%</td>
                                <td>{period.sharpe_ratio?.toFixed(2) || 'N/A'}</td>
                                <td className="negative">{(period.max_drawdown * 100).toFixed(2)}%</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === 'matrix' && (
            <div className="matrix-section">
            <h2>Best Account Recommendations by Time & Day</h2>
            <p>Shows the best performing account for each 30-minute time slot and day of the week</p>
            
            <div className="matrix-stats">
              <div className="populated-count">
                <strong>
                  {Object.keys(matrix).reduce((total, timeSlot) => {
                    return total + Object.keys(matrix[timeSlot] || {}).length;
                  }, 0)} / {getTimeSlots().length * 6}
                </strong> time slots with recommendations
                <small>
                  ({((Object.keys(matrix).reduce((total, timeSlot) => {
                    return total + Object.keys(matrix[timeSlot] || {}).length;
                  }, 0) / (getTimeSlots().length * 6)) * 100).toFixed(1)}% of all possible slots)
                </small>
              </div>
              <div className="filter-info">
                <small>
                  Filters: ≥${filterSettings.minAvgProfit} avg profit, 
                  ≥{filterSettings.minWinRate}% win rate, 
                  ≥{filterSettings.minTrades} trades per slot
                </small>
              </div>
            </div>
            
            <div className="matrix-container">
              <table style={{
                width: '100%',
                minWidth: '800px',
                border: '1px solid #d1d5db',
                borderRadius: '0.375rem',
                borderCollapse: 'separate',
                borderSpacing: '0',
                overflow: 'hidden',
                fontSize: '10px'
              }}>
                <thead>
                  <tr style={{ background: '#f9fafb' }}>
                    <th style={{
                      padding: '4px 8px',
                      fontWeight: '600',
                      color: '#374151',
                      fontSize: '11px',
                      textAlign: 'center',
                      borderRight: '1px solid #d1d5db',
                      borderBottom: '1px solid #d1d5db',
                      width: '80px'
                    }}>Time</th>
                    {dayNames.map((day, index) => (
                      <th key={index} style={{
                        padding: '4px 8px',
                        fontWeight: '600',
                        color: '#374151',
                        fontSize: '11px',
                        textAlign: 'center',
                        borderRight: index < dayNames.length - 1 ? '1px solid #d1d5db' : 'none',
                        borderBottom: '1px solid #d1d5db'
                      }}>{day}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {getFilteredTimeSlots().map((timeSlot, index) => {
                    const currentHour = timeSlot.split(':')[0];
                    const currentMinute = timeSlot.split(':')[1];
                    const nextTimeSlot = index < getFilteredTimeSlots().length - 1 ? getFilteredTimeSlots()[index + 1] : null;
                    const nextHour = nextTimeSlot ? nextTimeSlot.split(':')[0] : null;
                    const prevTimeSlot = index > 0 ? getFilteredTimeSlots()[index - 1] : null;
                    const prevHour = prevTimeSlot ? prevTimeSlot.split(':')[0] : null;
                    
                    const isNewHour = currentHour !== prevHour;
                    const isLastInHour = currentHour !== nextHour;
                    const isFirstRow = index === 0;
                    
                    return (
                      <tr key={timeSlot} style={{ 
                        borderBottom: isLastInHour ? '2px solid #6b7280' : '1px solid #e5e7eb',
                        borderTop: (isNewHour && !isFirstRow) ? '2px solid #6b7280' : 'none'
                      }}>
                        <td style={{
                          padding: '6px 8px',
                          background: '#f9fafb',
                          borderRight: '1px solid #d1d5db',
                          fontWeight: '600',
                          color: '#374151',
                          fontSize: '12px',
                          textAlign: 'center',
                          verticalAlign: 'middle',
                          borderTop: (isNewHour && !isFirstRow) ? '2px solid #6b7280' : 'none',
                          borderBottom: isLastInHour ? '2px solid #6b7280' : '1px solid #e5e7eb'
                        }}>{timeSlot}</td>
                      {[0, 1, 2, 3, 4, 5].map(dayOfWeek => { // 0-5 (Sun-Fri, no Saturday)
                        const cellData = getCellData(timeSlot, dayOfWeek);
                        const cellClass = getCellClass(cellData);
                        const bgColor = cellClass.includes('excellent') ? '#d1fae5' :
                                       cellClass.includes('good') ? '#ecfdf5' :
                                       cellClass.includes('neutral') ? '#fef3c7' :
                                       cellClass.includes('poor') ? '#fee2e2' : '#f9fafb';
                        const borderLeft = cellClass.includes('excellent') ? '3px solid #10b981' :
                                          cellClass.includes('good') ? '3px solid #22c55e' :
                                          cellClass.includes('neutral') ? '3px solid #f59e0b' :
                                          cellClass.includes('poor') ? '3px solid #ef4444' : 'none';
                        
                        return (
                          <td key={dayOfWeek} style={{
                            padding: '4px 6px',
                            borderRight: dayOfWeek < 5 ? '1px solid #d1d5db' : 'none',
                            textAlign: 'center',
                            verticalAlign: 'middle',
                            fontSize: '10px',
                            lineHeight: '1.2',
                            background: bgColor,
                            borderLeft: borderLeft,
                            borderTop: (isNewHour && !isFirstRow) ? '2px solid #6b7280' : 'none',
                            borderBottom: isLastInHour ? '2px solid #6b7280' : '1px solid #e5e7eb',
                            cursor: cellData ? 'pointer' : 'default',
                            transition: 'all 0.2s ease'
                          }}

                          >
                            {cellData ? (
                              <div style={{ textAlign: 'center' }}>
                                <div style={{ fontWeight: '600', fontSize: '11px', color: '#374151', marginBottom: '2px' }}>
                                  {cellData.best_account}
                                </div>
                                <div style={{ fontSize: '10px', color: '#374151' }}>
                                  {formatCurrency(cellData.avg_trade)}, {cellData.win_rate.toFixed(1)}%
                                </div>

                              </div>
                            ) : (
                              <div style={{ color: '#9ca3af', fontSize: '12px' }}>-</div>
                            )}
                          </td>
                        );
                      })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
          )}

          {/* Strategy Explanation */}
          <div className="strategy-explanation">
            <h3>📊 How This Strategy Works</h3>
            <div className="explanation-content">
              <div className="step">
                <span className="step-number">1</span>
                <div className="step-content">
                  <strong>System analyzes data</strong> and creates a recommendation matrix: "At 10:00 AM on Mondays, use account IPS_TM_6"
                </div>
              </div>
              <div className="step">
                <span className="step-number">2</span>
                <div className="step-content">
                  <strong>Strategy only trades</strong> when the actual trade matches the recommendation (right account + right time slot)
                </div>
              </div>
              <div className="step">
                <span className="step-number">3</span>
                <div className="step-content">
                  <strong>Chart shows results</strong> of this selective trading approach vs. trading everything
                </div>
              </div>
            </div>
          </div>

          {/* Historical P&L Chart */}
          <div className="backtest-section">
            <div className="chart-header">
              <div className="chart-title">
                <h2>Strategy Performance ({getTimeHorizonLabel(timeHorizon)})</h2>
                <p>P&L from only trading when the system recommends that account for that time slot</p>
              </div>
            </div>
            
            {isLoading ? (
              <div className="chart-loading">Loading chart data...</div>
            ) : backtestData && backtestData.length > 0 ? (
              <div className="chart-container">
                <div className="chart-summary">
                  <div className="summary-item">
                    <span className="label">Total P&L:</span>
                    <span className={`value ${(backtestMetadata?.total_pnl || 0) >= 0 ? 'positive' : 'negative'}`}>
                      {formatCurrency(backtestMetadata?.total_pnl || 0)}
                    </span>
                  </div>
                  <div className="summary-item">
                    <span className="label">Trades Followed:</span>
                    <span className="value">{backtestMetadata?.total_trades_followed || 0}</span>
                  </div>
                  <div className="summary-item">
                    <span className="label">Trading Days:</span>
                    <span className="value">
                      {backtestData.length > 0 
                        ? new Set(backtestData.map(d => d.date)).size 
                        : 0
                      }
                    </span>
                  </div>
                  <div className="summary-item">
                    <span className="label">Avg Per Trade:</span>
                    <span className="value">
                      {backtestMetadata?.total_trades_followed > 0 
                        ? formatCurrency((backtestMetadata?.total_pnl || 0) / backtestMetadata.total_trades_followed)
                        : '$0.00'
                      }
                    </span>
                  </div>
                </div>
                
                {/* Interactive Chart */}
                <InteractiveChart 
                  data={backtestData}
                  formatCurrency={formatCurrency}
                  width={1400}
                  height={600}
                />

                {/* Daily P&L Bar Chart - Right below the main chart */}
                <div className="bar-chart-container">
                  <h4>Daily P&L Distribution</h4>
                  <div className="simple-chart">
                    {backtestData.length > 0 ? (
                      backtestData.map((point, index) => (
                        <div key={index} className="chart-point" title={`${point.date}: ${formatCurrency(point.daily_pnl)}`}>
                          <div 
                            className={`bar ${point.daily_pnl >= 0 ? 'positive' : 'negative'}`}
                            style={{
                              height: `${Math.min(Math.max(Math.abs(point.daily_pnl) / 20 + 10, 15), 80)}px`
                            }}
                          />
                        </div>
                      ))
                    ) : (
                      <div style={{ color: '#6b7280', fontSize: '14px', padding: '20px' }}>
                        No distribution data available
                      </div>
                    )}
                  </div>
                </div>

                {/* Recommendation Following Performance Summary */}
                {backtestMetadata && (
                  <div className="backtest-summary">
                    <h3>Strategy Performance</h3>
                    <p>Results if you only traded when the system recommended that specific account for that time slot</p>
                    
                    <div className="summary-grid">
                      <div className="summary-card">
                        <h4>Trading Activity</h4>
                        <div className="summary-item">
                          <span className="label">Total Trades Available:</span>
                          <span className="value">{backtestMetadata.total_trades_available}</span>
                        </div>
                        <div className="summary-item">
                          <span className="label">Strategy Trades:</span>
                          <span className="value">{backtestMetadata.total_trades_followed}</span>
                        </div>
                        <div className="summary-item">
                          <span className="label">Strategy Selectivity:</span>
                          <span className="value">
                            {backtestMetadata.total_trades_available > 0 
                              ? ((backtestMetadata.total_trades_followed / backtestMetadata.total_trades_available) * 100).toFixed(1) + '%'
                              : '0%'
                            }
                          </span>
                        </div>
                      </div>

                      <div className="summary-card">
                        <h4>Financial Performance</h4>
                        <div className="summary-item">
                          <span className="label">Total P&L:</span>
                          <span className={`value ${backtestMetadata.total_pnl >= 0 ? 'positive' : 'negative'}`}>
                            {formatCurrency(backtestMetadata.total_pnl)}
                          </span>
                        </div>
                        <div className="summary-item">
                          <span className="label">Average Per Trade:</span>
                          <span className="value">
                            {backtestMetadata.total_trades_followed > 0 
                              ? formatCurrency(backtestMetadata.total_pnl / backtestMetadata.total_trades_followed)
                              : '$0.00'
                            }
                          </span>
                        </div>
                        <div className="summary-item">
                          <span className="label">Trading Days:</span>
                          <span className="value">
                            {getExpectedTradingDays(timeHorizon)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Time-Filtered Statistics */}
                <div className="time-filtered-stats">
                  <div className="stats-header">
                    <h3>📊 Strategy Statistics for {getTimeHorizonLabel(timeHorizon)}</h3>
                    <button onClick={exportTradesToCSV} className="export-btn" disabled={!backtestMetadata}>
                      📥 Export Trades CSV
                    </button>
                  </div>
                  <p>Performance statistics for the selected time period and optimal time slots only</p>
                  
                  {timeFilteredStats ? (
                    <div className="filtered-stats-grid">
                      <div className="filtered-stat-card">
                        <h4>Strategy Performance</h4>
                        <div className="stat-row">
                          <span className="stat-label">Total P&L:</span>
                          <span className={`stat-value ${timeFilteredStats.combined_metrics.total_pnl >= 0 ? 'positive' : 'negative'}`}>
                            {formatCurrency(timeFilteredStats.combined_metrics.total_pnl)}
                          </span>
                        </div>
                        <div className="stat-row">
                          <span className="stat-label">Total Trades:</span>
                          <span className="stat-value">{timeFilteredStats.combined_metrics.total_trades}</span>
                        </div>
                        <div className="stat-row">
                          <span className="stat-label">Win Rate:</span>
                          <span className={`stat-value ${timeFilteredStats.combined_metrics.win_rate >= 50 ? 'positive' : 'negative'}`}>
                            {timeFilteredStats.combined_metrics.win_rate.toFixed(1)}%
                          </span>
                        </div>
                        <div className="stat-row">
                          <span className="stat-label">Average Trade:</span>
                          <span className={`stat-value ${timeFilteredStats.combined_metrics.avg_trade >= 0 ? 'positive' : 'negative'}`}>
                            {formatCurrency(timeFilteredStats.combined_metrics.avg_trade)}
                          </span>
                        </div>
                      </div>

                      <div className="filtered-stat-card">
                        <h4>Risk Analysis</h4>
                        <div className="stat-row">
                          <span className="stat-label">Profit Factor:</span>
                          <span className={`stat-value ${timeFilteredStats.combined_metrics.profit_factor >= 1 ? 'positive' : 'negative'}`}>
                            {timeFilteredStats.combined_metrics.profit_factor.toFixed(2)}
                          </span>
                        </div>
                        <div className="stat-row">
                          <span className="stat-label">Sharpe Ratio:</span>
                          <span className={`stat-value ${timeFilteredStats.combined_metrics.sharpe_ratio >= 1 ? 'positive' : 'negative'}`}>
                            {timeFilteredStats.combined_metrics.sharpe_ratio.toFixed(2)}
                          </span>
                        </div>
                        <div className="stat-row">
                          <span className="stat-label">Max Drawdown:</span>
                          <span className="stat-value negative">{formatCurrency(timeFilteredStats.combined_metrics.max_drawdown)}</span>
                        </div>
                        <div className="stat-row">
                          <span className="stat-label">Largest Winner:</span>
                          <span className="stat-value positive">{formatCurrency(timeFilteredStats.combined_metrics.largest_winner)}</span>
                        </div>
                      </div>

                      <div className="filtered-stat-card">
                        <h4>Trading Details</h4>
                        <div className="stat-row">
                          <span className="stat-label">Winning Trades:</span>
                          <span className="stat-value positive">{timeFilteredStats.combined_metrics.winning_trades}</span>
                        </div>
                        <div className="stat-row">
                          <span className="stat-label">Losing Trades:</span>
                          <span className="stat-value negative">{timeFilteredStats.combined_metrics.losing_trades}</span>
                        </div>
                        <div className="stat-row">
                          <span className="stat-label">Average Winner:</span>
                          <span className="stat-value positive">{formatCurrency(timeFilteredStats.combined_metrics.avg_winner)}</span>
                        </div>
                        <div className="stat-row">
                          <span className="stat-label">Average Loser:</span>
                          <span className="stat-value negative">{formatCurrency(timeFilteredStats.combined_metrics.avg_loser)}</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="loading-stats">Loading time-filtered statistics...</div>
                  )}
                </div>


              </div>
            ) : (
              <div className="no-data">
                <p>No chart data available for selected time horizon</p>
                <small style={{ color: '#6b7280', fontSize: '11px' }}>
                  Debug: backtestData length = {backtestData ? backtestData.length : 'null'}, 
                  isLoading = {isLoading.toString()},
                  symbol = {selectedSymbol},
                  timeHorizon = {timeHorizon}
                </small>
              </div>
            )}
          </div>

          {/* Combined Statistics */}
          {combinedStats && (
            <div className="stats-section">
              <h2>Account Performance Breakdown for {selectedSymbol}</h2>
              <p>Total performance of each recommended account: {combinedStats.recommended_accounts.join(', ')}</p>
              <div className="stats-note">
                <small>
                  ⚠️ <strong>Important:</strong> This section shows ALL historical trades from these recommended accounts, regardless of time slots or the time horizon selected above.
                  <br/>
                  • <strong>Time Period:</strong> Complete trading history (not filtered by your time selection)
                  • <strong>Trades Included:</strong> Every trade these accounts made, not just optimal time slots
                  • <strong>Purpose:</strong> Shows overall account performance vs. the selective strategy performance in the chart
                </small>
              </div>
              
              <div className="stats-grid">
                <div className="stat-card">
                  <h4>Trading Performance</h4>
                  <div className="stat-item">
                    <span className="stat-label">Total Trades:</span>
                    <span className="stat-value">{combinedStats.combined_metrics.total_trades}</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Win Rate:</span>
                    <span className={`stat-value ${combinedStats.combined_metrics.win_rate >= 50 ? 'positive' : 'negative'}`}>
                      {combinedStats.combined_metrics.win_rate.toFixed(1)}%
                    </span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Winning Trades:</span>
                    <span className="stat-value positive">{combinedStats.combined_metrics.winning_trades}</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Losing Trades:</span>
                    <span className="stat-value negative">{combinedStats.combined_metrics.losing_trades}</span>
                  </div>
                </div>

                <div className="stat-card">
                  <h4>Financial Metrics</h4>
                  <div className="stat-item">
                    <span className="stat-label">Total P&L:</span>
                    <span className={`stat-value ${combinedStats.combined_metrics.total_pnl >= 0 ? 'positive' : 'negative'}`}>
                      {formatCurrency(combinedStats.combined_metrics.total_pnl)}
                    </span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Average Trade:</span>
                    <span className={`stat-value ${combinedStats.combined_metrics.avg_trade >= 0 ? 'positive' : 'negative'}`}>
                      {formatCurrency(combinedStats.combined_metrics.avg_trade)}
                    </span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Average Winner:</span>
                    <span className="stat-value positive">{formatCurrency(combinedStats.combined_metrics.avg_winner)}</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Average Loser:</span>
                    <span className="stat-value negative">{formatCurrency(combinedStats.combined_metrics.avg_loser)}</span>
                  </div>
                </div>

                <div className="stat-card">
                  <h4>Risk Metrics</h4>
                  <div className="stat-item">
                    <span className="stat-label">Profit Factor:</span>
                    <span className={`stat-value ${combinedStats.combined_metrics.profit_factor >= 1 ? 'positive' : 'negative'}`}>
                      {combinedStats.combined_metrics.profit_factor.toFixed(2)}
                    </span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Sharpe Ratio:</span>
                    <span className={`stat-value ${combinedStats.combined_metrics.sharpe_ratio >= 1 ? 'positive' : 'negative'}`}>
                      {combinedStats.combined_metrics.sharpe_ratio.toFixed(2)}
                    </span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Max Drawdown:</span>
                    <span className="stat-value negative">{formatCurrency(combinedStats.combined_metrics.max_drawdown)}</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Largest Winner:</span>
                    <span className="stat-value positive">{formatCurrency(combinedStats.combined_metrics.largest_winner)}</span>
                  </div>
                </div>

                <div className="stat-card">
                  <h4>Account Breakdown</h4>
                  {combinedStats.account_breakdown.map(account => (
                    <div key={account.account_name} className="account-breakdown-item">
                      <div className="account-name">{account.account_name}</div>
                      <div className="account-stats">
                        <span>{account.total_trades} trades</span>
                        <span className={account.total_pnl >= 0 ? 'positive' : 'negative'}>
                          {formatCurrency(account.total_pnl)}
                        </span>
                        <span>{account.win_rate.toFixed(1)}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Recommendations;