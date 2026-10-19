"""A fixed-price, FIFO funding-turnover model; all quantities are in millions.

Cash: USD million. Tokens: million tokens. Price: USD/token. Time: integer days.
This is a scenario model, NOT a stablecoin price model or historical calibration.
"""
from collections import defaultdict, deque
from math import ceil, isfinite

EPS = 1e-9


def rolling_threshold(sales, delay, price=0.98):
    """Exact no-backlog initial principal under fixed delay and no reinvestment."""
    return price * max((sum(sales[max(0, i-delay+1):i+1])
                        for i in range(len(sales))), default=0.0)


def simulate(sales, delay, initial_cash, price=0.98, reinvest=False):
    """Arrivals and trades occur after settlements; each buy settles at day + delay.

    Baseline: only purchase principal returns to deployable cash; profit is set aside.
    Robustness: the entire $1 redemption is reinvested. No interest, fees, default,
    price feedback, issuer capacity limit, new borrowing, or discretionary timing.
    """
    sales = list(sales)
    if not isinstance(delay, int) or isinstance(delay, bool) or delay < 1:
        raise ValueError('delay must be an integer >= 1')
    if not (isfinite(initial_cash) and initial_cash > 0 and 0 < price <= 1):
        raise ValueError('require finite positive cash and 0 < price <= 1')
    if any(not isfinite(s) or s < 0 for s in sales):
        raise ValueError('sales must be finite and nonnegative')
    total = sum(sales)
    cash = float(initial_cash)
    # Due amounts are token quantities, not a second source of initial funding.
    due = defaultdict(float)
    queue = deque()
    daily, fills = [], []
    bought_total = matured_total = realized_profit = withdrawn_profit = 0.0
    last_purchase = last_settlement = 0
    last_arrival = max((i+1 for i,s in enumerate(sales) if s > EPS), default=0)
    max_days = len(sales) + delay * (ceil(total*price/initial_cash) + 3) + 5
    for day in range(1, max_days+1):
        matured = due.pop(day, 0.0)
        matured_total += matured
        realized_profit += matured * (1-price)
        cash += matured * (1 if reinvest else price)
        if not reinvest:
            withdrawn_profit += matured * (1-price)
        if matured > EPS:
            last_settlement = day
        arrival = sales[day-1] if day <= len(sales) else 0.0
        if arrival > EPS:
            queue.append([day, float(arrival)])
        backlog_before = sum(q for _, q in queue)
        qty = min(backlog_before, max(cash,0.0)/price)
        cash -= qty * price
        if abs(cash) < EPS:
            cash = 0.0
        remaining = qty
        while remaining > EPS and queue:
            arrival_day, amount = queue[0]
            fill = min(remaining, amount)
            fills.append({'arrival_day': arrival_day, 'purchase_day': day,
                          'quantity_million': fill, 'wait_days': day-arrival_day})
            remaining -= fill
            queue[0][1] -= fill
            if queue[0][1] < EPS:
                queue.popleft()
        bought_total += qty
        if qty > EPS:
            due[day+delay] += qty
            last_purchase = day
        backlog = sum(q for _,q in queue)
        locked = price * sum(due.values())
        # Accounting identities independently check the funding engine each day.
        arrived = sum(sales[:min(day,len(sales))])
        assert abs(arrived-bought_total-backlog) < 1e-7
        assert abs(cash+locked-(initial_cash+realized_profit-withdrawn_profit)) < 1e-7
        assert abs(bought_total-matured_total-sum(due.values())) < 1e-7
        assert cash >= -EPS and backlog >= -EPS
        daily.append({'day':day, 'arrival_million':arrival,
                      'matured_tokens_million':matured,
                      'purchased_million':qty, 'cumulative_purchased_million':bought_total,
                      'backlog_million':backlog, 'cash_usd_million':cash,
                      'locked_principal_usd_million':locked,
                      'realized_profit_usd_million':realized_profit,
                      'withdrawn_profit_usd_million':withdrawn_profit})
        if day >= len(sales) and backlog < EPS and not due:
            break
    else:
        raise RuntimeError('Simulation did not finish within its conservative bound')
    weighted_wait = sum(f['quantity_million']*f['wait_days'] for f in fills)
    area_wait = sum(r['backlog_million'] for r in daily)
    assert abs(weighted_wait-area_wait) < 1e-7
    assert abs(bought_total-total) < 1e-7
    assert abs(matured_total-total) < 1e-7
    threshold = rolling_threshold(sales,delay,price)
    stats = {'delay_days':delay,'initial_cash_usd_million':initial_cash,
             'reinvest_profit':reinvest,'price_usd_per_token':price,
             'total_sales_million':total,
             'peak_backlog_million':max(r['backlog_million'] for r in daily),
             'average_wait_days':weighted_wait/total if total else 0.,
             'backlog_day6_million':next((r['backlog_million'] for r in daily if r['day']==6),0.),
             'purchased_by_day6_million':next((r['cumulative_purchased_million'] for r in daily if r['day']==6),bought_total),
             'last_arrival_day':last_arrival,'last_purchase_day':last_purchase,
             'last_settlement_day':last_settlement,
             'cleanup_days_after_last_arrival':max(0,last_purchase-last_arrival),
             'peak_locked_principal_usd_million':max(r['locked_principal_usd_million'] for r in daily),
             'baseline_exact_threshold_usd_million':threshold,
             'average_flow_proxy_usd_million':price*(total/len(sales) if sales else 0)*delay,
             'final_cash_usd_million':cash,
             'final_withdrawn_profit_usd_million':withdrawn_profit}
    return stats, daily, fills
