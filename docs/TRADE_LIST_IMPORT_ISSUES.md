# Trade List Import — Known Issues

This document captures the issues encountered when importing Sierra Chart trade data into the platform. **As of now, we cannot reliably import data that matches SC's Trades tab.**

---

## 1. Binary Import (.data files)

| Issue | Cause | Impact |
|-------|-------|--------|
| **Trade list doesn't match SC** | Binary has no Open/Close tag. We use FIFO only. SC uses order-based pairing (ParentInternalOrderID). | Different entry/exit pairing → different trades, different PnL. |
| **Ghost removal** | Pre-FIFO or post-pair removal. Either way, pairing is still FIFO. | Ghosts removed, but remaining trades still don't match SC structure. |

**Bottom line:** Binary import will never match SC's Trades tab without parsing OpenClose/InternalOrderID from the binary (format not documented by SC).

---

## 2. Activity Export (Trade Activity tab → Save Log As)

| Issue | Cause | Impact |
|-------|-------|--------|
| **ParentInternalOrderID often empty** | SC export sometimes omits or leaves blank. | We fall back to FIFO → same pairing mismatch as binary. |
| **Open/Close present but parent link missing** | Export format varies by SC version/settings. | OpenClose column exists but we can't link Close→Open. |

**Bottom line:** Activity export can work when ParentInternalOrderID is populated. When it's empty, we get FIFO fallback → trades don't match SC.

---

## 3. TradesList / Period Stats (26-col paste)

| Issue | Cause | Impact |
|-------|-------|--------|
| **Column order variations** | SC exports differ: "Trade Quantity" vs "Quantity", column positions change. | Parser may mis-map columns → wrong data or parse failures. |
| **BP/EP suffixes** | "Begin Position", "End Position" on Entry/Exit DateTime. | Parser strips them; edge cases may fail. |
| **Account in Note column** | Account/permutation name lives in Note; some exports have separate Account column. | Account detection can fail if Note format differs. |
| **Format detection** | If header has "activitytype" + "openclose", we route to Activity parser. TradesList has "Symbol", "Trade Type", "Entry DateTime". | Wrong parser can be selected if both headers appear or paste is mixed. |

**Bottom line:** 26-col TradesList paste can work when format matches our expected headers. Column variations and format detection can cause failures.

---

## 4. Current State (Mar 2026)

- **Binary:** Imports but trades don't match SC.
- **Activity export:** Imports; matches SC only when ParentInternalOrderID is populated (often not).
- **TradesList paste:** Parsed when format matches; no file-based TradesList import.
- **No working path** to get a trade list that 1:1 matches Sierra Chart's Trades tab.

---

## 5. What Would Fix It

1. **SC documents binary format** (OpenClose, InternalOrderID tags) — or we obtain the 010 Editor template and reverse-engineer.
2. **SC fixes Activity export** to always include ParentInternalOrderID.
3. **Trades tab export** — File >> Save Log As from the **Trades** tab (not Activity). One row per trade, no pairing. We would need to add a parser for this format and a file-based import path.

---

*Created: Mar 1, 2026 — from docs review and codebase analysis*
