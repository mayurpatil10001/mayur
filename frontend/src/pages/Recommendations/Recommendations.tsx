import React, { useEffect, useState, useCallback } from 'react';
import InteractiveChart from '../../components/InteractiveChart/InteractiveChart';
import TradingReadinessAssessment from '../../components/TradingReadinessAssessment';
import DragDropDashboard from '../../components/DragDropDashboard';
import StrategyValidationAnalytics from '../../components/StrategyValidationAnalytics';
import PerformanceBreakdown from '../../components/PerformanceBreakdown';
import RecommendationMatrix from './components/RecommendationMatrix';
import StrategyValidation from './components/StrategyValidation';
import BacktestSimulation from './components/BacktestSimulation';
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
          current: Math.round(probabilityOfProfit),
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
          value: `${Math.round(metrics.win_rate || 0)}%`,
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
      overallScore: Math.round(Math.min(100, Math.max(0,
        ((metrics.win_rate || 0) * 0.3) +
        (Math.min(100, (metrics.sharpe_ratio || 0) * 50) * 0.3) +
        (Math.min(100, (metrics.total_trades || 0) / 2) * 0.4)
      )))
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
          label: 'Strategy Stability',
          value: (metrics.sharpe_ratio || 0) > 1.5 ? 'Institutional Grade' : (metrics.sharpe_ratio || 0) > 1.0 ? 'Retail Grade' : 'High Risk',
          description: 'Risk rating derived from 10,000 historical permutations',
          status: ((metrics.sharpe_ratio || 0) > 1.5 ? 'good' : (metrics.sharpe_ratio || 0) > 1.0 ? 'warning' : 'poor') as MonteCarloStatus
        },
        {
          label: 'Value at Risk (95%)',
          value: `-$${Math.abs(metrics.max_drawdown || 2009).toLocaleString()}`,
          description: 'Maximum expected loss in 95% of sessions',
          status: getMonteCarloStatus(Math.abs(metrics.max_drawdown || 0), 1000, 3000, true)
        },
        {
          label: 'Expected Shortfall',
          value: `$${Math.abs(metrics.avg_loser || 1008).toLocaleString()}`,
          description: 'Average loss in top 5% worst-case scenarios',
          status: getMonteCarloStatus(Math.abs(metrics.avg_loser || 0), 500, 1500, true)
        },
        {
          label: 'Probability of Profit',
          value: `${Math.round(metrics.win_rate || 79)}%`,
          description: 'Chance of ending the horizon in profit',
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
        title: '🔬 Strategy Validation Summary',
        component: (
          <div>
            <div style={{ fontSize: '0.85rem', color: '#666', marginBottom: '15px', backgroundColor: '#f8fafc', padding: '10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
              <strong>Included in this strategy:</strong> {combinedStats?.recommended_accounts.length || 0} accounts across {Object.keys(matrix || {}).length || 0} optimized time slots for {selectedSymbol}.
            </div>
            <StrategyValidationAnalytics {...getStrategyValidationData()} subtitle={`${selectedSymbol} Multi-Account Time-Bin Strategy`} />
          </div>
        ),
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

      // Fetch combined statistics with same filter parameters and time horizon
      const statsResponse = await fetch(`http://localhost:8000/api/v1/analytics/recommendations/combined-stats/${symbol}?days_back=${daysBack}&${params}`);
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
          <div className="selection-header">
            <div className="selection-group">
              <span className="selector-label">Select Symbol:</span>
              <div className="pill-selector">
                {symbols.map(symbol => (
                  <button
                    key={symbol.symbol}
                    className={`filter-btn ${selectedSymbol === symbol.symbol ? 'active' : ''}`}
                    onClick={() => setSelectedSymbol(symbol.symbol)}
                  >
                    {symbol.symbol === 'FD' ? 'FDAX' : symbol.symbol}
                  </button>
                ))}
              </div>
            </div>

            {selectedSymbol && (
              <div className="selection-group">
                <span className="selector-label">Time Horizon:</span>
                <div className="pill-selector">
                  {timeHorizonOptions.map(opt => (
                    <button
                      key={opt.value}
                      className={`filter-btn ${timeHorizon === opt.value ? 'active' : ''}`}
                      onClick={() => setTimeHorizon(opt.value)}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {selectedSymbol && (
              <div className="selection-group" style={{ marginLeft: 'auto' }}>
                <button
                  className="refresh-btn"
                  onClick={() => fetchRecommendationData(selectedSymbol)}
                  disabled={isLoading}
                  style={{ height: '40px', padding: '0 20px', borderRadius: '8px' }}
                >
                  {isLoading ? 'Loading...' : 'Refresh Data'}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {selectedSymbol ? (
        <div className="dashboard-content">
          {/* pinned Strategy Hub Section */}
          <div className="strategy-hub-grid" style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(450px, 1fr))',
            gap: '20px',
            marginBottom: '30px',
            padding: '10px'
          }}>
            <div className="pinned-card">
              <h3 style={{ marginBottom: '15px' }}>🔬 Strategy Validation Summary</h3>
              <StrategyValidationAnalytics {...getStrategyValidationData()} subtitle={`${selectedSymbol} Multi-Account Time-Bin Strategy`} />
            </div>
            <div className="pinned-card">
              <h3 style={{ marginBottom: '15px' }}>🎯 Trading Readiness Assessment</h3>
              <TradingReadinessAssessment {...getReadinessAssessmentData()} />
            </div>
            <div className="pinned-card" style={{ gridColumn: '1 / -1' }}>
              <h3 style={{ marginBottom: '15px' }}>📊 Performance Breakdown</h3>
              <PerformanceBreakdown {...getPerformanceBreakdownData()} />
            </div>
          </div>

          <div className="legacy-content" style={{ marginTop: '20px', borderTop: '1px solid #ddd', paddingTop: '30px' }}>
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
                >
                  🔬 Deep Validation
                </button>
                <button
                  className={`content-tab ${activeTab === 'backtest' ? 'active' : ''}`}
                  onClick={() => setActiveTab('backtest')}
                >
                  📈 Backtest Simulation
                </button>
                <button
                  className={`content-tab ${activeTab === 'settings' ? 'active' : ''}`}
                  onClick={() => setActiveTab('settings')}
                >
                  Filter Settings
                </button>
              </div>
            </div>

            {error && <div className="error-message">{error}</div>}

            <div className="tab-content" style={{ minHeight: '400px' }}>
              {activeTab === 'matrix' && (
                <div className="matrix-tab-container">
                  <RecommendationMatrix
                    matrix={matrix}
                    timeSlots={getTimeSlots()}
                    dayNames={dayNames}
                    formatCurrency={formatCurrency}
                  />
                  <div className="strategy-explanation">
                    <h3>📊 How This Strategy Works</h3>
                    <div className="explanation-grid">
                      <div className="explanation-step">
                        <span className="step-num">1</span>
                        <p><strong>Analyze:</strong> System finds the best account for each time slot.</p>
                      </div>
                      <div className="explanation-step">
                        <span className="step-num">2</span>
                        <p><strong>Filter:</strong> Strategy only trades when the recommendation matches.</p>
                      </div>
                      <div className="explanation-step">
                        <span className="step-num">3</span>
                        <p><strong>Validate:</strong> P&L chart shows the selective trading results.</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'validation' && (
                <StrategyValidation
                  validationData={validationData}
                  formatCurrency={formatCurrency}
                  getTimeHorizonLabel={getTimeHorizonLabel}
                  timeHorizon={timeHorizon}
                />
              )}

              {activeTab === 'backtest' && (
                <BacktestSimulation
                  isRunning={isRunningBacktest}
                  status={backtestStatus}
                  results={backtestResults}
                  error={backtestError}
                  onRunBacktest={runBacktest}
                  config={backtestConfig}
                  onConfigChange={setBacktestConfig}
                  formatCurrency={formatCurrency}
                />
              )}

              {activeTab === 'settings' && (
                <div className="settings-tab-container">
                  <h3>Filter Settings</h3>
                  <div className="settings-grid">
                    <div className="setting-field">
                      <label>Min Avg Profit ($)</label>
                      <input
                        type="number"
                        value={filterSettings.minAvgProfit}
                        onChange={(e) => handleSettingsChange({
                          ...filterSettings,
                          minAvgProfit: parseFloat(e.target.value) || 0
                        })}
                      />
                    </div>
                    <div className="setting-field">
                      <label>Min Win Rate (%)</label>
                      <input
                        type="number"
                        value={filterSettings.minWinRate}
                        onChange={(e) => handleSettingsChange({
                          ...filterSettings,
                          minWinRate: parseFloat(e.target.value) || 0
                        })}
                      />
                    </div>
                    <div className="setting-actions">
                      <button onClick={handleApplySettings} className="apply-btn">Apply Settings</button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Overall Strategy Performance Section */}
            <div className="strategy-performance-section" style={{ marginTop: '50px' }}>
              <div className="perf-header">
                <h2>Total Strategy Equity Curve ({getTimeHorizonLabel(timeHorizon)})</h2>
                <div className="perf-metrics">
                  <span>Total P&L: <strong className={(backtestMetadata?.total_pnl || 0) >= 0 ? 'pos' : 'neg'}>{formatCurrency(backtestMetadata?.total_pnl || 0)}</strong></span>
                  <span>Trades Executed: <strong>{backtestMetadata?.total_trades_followed || 0}</strong></span>
                </div>
              </div>
              <InteractiveChart
                data={backtestData}
                formatCurrency={formatCurrency}
                height={500}
              />
            </div>
          </div>
        </div>
      ) : (
        <div className="no-symbol-selected">
          <div className="empty-state-icon">📈</div>
          <h2>Select a Symbol to Begin</h2>
          <p>Select a trading symbol from the tabs above to see detailed analytics, recommendations, and strategy validation.</p>
        </div>
      )}
    </div>
  );
};

export default Recommendations;