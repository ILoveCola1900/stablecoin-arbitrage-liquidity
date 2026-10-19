"""Run the 36 baseline + 36 robustness cases and export three standalone figures."""
from pathlib import Path
import json
import platform
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from simulator import simulate, rolling_threshold

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results'
FIG=ROOT/'figures'
PATHS={'uniform':[1,1,1,1,1,1],
       'spaced_blocks':[3,0,0,3,0,0],
       'clustered_blocks':[0,0,3,3,0,0]}
LABELS={'uniform':'均匀卖出','spaced_blocks':'分散大单','clustered_blocks':'集中大单'}
CN={'uniform':'均匀卖出','spaced_blocks':'分散大单','clustered_blocks':'集中大单'}
DELAYS=[1,2,3,5]
BUDGETS=[.98,1.96,2.94]
COLORS={'uniform':'#276C86','spaced_blocks':'#CA9444','clustered_blocks':'#AA4C61'}


def save_figure(fig,name):
    for ext in ['png','svg']:
        fig.savefig(FIG/f'{name}.{ext}',dpi=220,bbox_inches='tight',facecolor='white')
    plt.close(fig)


def generate():
    OUT.mkdir(exist_ok=True);FIG.mkdir(exist_ok=True)
    summary=[];traces=[];fill_records=[]
    for reinvest in [False,True]:
        for key,path in PATHS.items():
            for delay in DELAYS:
                for budget in BUDGETS:
                    sid=f'{key}_T{delay}_B{budget:.2f}_R{int(reinvest)}'
                    stats,daily,fills=simulate(path,delay,budget,reinvest=reinvest)
                    meta={'scenario_id':sid,'path':key}
                    summary.append({**meta,**stats})
                    traces.extend({**meta,**row} for row in daily)
                    fill_records.extend({**meta,**row} for row in fills)
    df=pd.DataFrame(summary)
    df.to_csv(OUT/'scenario_summary.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(traces).to_csv(OUT/'daily_traces.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(fill_records).to_csv(OUT/'fifo_fills.csv',index=False,encoding='utf-8-sig')
    base=df[~df.reinvest_profit].copy()
    rob=df[df.reinvest_profit].copy()
    metrics=['peak_backlog_million','average_wait_days','last_purchase_day']
    comparison=base[['path','delay_days','initial_cash_usd_million']+metrics].merge(
        rob[['path','delay_days','initial_cash_usd_million']+metrics],
        on=['path','delay_days','initial_cash_usd_million'],suffixes=('_baseline','_reinvest'))
    for metric in metrics:
        comparison[metric+'_change']=comparison[metric+'_reinvest']-comparison[metric+'_baseline']
    comparison.to_csv(OUT/'reinvestment_comparison.csv',index=False,encoding='utf-8-sig')
    threshold_rows=[]
    for key,path in PATHS.items():
        for delay in DELAYS:
            threshold_rows.append({'path':key,'delay_days':delay,
                                   'exact_principal_threshold_usd_million':rolling_threshold(path,delay),
                                   'average_flow_proxy_usd_million':.98*delay})
    thresholds=pd.DataFrame(threshold_rows)
    thresholds.to_csv(OUT/'funding_thresholds.csv',index=False,encoding='utf-8-sig')
    env={'python':sys.version,'platform':platform.platform(),'numpy':np.__version__,
         'pandas':pd.__version__,'matplotlib':matplotlib.__version__,
         'units':{'cash':'USD million','tokens':'million tokens','price':'USD/token'},
         'paths':PATHS,'delays_days':DELAYS,'budgets_usd_million':BUDGETS,
         'price':.98,'redemption_value':1.,'randomness_in_main_experiment':False}
    (OUT/'run_config.json').write_text(json.dumps(env,indent=2,ensure_ascii=False),encoding='utf-8')
    from matplotlib import font_manager
    font_path=ROOT/'assets/fonts/NotoSansCJKsc-Regular.otf'
    font_manager.fontManager.addfont(str(font_path))
    font_name=font_manager.FontProperties(fname=str(font_path)).get_name()
    plt.rcParams.update({'font.family':font_name,'font.size':11,'axes.spines.top':False,
                         'axes.spines.right':False,'axes.labelcolor':'#263645',
                         'text.color':'#263645','axes.titleweight':'bold',
                         'svg.fonttype':'none'})
    # Figure 1: arrivals and daily end-of-day backlog, same budget and delay.
    fig,axes=plt.subplots(2,1,figsize=(10.5,7.4),gridspec_kw={'height_ratios':[1,1.35]},sharex=True)
    fig.suptitle('总卖出量相同，时序不同',x=.085,ha='left',fontsize=19,fontweight='bold')
    fig.text(.085,.922,'假设情景：资金294万美元，赎回等待3天，买价0.98美元',fontsize=11)
    horizon=9
    focus=[]
    for key,path in PATHS.items():
        stats,daily,_=simulate(path,3,2.94)
        focus.append({'path':key,**stats})
        axes[0].plot(range(1,7),path,marker='o',label=LABELS[key],color=COLORS[key],linewidth=2)
        series={r['day']:r['backlog_million'] for r in daily}
        axes[1].step(range(1,horizon+1),[series.get(d,0.) for d in range(1,horizon+1)],
                     where='post',color=COLORS[key],linewidth=2.4,label=LABELS[key])
    axes[0].set_ylabel('新增卖单（百万枚）');axes[0].set_ylim(-.1,3.6)
    axes[0].legend(ncol=3,loc='upper right',frameon=False,fontsize=10)
    axes[1].set_ylabel('日终积压（百万枚）')
    axes[1].set_xlabel('天数');axes[1].set_xticks(range(1,horizon+1));axes[1].set_ylim(-.1,3.6)
    axes[1].annotate('第4、5天日末各积压300万枚',xy=(4.4,3),xytext=(2.4,3.4),fontsize=10)
    for ax in axes:
        ax.grid(axis='y',alpha=.15);ax.set_xlim(.8,horizon)
    fig.text(.085,.015,'注：赎回款先到账，再交易；仅循环本金，利润另存。数据为情景计算。',fontsize=9,color='#526574')
    fig.tight_layout(rect=(0,.04,1,.90));save_figure(fig,'01_backlog_paths')
    # Figure 2: all 36 main cases, shared scale and visible values.
    fig,axes=plt.subplots(1,3,figsize=(12,5.1),sharey=True)
    fig.suptitle('资金与赎回时间如何影响积压',x=.065,ha='left',fontsize=19,fontweight='bold')
    fig.text(.065,.89,'最大日终积压（百万枚）：36组基准情景',fontsize=11)
    vmax=float(base.peak_backlog_million.max())
    for ax,key in zip(axes,PATHS):
        z=np.array([[base[(base.path==key)&(base.delay_days==t)&
                     (np.isclose(base.initial_cash_usd_million,b))].peak_backlog_million.iloc[0]
                     for b in BUDGETS] for t in DELAYS])
        im=ax.imshow(z,cmap='YlOrRd',vmin=0,vmax=vmax,aspect='auto')
        ax.set_title(LABELS[key],fontsize=12,pad=12)
        ax.set_xticks(range(3),[f'{b:.2f}' for b in BUDGETS]);ax.set_xlabel('可用资金（百万美元）')
        ax.set_yticks(range(4),DELAYS)
        for i in range(4):
            for j in range(3):
                ax.text(j,i,f'{z[i,j]:.1f}',ha='center',va='center',fontsize=12,
                        color='white' if z[i,j]>vmax*.62 else '#263645')
    axes[0].set_ylabel('赎回等待时间（天）')
    fig.subplots_adjust(left=.065,right=.9,bottom=.19,top=.77,wspace=.16)
    cax=fig.add_axes([.925,.20,.018,.55]);fig.colorbar(im,cax=cax,label='百万枚')
    fig.text(.065,.035,'注：买价0.98美元，各路径总卖出量600万枚；格内数值为积压量，并非脱锚幅度。',fontsize=9,color='#526574')
    save_figure(fig,'02_funding_delay_heatmap')
    # Figure 3: diagnostic threshold vs full-horizon average-flow proxy.
    fig,ax=plt.subplots(figsize=(10.5,6.0))
    fig.suptitle('平均流量可能掩盖峰值资金需求',x=.085,ha='left',fontsize=19,fontweight='bold')
    fig.text(.085,.90,'无积压所需初始资金：仅循环本金',fontsize=11)
    for key,path in PATHS.items():
        ax.plot(DELAYS,[rolling_threshold(path,t) for t in DELAYS],marker='o',
                linewidth=2.3,color=COLORS[key],label=LABELS[key])
    ax.plot(DELAYS,[.98*t for t in DELAYS],color='#263645',linestyle=':',linewidth=2.4,
            label='六日平均流量参照（与均匀路径重合）')
    ax.set_xlabel('赎回等待时间（天）');ax.set_ylabel('所需初始资金（百万美元）')
    ax.set_xticks(DELAYS);ax.set_ylim(0,6.5);ax.grid(axis='y',alpha=.18)
    ax.legend(frameon=False,loc='lower right',fontsize=10)
    ax.annotate('赎回等待3天：集中路径需588万美元，\n平均流量参照为294万美元',
                xy=(3,5.88),xytext=(2.1,4.2),fontsize=11,
                arrowprops={'arrowstyle':'->','color':'#526574'})
    fig.text(.085,.025,'注：参照值统一采用六日平均流量。阈值来自给定规则下的资金收支关系。',fontsize=9,color='#526574')
    fig.tight_layout(rect=(0,.065,1,.87));save_figure(fig,'03_peak_funding_threshold')
    pd.DataFrame(focus).to_csv(OUT/'focus_cases.csv',index=False,encoding='utf-8-sig')
    # A second analytical check: fixed-principal theorem vs every baseline run.
    predicted=base.initial_cash_usd_million+1e-8>=base.baseline_exact_threshold_usd_million
    observed=base.peak_backlog_million<1e-8
    assert (predicted==observed).all()
    output={'scenarios':len(df),'baseline_cases':len(base),'reinvestment_cases':len(rob),
            'threshold_classification_matches':int((predicted==observed).sum()),
            'reinvestment_reduces_peak_cases':int((comparison.peak_backlog_million_change < -1e-8).sum()),
            'reinvestment_reduces_wait_cases':int((comparison.average_wait_days_change < -1e-8).sum()),
            'max_peak_reduction_million':float(-comparison.peak_backlog_million_change.min()),
            'max_wait_reduction_days':float(-comparison.average_wait_days_change.min()),
            'focus':focus}
    (OUT/'validation_summary.json').write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(output,indent=2,ensure_ascii=False))


if __name__=='__main__':
    generate()
