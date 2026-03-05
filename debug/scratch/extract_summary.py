"""Extract key findings into a compact summary."""
with open('diag_deep_result.txt','r',encoding='utf-8') as f:
    lines = [l.rstrip() for l in f.readlines()]

# Extract sections
def extract(keyword, max_lines=40):
    result = []
    found = False
    for i, l in enumerate(lines):
        if keyword in l:
            found = True
        if found:
            result.append(l)
            if len(result) >= max_lines:
                break
            # Stop at next section header
            if len(result) > 2 and '='*30 in l:
                break
    return result

summary = []
summary.append("=== Q1: Ghost fills across 20 days ===")
for l in lines:
    if 'Ghost fills across' in l: summary.append(l)
    if 'order type' in l.lower() and ':' in l: summary.append(l)
    if 'Unknown:' in l: summary.append(l)
    if 'Trailing' in l and ':' in l: summary.append(l)

summary.append("")
summary.append("=== Q2: Dec 18 ghost count ===")
for l in lines:
    if 'Ghost fill RECORDS' in l: summary.append(l)
    if 'Ghost fill CONTRACTS' in l: summary.append(l)
    if 'Parser reported' in l: summary.append(l)
    if l.strip().startswith('[') and 'GHOST' not in l and 'qty=' in l and 'note=' in l and '2025-12-18' not in l:
        continue
    if l.strip().startswith('[') and 'qty=' in l and len(summary) < 20:
        summary.append(l)

summary.append("")
summary.append("=== Q3: Context around ghost fills ===")
in_q3 = False
count = 0
for l in lines:
    if 'Q3:' in l and 'CONTEXT' in l:
        in_q3 = True
        continue
    if in_q3:
        if 'Q4:' in l:
            break
        if l.strip():
            summary.append(l)
            count += 1
        if count > 50:
            break

summary.append("")
summary.append("=== Q4: Session balance ===")
in_q4 = False
count = 0
imbalanced_count = 0
for l in lines:
    if 'Q4:' in l and 'SESSION' in l:
        in_q4 = True
        continue
    if in_q4:
        if 'Total fills' in l or 'Total sessions' in l or 'IMBALANCED' in l or 'non-zero' in l:
            summary.append(l)
            if 'IMBALANCED' in l: imbalanced_count += 1
        if l.strip().startswith('20') and 'IMBALANCED' in l:
            summary.append(l)
        if count > 100: break
        count += 1

summary.append(f"Total imbalanced sessions: {imbalanced_count}")

with open('diag_summary.txt', 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(summary))
print(f"Summary: {len(summary)} lines")
