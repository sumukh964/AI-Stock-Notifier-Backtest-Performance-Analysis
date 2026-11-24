# Cleaning report

- Alerts in file: 779
- Signal alerts (rise/fall/buy): 745
- In date range 2026-05-13 to 2026-11-13: 710
- Rejected (not a listed stock): 318
- Rejected (repeat headline): 76
- **Clean alerts: 319** across 178 tickers
- Mapped from company field: 235, from headline: 84

## Reject reasons
reject_reason
unknown_or_unlisted                  105
index_or_market                       90
repeat_of_earlier_alert               76
amount_not_company                    38
broker_or_agency                      32
foreign_company                       22
regulator_or_event                    14
ambiguous_headline_several_stocks     13
manual_exclude_wrong_subject           4

## Label check (alert type vs headline direction)
label_status
match       265
unclear      45
mismatch      8
n/a           1

Mismatch rate among clear headlines: 8/273 = 2.9%
Same-day conflicts (same stock, opposite alerts): 0