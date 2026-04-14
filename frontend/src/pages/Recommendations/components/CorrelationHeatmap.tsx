import React, { useState } from 'react';
import { getApiV1BaseUrl } from '../../../services/api';

interface CorrelationData {
    accounts: string[];
    period_start: string;
    period_end: string;
    correlation_matrix: { [a: string]: { [b: string]: number } };
    p_value_matrix: { [a: string]: { [b: string]: number } };
    overlapping_days_matrix: { [a: string]: { [b: string]: number } };
    strongest_correlation: { accounts: string[]; correlation: number } | null;
    weakest_correlation: { accounts: string[]; correlation: number } | null;
    average_correlation: number;
    diversification_score: number;
    high_correlation_warnings: { accounts: string[]; correlation: number }[];
}

interface Props {
    symbol: string;
    candidateAccounts?: string[];
    formatCurrency?: (v: number) => string;
}

function corrToColor(val: number): string {
    // -1 = blue, 0 = dark gray, +1 = red
    if (val >= 0) {
        const r = Math.round(200 + 55 * val);
        const g = Math.round(40 - 40 * val);
        const b = Math.round(40 - 40 * val);
        return `rgb(${r},${g},${b})`;
    } else {
        const absVal = Math.abs(val);
        const r = Math.round(40 - 40 * absVal);
        const g = Math.round(80 - 40 * absVal);
        const b = Math.round(200 + 55 * absVal);
        return `rgb(${r},${g},${b})`;
    }
}

function corrTextColor(val: number): string {
    return Math.abs(val) > 0.5 ? '#fff' : '#e2e8f0';
}

const CorrelationHeatmap: React.FC<Props> = ({ symbol, candidateAccounts = [] }) => {
    const [accountInput, setAccountInput] = useState(candidateAccounts.join(', '));
    const [isLoading, setIsLoading] = useState(false);
    const [data, setData] = useState<CorrelationData | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [hovered, setHovered] = useState<{ a: string; b: string } | null>(null);

    const normalizeAccount = (s: string) => {
        let t = s.trim();
        while (t.includes('  ')) t = t.replace(/  /g, ' ');
        return t.replace(/\s+/g, '_');
    };

    const runCorrelation = async () => {
        const raw = accountInput.split(',').map(a => normalizeAccount(a)).filter(Boolean);
        const accounts = Array.from(new Set(raw));
        if (accounts.length < 2) {
            setError('Enter at least 2 distinct account names (comma-separated). Spaces are converted to underscores (e.g. TM_D-R-1_2).');
            return;
        }
        setIsLoading(true);
        setError(null);
        setData(null);
        try {
            const params = new URLSearchParams({ account_names: accounts.join(',') });
            const token = localStorage.getItem('authToken');
            const headers: HeadersInit = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;
            const resp = await fetch(`${getApiV1BaseUrl()}/analytics/correlation?${params}`, { headers });
            const json = await resp.json().catch(() => ({}));
            if (!resp.ok) {
                const detail = typeof json.detail === 'string' ? json.detail : (json.message || JSON.stringify(json.detail || json));
                setError(detail || `HTTP ${resp.status}`);
                return;
            }
            if (json.status === 'success') {
                setData(json.data);
            } else {
                setError(json.message || 'Correlation failed');
            }
        } catch (err: any) {
            setError(String(err));
        } finally {
            setIsLoading(false);
        }
    };

    // Sync candidateAccounts prop into input when it changes
    React.useEffect(() => {
        if (candidateAccounts.length > 0) {
            setAccountInput(candidateAccounts.join(', '));
        }
    }, [candidateAccounts.join(',')]);

    const accounts = data?.accounts ?? [];

    return (
        <div style={{ padding: '16px 0' }}>
            {/* Instructions */}
            <div style={{ background: '#0f172a', border: '1px solid #1e2a3a', borderRadius: 8, padding: '10px 16px', marginBottom: 16, fontSize: 12, color: '#94a3b8', lineHeight: 1.7 }}>
                <strong style={{ color: '#e2e8f0' }}>How to use:</strong> Paste <strong>exact</strong> permutation names as stored in imports (same as matrix cells; spaces are normalized to underscores). Comma-separated; duplicates are ignored.
                Each name must have trades in the DB for the selected asset — if you see an error naming one account, check spelling against Trade Import / matrix labels.
                Run the analysis to see which permutations move together.
                Any pair with correlation &gt; 0.7 should not be traded simultaneously — you would be doubling your risk, not diversifying.
                Pairs near 0.0 provide real diversification benefit.
            </div>

            {/* Input */}
            <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
                <textarea
                    value={accountInput}
                    onChange={e => setAccountInput(e.target.value)}
                    rows={2}
                    placeholder="e.g. TM_D-R-1_1, TM_D-R-1_2, TS_6, IPS_TM_10"
                    style={{
                        flex: 1, minWidth: 260, padding: '8px 12px',
                        borderRadius: 8, border: '1px solid #3a4460',
                        background: '#151c2e', color: '#e2e8f0', fontSize: 12,
                        resize: 'vertical',
                    }}
                />
                <button
                    onClick={runCorrelation}
                    disabled={isLoading}
                    style={{
                        padding: '8px 20px', background: isLoading ? '#3a4460' : '#7c3aed',
                        color: '#fff', border: 'none', borderRadius: 8,
                        cursor: isLoading ? 'not-allowed' : 'pointer',
                        fontWeight: 600, fontSize: 13, alignSelf: 'flex-start',
                    }}
                >
                    {isLoading ? 'Computing...' : 'Compute Correlation'}
                </button>
            </div>

            {error && (
                <div style={{ background: '#3b1f1f', border: '1px solid #dc2626', borderRadius: 8, padding: '10px 14px', color: '#fca5a5', marginBottom: 14 }}>
                    {error}
                </div>
            )}

            {data && (
                <>
                    {/* Warnings */}
                    {data.high_correlation_warnings.length > 0 && (
                        <div style={{ background: '#2d1b00', border: '2px solid #f59e0b', borderRadius: 10, padding: '12px 16px', marginBottom: 16 }}>
                            <div style={{ fontWeight: 700, color: '#fbbf24', marginBottom: 6 }}>
                                ⚠ High Correlation Warning — Do NOT trade these pairs simultaneously:
                            </div>
                            {data.high_correlation_warnings.map((w, i) => (
                                <div key={i} style={{ fontSize: 13, color: '#fde68a', marginBottom: 2 }}>
                                    {w.accounts[0]} ↔ {w.accounts[1]}: <strong>{(w.correlation * 100).toFixed(0)}%</strong> correlated
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Summary row */}
                    <div style={{ display: 'flex', gap: 16, marginBottom: 18, flexWrap: 'wrap' }}>
                        {[
                            { label: 'Avg Correlation', value: (data.average_correlation * 100).toFixed(1) + '%', good: data.average_correlation < 0.3 },
                            { label: 'Diversification Score', value: (data.diversification_score * 100).toFixed(0) + '%', good: data.diversification_score > 0.6 },
                            { label: 'High-Corr Pairs', value: String(data.high_correlation_warnings.length), good: data.high_correlation_warnings.length === 0 },
                            data.strongest_correlation ? { label: 'Strongest Pair', value: `${data.strongest_correlation.accounts.join(' / ')}: ${(data.strongest_correlation.correlation * 100).toFixed(0)}%`, good: Math.abs(data.strongest_correlation.correlation) < 0.5 } : null,
                        ].filter(Boolean).map((item, i) => (
                            <div key={i} style={{ background: '#1a2535', borderRadius: 8, padding: '10px 16px', minWidth: 140 }}>
                                <div style={{ fontSize: 11, color: '#94a3b8' }}>{item!.label}</div>
                                <div style={{ fontSize: 15, fontWeight: 700, color: item!.good ? '#4ade80' : '#f87171', marginTop: 2 }}>{item!.value}</div>
                            </div>
                        ))}
                    </div>

                    {/* Heatmap */}
                    <div style={{ overflowX: 'auto' }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0', marginBottom: 8 }}>Correlation Matrix</div>
                        <table style={{ borderCollapse: 'collapse', fontSize: 11 }}>
                            <thead>
                                <tr>
                                    <th style={{ padding: '6px 8px', color: '#64748b' }}></th>
                                    {accounts.map(a => (
                                        <th key={a} style={{ padding: '4px 6px', color: '#94a3b8', fontWeight: 600, maxWidth: 90, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            {a}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {accounts.map(a => (
                                    <tr key={a}>
                                        <td style={{ padding: '4px 8px', color: '#94a3b8', fontWeight: 600, whiteSpace: 'nowrap', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                            {a}
                                        </td>
                                        {accounts.map(b => {
                                            const val = data.correlation_matrix[a]?.[b] ?? 0;
                                            const pval = data.p_value_matrix[a]?.[b] ?? 1;
                                            const days = data.overlapping_days_matrix[a]?.[b] ?? 0;
                                            const isHovered = hovered?.a === a && hovered?.b === b;
                                            const isHighlighted = Math.abs(val) > 0.7 && a !== b;
                                            return (
                                                <td
                                                    key={b}
                                                    style={{
                                                        width: 52, height: 36,
                                                        background: corrToColor(val),
                                                        textAlign: 'center',
                                                        color: corrTextColor(val),
                                                        fontWeight: a === b ? 700 : 400,
                                                        cursor: a !== b ? 'pointer' : 'default',
                                                        outline: isHighlighted ? '2px solid #f59e0b' : isHovered ? '2px solid #e2e8f0' : 'none',
                                                        outlineOffset: '-2px',
                                                        fontSize: a === b ? 11 : 12,
                                                        transition: 'outline 0.1s',
                                                        padding: '2px 4px',
                                                        position: 'relative',
                                                    }}
                                                    onMouseEnter={() => setHovered({ a, b })}
                                                    onMouseLeave={() => setHovered(null)}
                                                    title={a !== b ? `${a} ↔ ${b}: ${val.toFixed(4)} (p=${pval.toFixed(4)}, ${days} overlapping days)` : a}
                                                >
                                                    {a === b ? '—' : val.toFixed(2)}
                                                    {isHighlighted && <span style={{ position: 'absolute', top: 1, right: 2, fontSize: 8 }}>⚠</span>}
                                                </td>
                                            );
                                        })}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {/* Color scale */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, fontSize: 11, color: '#64748b' }}>
                        <span>−1 (inverse)</span>
                        <div style={{ display: 'flex', height: 8, width: 120, borderRadius: 4, overflow: 'hidden' }}>
                            {Array.from({ length: 20 }, (_, i) => {
                                const v = -1 + (i / 19) * 2;
                                return <div key={i} style={{ flex: 1, background: corrToColor(v) }} />;
                            })}
                        </div>
                        <span>+1 (perfect)</span>
                        <span style={{ marginLeft: 16, color: '#f59e0b' }}>⚠ = High (&gt;0.7)</span>
                    </div>

                    {hovered && hovered.a !== hovered.b && (
                        <div style={{ marginTop: 10, background: '#1a2535', borderRadius: 8, padding: '8px 14px', fontSize: 12, color: '#e2e8f0', display: 'inline-block' }}>
                            <strong>{hovered.a}</strong> ↔ <strong>{hovered.b}</strong>:
                            {' '}{(data.correlation_matrix[hovered.a]?.[hovered.b] ?? 0).toFixed(4)} correlation
                            {' '}(p = {(data.p_value_matrix[hovered.a]?.[hovered.b] ?? 1).toFixed(4)},
                            {' '}{data.overlapping_days_matrix[hovered.a]?.[hovered.b] ?? 0} overlapping days)
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

export default CorrelationHeatmap;
