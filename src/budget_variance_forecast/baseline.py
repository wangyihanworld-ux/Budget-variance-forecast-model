"""Trailing run-rate benchmark. No future actuals enter the forecast function."""
import argparse
from pathlib import Path
import pandas as pd
from .synthetic import build_synthetic_dataset, KEY_COLUMNS
from .validation import normalize_and_validate_inputs,DataValidationError
from .review import create_snapshot,review_forecasts

def run_rate_snapshot(budget,actual,version,as_of,window=3):
    if isinstance(window,bool) or not isinstance(window,int) or window<1:
        raise DataValidationError('window must be a positive integer')
    budget,actual=normalize_and_validate_inputs(budget,actual)
    cutoff=pd.Timestamp(as_of).to_period('M').to_timestamp()
    if cutoff!=actual.month.max(): raise DataValidationError('Actual cutoff must match as_of')
    start=cutoff-pd.DateOffset(months=window-1)
    history=actual[actual.month>=start].copy()
    if history.month.nunique()<window: raise DataValidationError('Insufficient history for window')
    history['operating_profit']=history.actual_revenue-history.actual_variable_cost-history.actual_fixed_expense
    means=history.groupby(['business_unit','product']).agg(revenue=('actual_revenue','mean'),operating_profit=('operating_profit','mean'),n=('month','nunique')).reset_index()
    if means.n.ne(window).any(): raise DataValidationError('Incomplete product history')
    future=budget.loc[budget.month>cutoff,KEY_COLUMNS].merge(means.drop(columns='n'),on=['business_unit','product'],how='left',validate='many_to_one')
    if future.empty or future[['revenue','operating_profit']].isna().any().any():
        raise DataValidationError('Missing future targets or product history')
    future['version']=version; future['as_of']=cutoff; future['scenario']='trailing_3m' if window==3 else f'trailing_{window}m'
    future['horizon_months']=(future.month.dt.year-cutoff.year)*12+future.month.dt.month-cutoff.month
    return future[['version','as_of','scenario',*KEY_COLUMNS,'horizon_months','revenue','operating_profit']]

def main():
    p=argparse.ArgumentParser(); p.add_argument('--output-dir',default='docs/baseline-results'); a=p.parse_args()
    out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
    full=build_synthetic_dataset(actual_months=12); snapshots=[]
    for month in [3,6,9]:
        cutoff=pd.Timestamp(2026,month,1); observed=full.actual[full.actual.month<=cutoff]
        version=f'2026M{month:02}'
        snapshots.append(create_snapshot(full.budget,observed,full.assumptions,version,cutoff))
        snapshots.append(run_rate_snapshot(full.budget,observed,version,cutoff))
    detail,scores=review_forecasts(pd.concat(snapshots,ignore_index=True),full.actual)
    detail.to_csv(out/'comparison_detail.csv',index=False)
    scores.to_csv(out/'comparison_metrics.csv',index=False)
    print('Reconstructed synthetic comparison; same targets and horizons; no real-business performance claim.')
    print(scores.groupby('scenario')[['mae','rmse']].mean().to_string())

if __name__=='__main__': main()
