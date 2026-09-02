# Data Integrity Report

## Trading-calendar reconciliation
A market holiday must never be treated as a zero-return day. The
benchmark index trades on every NSE session, so its date index is the
authoritative calendar.

```
panel_days: 2041
benchmark_days: 2027
days_in_panel_not_in_benchmark: 14
days_in_benchmark_not_in_panel: 0
examples_extra: ['2019-10-27', '2020-11-14', '2021-01-01', '2022-12-26', '2024-01-01', '2024-02-19', '2025-01-01', '2025-02-01', '2026-01-01', '2026-01-15']
examples_missing: []
```

## Unexplained price jumps (>50% in a day, no recorded split)
count: 6

| date                | symbol     |    return |   split_on_day |
|:--------------------|:-----------|----------:|---------------:|
| 2019-10-16 00:00:00 | GICHSGFIN  |  3.86753  |              1 |
| 2018-06-25 00:00:00 | FCL        |  1.09515  |              1 |
| 2019-06-20 00:00:00 | JETAIRWAYS |  0.898792 |              1 |
| 2019-10-17 00:00:00 | GICHSGFIN  | -0.759331 |              1 |
| 2018-09-28 00:00:00 | CCAVENUE   | -0.708261 |              1 |
| 2019-10-11 00:00:00 | ABREL      | -0.553559 |              1 |

## Level shifts (paise/rupee or face-value errors)
count: 40

| date                | symbol     |     ratio |
|:--------------------|:-----------|----------:|
| 2018-08-14 00:00:00 | TIRUMALCHM | 0.107782  |
| 2018-10-19 00:00:00 | IEX        | 0.0990814 |
| 2018-11-12 00:00:00 | SAKUMA     | 0.102154  |
| 2019-10-15 00:00:00 | SATIA      | 0.0988316 |
| 2019-12-13 00:00:00 | TRIDENT    | 0.112275  |
| 2020-08-24 00:00:00 | EICHERMOT  | 0.100286  |
| 2021-06-24 00:00:00 | INVENTURE  | 0.115482  |
| 2021-09-17 00:00:00 | CESC       | 0.104529  |
| 2022-02-22 00:00:00 | SBC        | 0.105085  |
| 2022-04-26 00:00:00 | SAREGAMA   | 0.0999088 |
| 2022-07-12 00:00:00 | STEELXIND  | 0.104807  |
| 2022-07-28 00:00:00 | TATASTEEL  | 0.104597  |
| 2022-09-23 00:00:00 | BSHSL      | 0.105019  |
| 2022-09-23 00:00:00 | SAKSOFT    | 0.0904828 |
| 2022-11-30 00:00:00 | RAJMET     | 0.119918  |
| 2023-02-22 00:00:00 | IRB        | 0.114473  |
| 2023-03-13 00:00:00 | OSIAHYPER  | 0.104829  |
| 2023-03-17 00:00:00 | HITECH     | 0.10049   |
| 2023-04-21 00:00:00 | TIPSMUSIC  | 0.0959703 |
| 2023-05-04 00:00:00 | APOLLO     | 0.105     |
| 2023-06-12 00:00:00 | IONEXCHANG | 0.0954887 |
| 2023-08-04 00:00:00 | SARDAEN    | 0.101858  |
| 2023-10-09 00:00:00 | SIGACHI    | 0.0966006 |
| 2023-10-27 00:00:00 | BCLIND     | 0.0997839 |
| 2023-11-10 00:00:00 | MKPL       | 0.100534  |
| 2023-12-29 00:00:00 | HMAAGRO    | 0.10989   |
| 2024-01-05 00:00:00 | NESTLEIND  | 0.0983316 |
| 2024-07-10 00:00:00 | PGEL       | 0.0992275 |
| 2024-11-08 00:00:00 | MOTISONS   | 0.104793  |
| 2024-12-16 00:00:00 | PCJEWELLER | 0.105012  |

## Symbols with >2% zero-volume sessions
count: 36

| symbol     |   zero_vol_frac |
|:-----------|----------------:|
| JBCHEPHARM |       1         |
| MKPL       |       0.409225  |
| FRETAIL    |       0.360608  |
| AHLUCONT   |       0.274375  |
| RELCAPITAL |       0.258923  |
| ESSENTIA   |       0.250123  |
| RMDRIP     |       0.240686  |
| OSIAHYPER  |       0.234907  |
| FCONSUMER  |       0.22195   |
| JETAIRWAYS |       0.22146   |
| RAJMET     |       0.218734  |
| GAYAPROJ   |       0.151886  |
| E2E        |       0.15049   |
| RCOM       |       0.145098  |
| JYOTISTRUC |       0.137255  |
| FEL        |       0.0657185 |
| INFOBEAN   |       0.0509554 |
| RELINFRA   |       0.0431161 |
| TECHNOE    |       0.0396864 |
| TRU        |       0.0374181 |
| FLFL       |       0.0367827 |
| JTLIND     |       0.0292599 |
| VERTOZ     |       0.0269608 |
| MODEFENCE  |       0.0238569 |
| ICICIAMC   |       0.0227273 |
| PARKHOSPS  |       0.0224719 |
| FORCEMOT   |       0.0223005 |
| IIFLCAPS   |       0.0220674 |
| MEESHO     |       0.0218579 |
| AEQUS      |       0.0218579 |

## Internal history gaps (>10 consecutive missing sessions)
count: 1

| symbol   |   longest_internal_gap_days |   total_missing | first      | last       |
|:---------|----------------------------:|----------------:|:-----------|:-----------|
| FORCEMOT |                          41 |              41 | 2019-08-19 | 2026-09-01 |

## Backfill check
symbols with prices before listing: 0

## NaN fraction of the panel by year

```
2018: 0.3352
2019: 0.3167
2020: 0.2932
2021: 0.2521
2022: 0.2005
2023: 0.164
2024: 0.1117
2025: 0.0454
2026: 0.0049
```
