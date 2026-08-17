# Back-test results

Rows parsed from the 40 cached state-page snapshots: **903**.  
After filtering to listings with a vehicle type, a model year and an asking price >= $5,000: **766**.  
Of those, **577** are in the emergency-vehicle families the appraisal page names.  
Listing dates span 2026-06-10 to 2026-08-14.  
Target is the **asking price on an active listing**, not a closed sale price. Everything below inherits that limitation.

## Scope: emergency apparatus and ambulances (headline)

rows **577**, mileage present on 100%, pump gpm on 66%, tank size on 67%, engine hours on 40%.  
asking price median $50,000, range $5,000 to $1,150,000.  
time split cut date **2026-08-07** (train = listings last updated before it).

#### Time-based split (primary)

train n = 403, test n = 174

| model                   |   n |   MAE_$ |   RMSE_$ |   MAPE_% |   MedAPE_% |   P90_APE_% |   within_20% |   within_30% |   bias_$ |
|:------------------------|----:|--------:|---------:|---------:|-----------:|------------:|-------------:|-------------:|---------:|
| comps_k10 (this)        | 174 |  32,342 |   53,200 |     60.7 |       36   |       126.7 |         30.5 |         41.4 |    5,686 |
| gbt_log                 | 174 |  29,916 |   46,725 |     56.7 |       37   |       110.2 |         29.9 |         40.2 |    7,777 |
| median(type,age-decade) | 174 |  45,454 |   72,059 |     82.3 |       42.8 |       217.5 |         21.3 |         36.8 |   15,947 |
| global_median           | 174 |  41,230 |   68,051 |     75   |       47.5 |       169.4 |         18.4 |         32.8 |  -21,551 |


#### Random split (optimistic, shown for contrast)

train n = 403, test n = 174

| model                   |   n |   MAE_$ |   RMSE_$ |   MAPE_% |   MedAPE_% |   P90_APE_% |   within_20% |   within_30% |   bias_$ |
|:------------------------|----:|--------:|---------:|---------:|-----------:|------------:|-------------:|-------------:|---------:|
| comps_k10 (this)        | 174 |  46,465 |   88,788 |     51.3 |       38.6 |        98.1 |         28.2 |         39.7 |  -32,777 |
| gbt_log                 | 174 |  39,335 |   78,335 |     44.7 |       33.8 |        82.9 |         30.5 |         46   |  -20,082 |
| median(type,age-decade) | 174 |  50,219 |   93,210 |     62.2 |       45.1 |       147.9 |         24.1 |         35.6 |  -26,755 |
| global_median           | 174 |  69,886 |  128,007 |     89.5 |       66.7 |       233.3 |         15.5 |         25.9 |  -47,995 |


#### Error distribution, comps_k10, time-based test set

| percentile of |APE| | value (%) |
|---|---|
| p10 | 7.7 |
| p25 | 18.1 |
| p50 | 36.0 |
| p75 | 62.0 |
| p90 | 126.7 |
| p95 | 196.9 |
| p99 | 477.5 |
| max | 857.9 |

Mean APE 60.7% against median APE 36.0%. The gap is the right tail, and the right tail is what costs a marketplace a deal.


#### Is the error bar honest?

Band from the weighted spread of the comparables used, in log space. Nominal coverage assumes log-normal; actual coverage is measured on the held-out set.

| band | nominal | actual coverage | median band width (hi/lo) |
|---|---|---|---|
| +/-1.0 sd | 68% | 75.3% | 3.2x |
| +/-1.645 sd | 90% | 93.7% | 6.8x |
| +/-1.96 sd | 95% | 96.0% | 9.8x |


#### Where it is worst: how much training support the type had

| slice                      |   n |   MedAPE_% |   MAPE_% |   MAE_$ |
|:---------------------------|----:|-----------:|---------:|--------:|
| rare type (<10 train rows) |  31 |       37.9 |     51.6 |  30,878 |
| thin type (10-29)          |  54 |       29.2 |     60.6 |  37,970 |
| common type (30+)          |  89 |       38.1 |     63.9 |  29,438 |


#### Where it is worst: vehicle age

| slice    |   n |   MedAPE_% |   MAPE_% |   MAE_$ |
|:---------|----:|-----------:|---------:|--------:|
| 0-9 yr   |  16 |       33.9 |     86.3 |  42,336 |
| 10-19 yr |  57 |       37.9 |     58.2 |  44,568 |
| 20-29 yr |  79 |       34.7 |     59.9 |  26,111 |
| 30+ yr   |  22 |       46.8 |     51.2 |  15,774 |


#### Where it is worst: fields the seller did not fill in

| slice                |   n | MedAPE_%   | MAPE_%   | MAE_$   |
|:---------------------|----:|:-----------|:---------|:--------|
| mileage present      | 174 | 36.0       | 60.7     | 32,342  |
| mileage missing      |   0 | n/a        | n/a      | n/a     |
| pump gpm present     | 121 | 36.3       | 57.9     | 35,190  |
| pump gpm missing     |  53 | 34.1       | 66.9     | 25,841  |
| body builder present | 174 | 36.0       | 60.7     | 32,342  |
| body builder missing |   0 | n/a        | n/a      | n/a     |


#### Where it is worst: asking-price quartile

| slice                 |   n |   MedAPE_% |   MAPE_% |   MAE_$ |
|:----------------------|----:|-----------:|---------:|--------:|
| Q1 <= $30,000         |  51 |       53.9 |     89   |  16,574 |
| Q2 $30,000 to $52,500 |  36 |       30.6 |     64.8 |  28,751 |
| Q3 $52,500 to $81,800 |  43 |       32.2 |     52.1 |  35,434 |
| Q4 > $81,800          |  44 |       30.1 |     32.7 |  50,536 |


#### Five worst single predictions (time-based test set)

| title                            | type          |   year |   asking $ |   estimate $ |   APE % |
|:---------------------------------|:--------------|-------:|-----------:|-------------:|--------:|
| 2005 Spartan Pumper              | pumper-engine |   2005 |     10,000 |       95,786 |     858 |
| 2013 Ferrara Igniter 107' Aerial | aerial-ladder |   2013 |     70,000 |      431,821 |     517 |
| 2021 Spartan 4x4 Pumper          | pumper-engine |   2021 |     50,000 |      281,466 |     463 |
| 2019 Ford F350 Type I Ambulance  | type-1        |   2019 |     17,500 |       74,097 |     323 |
| 2003 Pierce Arrow 85' Aerial     | aerial-ladder |   2003 |     40,000 |      149,853 |     275 |


#### Worked example: what a seller would actually see

Subject: **2009 Pierce 75' Aerial** (aerial-ladder, Northeast, 2009, 37,491 mi)

Estimate **$258,203**, 90% band $78,607 to $848,128. Actual asking price $425,000.

| title                                 |   price | type          | chassis_make   | body_make   | region    |   model_year |   mileage |   pump_gpm |   tank_gal |   distance |   weight |
|:--------------------------------------|--------:|:--------------|:---------------|:------------|:----------|-------------:|----------:|-----------:|-----------:|-----------:|---------:|
| 2006 Pierce 61' Telesquirt 61' Aerial | 125,000 | aerial-ladder | Pierce         | Pierce      | South     |         2006 |     88552 |       1500 |        500 |      1.419 |    0.141 |
| 2008 Pierce Velocity 100' Aerial      | 125,000 | aerial-ladder | Pierce         | Pierce      | Northeast |         2008 |     30616 |          0 |          0 |      1.706 |    0.125 |
| 2013 Pierce Velocity 75' Aerial       | 115,000 | aerial-ladder | Pierce         | Pierce      | South     |         2013 |    120579 |       1500 |        500 |      1.767 |    0.122 |
| 2011 Pierce Velocity 105' Quint       | 339,000 | quint         | Pierce         | Pierce      | Northeast |         2011 |    100259 |       1500 |        500 |      2.043 |    0.11  |
| 2007 Darley Spartan 100' Aerial       | 275,000 | aerial-ladder | Spartan        | Darley      | Midwest   |         2007 |     18459 |       1500 |        350 |      2.353 |    0.099 |
| 2007 Pierce Enforcer 75' Quint        | 450,000 | quint         | Pierce         | Pierce      | South     |         2007 |     16109 |        nan |        nan |      2.838 |    0.085 |
| 2003 Pierce TL100 100' Quint          | 165,000 | quint         | Pierce         | Pierce      | Northeast |         2003 |     35000 |       1250 |        200 |      3.068 |    0.08  |
| 2018 Pierce ARROW XT 75' Aerial       | 798,000 | aerial-ladder | Pierce         | Pierce      | Midwest   |         2018 |     55495 |       2000 |        500 |      3.082 |    0.08  |
| 2015 Ferrara Ember 77' Aerial         | 685,000 | aerial-ladder | Ferrara        | Ferrara     | South     |         2015 |     39211 |       1750 |        500 |      3.118 |    0.079 |
| 2013 Pierce Velocity 100' Quint       | 685,000 | quint         | Pierce         | Pierce      | South     |         2013 |     38058 |       2000 |        300 |      3.166 |    0.078 |


## Scope: all priced vehicles on the site

rows **766**, mileage present on 100%, pump gpm on 53%, tank size on 55%, engine hours on 38%.  
asking price median $60,000, range $5,000 to $3,200,000.  
time split cut date **2026-08-06** (train = listings last updated before it).

#### Time-based split (primary)

train n = 536, test n = 230

| model                   |   n |   MAE_$ |   RMSE_$ |   MAPE_% |   MedAPE_% |   P90_APE_% |   within_20% |   within_30% |   bias_$ |
|:------------------------|----:|--------:|---------:|---------:|-----------:|------------:|-------------:|-------------:|---------:|
| comps_k10 (this)        | 230 |  33,111 |   52,193 |     58.4 |       34   |       127.7 |         31.3 |         43.5 |    4,612 |
| gbt_log                 | 230 |  34,076 |   57,834 |     59.6 |       35   |       123.5 |         27.8 |         42.2 |   10,012 |
| median(type,age-decade) | 230 |  49,884 |   75,410 |     85.4 |       46.5 |       200.9 |         19.6 |         33   |   20,696 |
| global_median           | 230 |  43,785 |   74,825 |     83.2 |       50   |       200   |         31.3 |         40   |  -16,831 |


#### Random split (optimistic, shown for contrast)

train n = 536, test n = 230

| model                   |   n |   MAE_$ |   RMSE_$ |   MAPE_% |   MedAPE_% |   P90_APE_% |   within_20% |   within_30% |   bias_$ |
|:------------------------|----:|--------:|---------:|---------:|-----------:|------------:|-------------:|-------------:|---------:|
| comps_k10 (this)        | 230 |  40,742 |   80,226 |     47.6 |       30.5 |        92.5 |         33.9 |         49.1 |  -24,294 |
| gbt_log                 | 230 |  35,053 |   65,151 |     40.9 |       27.7 |        80.3 |         39.6 |         53.9 |  -10,138 |
| median(type,age-decade) | 230 |  48,160 |   84,342 |     74.1 |       39.1 |       170.6 |         24.3 |         37.4 |   -2,383 |
| global_median           | 230 |  71,220 |  131,986 |     94.3 |       63.3 |       209.5 |         12.6 |         23.5 |  -48,183 |

