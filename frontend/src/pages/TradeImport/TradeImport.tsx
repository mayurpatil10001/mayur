import React, { useState } from 'react';
import './TradeImport.css';

interface ParsedTrade {
    account_name: string;
    symbol: string;
    base_symbol: string;
    trade_type: string;
    entry_datetime: string;
    exit_datetime: string;
    entry_price: number;
    exit_price: number;
    quantity: number;
    profit_loss: number;
    commission: number;
    duration: string;
    note: string;
}

interface ImportResult {
    total_parsed: number;
    new_trades?: number;
    duplicates?: number;
    errors: string[];
    trades: ParsedTrade[];
    stats?: Record<string, any>;
}

const TradeImport: React.FC = () => {
    const [pasteText, setPasteText] = useState('');
    const [previewResult, setPreviewResult] = useState<ImportResult | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    const handlePreview = async () => {
        if (!pasteText.trim()) return;
        setIsLoading(true);
        setError(null);
        setSuccessMessage(null);
        try {
            const response = await fetch('/api/v1/trades/import-preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: pasteText }),
            });
            if (!response.ok) throw new Error('Preview failed');
            const data = await response.json();
            setPreviewResult(data);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setIsLoading(false);
        }
    };

    const handleImport = async () => {
        if (!pasteText.trim()) return;
        setIsLoading(true);
        setError(null);
        try {
            const response = await fetch('/api/v1/trades/import-paste', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: pasteText }),
            });
            if (!response.ok) throw new Error('Import failed');
            const data = await response.json();
            setSuccessMessage(`Successfully imported ${data.new_trades} new trades. (${data.duplicates} duplicates skipped)`);
            setPreviewResult(data);
            setPasteText(''); // Clear text on success
        } catch (err: any) {
            setError(err.message);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="trade-import-container">
            <h1>Trade Import (Sierra Chart)</h1>
            <p className="description">
                Paste the contents of your Sierra Chart <strong>TradesList.txt</strong> (26-column format) below.
            </p>

            <div className="input-section">
                <textarea
                    placeholder="Paste tab-delimited trade data here..."
                    value={pasteText}
                    onChange={(e) => setPasteText(e.target.value)}
                    disabled={isLoading}
                />
                <div className="button-group">
                    <button onClick={handlePreview} disabled={isLoading || !pasteText.trim()} className="secondary">
                        Preview
                    </button>
                    <button onClick={handleImport} disabled={isLoading || !pasteText.trim()} className="primary">
                        Import to Database
                    </button>
                </div>
            </div>

            {isLoading && <div className="loading">Processing...</div>}
            {error && <div className="error-message">Error: {error}</div>}
            {successMessage && <div className="success-message">{successMessage}</div>}

            {previewResult && (
                <div className="preview-section">
                    <h2>
                        {previewResult.new_trades !== undefined ? 'Import Result' : 'Import Preview'}
                        <span className="count-badge">{previewResult.total_parsed} trades parsed</span>
                    </h2>

                    {previewResult.errors.length > 0 && (
                        <div className="parsing-errors">
                            <h3>Errors ({previewResult.errors.length})</h3>
                            <ul>
                                {previewResult.errors.map((err, i) => <li key={i}>{err}</li>)}
                            </ul>
                        </div>
                    )}

                    {previewResult.stats && Object.keys(previewResult.stats).length > 0 && (
                        <div className="import-stats-summary">
                            <h3>🛡️ Shield Filter Summary</h3>
                            <div className="stats-grid">
                                {(() => {
                                    const totals = {
                                        outliers: 0,
                                        long_duration: 0,
                                        eod_1700: 0,
                                        future: 0,
                                        price_mismatch: 0
                                    };

                                    Object.values(previewResult.stats).forEach((accStats: any) => {
                                        totals.outliers += accStats.outliers?.count || 0;
                                        totals.long_duration += accStats.long_duration?.count || 0;
                                        totals.eod_1700 += accStats.eod_1700?.count || 0;
                                        totals.future += accStats.future?.count || 0;
                                        totals.price_mismatch += accStats.price_mismatch?.count || 0;
                                    });

                                    return (
                                        <>
                                            {totals.outliers > 0 && (
                                                <div className="stat-item outlier">
                                                    <label>Math Outliers Removed</label>
                                                    <span>{totals.outliers}</span>
                                                </div>
                                            )}
                                            {totals.long_duration > 0 && (
                                                <div className="stat-item">
                                                    <label>Long Duration (&gt;24h)</label>
                                                    <span>{totals.long_duration}</span>
                                                </div>
                                            )}
                                            {totals.eod_1700 > 0 && (
                                                <div className="stat-item">
                                                    <label>EOD 17:00 Gap</label>
                                                    <span>{totals.eod_1700}</span>
                                                </div>
                                            )}
                                            {totals.future > 0 && (
                                                <div className="stat-item">
                                                    <label>Future Trades</label>
                                                    <span>{totals.future}</span>
                                                </div>
                                            )}
                                        </>
                                    );
                                })()}
                            </div>
                        </div>
                    )}

                    <div className="trades-table-container">
                        <table className="trades-table">
                            <thead>
                                <tr>
                                    <th>Account</th>
                                    <th>Symbol</th>
                                    <th>Type</th>
                                    <th>Entry</th>
                                    <th>Exit</th>
                                    <th>P/L</th>
                                </tr>
                            </thead>
                            <tbody>
                                {previewResult.trades.slice(0, 50).map((trade, i) => (
                                    <tr key={i}>
                                        <td title={trade.note}>{trade.account_name.substring(0, 30)}...</td>
                                        <td>{trade.base_symbol}</td>
                                        <td>{trade.trade_type}</td>
                                        <td>{new Date(trade.entry_datetime).toLocaleString()}</td>
                                        <td>{new Date(trade.exit_datetime).toLocaleString()}</td>
                                        <td className={trade.profit_loss >= 0 ? 'pos' : 'neg'}>
                                            ${trade.profit_loss.toFixed(2)}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        {previewResult.trades.length > 50 && (
                            <p className="extra-rows">... and {previewResult.trades.length - 50} more trades</p>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default TradeImport;
