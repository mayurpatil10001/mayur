limit = 3

def test_drift(current_net, qty, side):
    if side == 'BUY':
        intended_net = current_net + qty
        if intended_net > limit:
            allowed_qty = max(0, limit - current_net)
            dropped_qty = qty - allowed_qty
            print(f"BUY: Pre={current_net} Qty={qty} Intended={intended_net} -> Allowed={allowed_qty} Dropped={dropped_qty}")
    else:
        intended_net = current_net - qty
        if intended_net < -limit:
            allowed_qty = max(0, limit + current_net)
            dropped_qty = qty - allowed_qty
            print(f"SELL: Pre={current_net} Qty={qty} Intended={intended_net} -> Allowed={allowed_qty} Dropped={dropped_qty}")

print("Testing SELL 6 when Pre-Pos is 3:")
test_drift(3, 6, 'SELL')

print("\nTesting SELL 7 when Pre-Pos is 3:")
test_drift(3, 7, 'SELL')

print("\nTesting BUY 6 when Pre-Pos is -3:")
test_drift(-3, 6, 'BUY')

print("\nTesting BUY 7 when Pre-Pos is -3:")
test_drift(-3, 7, 'BUY')
