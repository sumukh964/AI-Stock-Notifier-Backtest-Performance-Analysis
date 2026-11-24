# **Did My AI Stock Notifier Actually Work? (May–Nov 2026)**

I built an AI Stock Notifier that reads daily financial news and sends alerts predicting whether stocks will rise or fall.

I wanted to test one thing: **Were my alerts actually predicting stock movements?**

I cleaned the alert data, tracked stock prices after each alert, compared the results with Nifty 50, and created a Power BI dashboard.

## **Results**

| Metric (5-day period) | Result                  |
| --------------------- | ----------------------- |
| Alerts tested         | 316                     |
| Overall accuracy      | 52.5%                   |
| Fall alert accuracy   | 58.4%                   |
| Rise alert accuracy   | 45.8%                   |
| Final verdict         | Almost like a coin toss |

- Confidence scores did not really affect accuracy.
- I tested around 15 different categories. Some good results could have happened just by chance.
- Most headlines reported price movements that had already happened. The system was reading news, not predicting the future.
- 8 out of 273 clear alerts (3%) had incorrect labels.

## **How the project works**

```
Raw News Alerts (JSON)
        ↓
Data Cleaning (Python)
        ↓
Stock Price Analysis
        ↓
Compare with Nifty 50
        ↓
Results (CSV)
        ↓
Power BI Dashboard
```

### **1. Data Cleaning (Python)**

- Started with 779 raw alerts.
- Removed irrelevant alerts and duplicate entries.
- Matched company names with NSE stock tickers.
- Removed foreign companies, brokers and non-stock names.
- Checked whether the rise/fall labels matched the headlines.
- Final result: 319 cleaned alerts covering 178 NSE stocks.

### **2. Stock Performance Testing (Python)**

- Downloaded stock prices using Yahoo Finance.
- Checked stock prices after 1, 5 and 20 trading days.
- Compared stock performance with Nifty 50.
- Calculated whether each alert was correct or incorrect.
- Used statistical tests to check whether the results were better than 50%.

### **3. Power BI Dashboard**

Created an interactive dashboard showing:

- Overall accuracy and total alerts.
- Rise vs fall alert performance.
- Monthly and sector-wise performance.
- Best and worst-performing alerts.
- Stock performance compared with Nifty 50.
- Cumulative excess returns.

**Dashboard:** 

## **Tools Used**

Python, Pandas, NumPy, SciPy, yfinance and Power BI.

## **Limitations**

- Tested only around 6 months of data.
- Small groups of alerts may give unreliable results.
- Brokerage charges and transaction costs were not included.
- Some stock names and labels needed manual corrections.
- The system reads financial news; it does not truly predict future market movements.

**Final takeaway:** My system achieved 52.5% accuracy, which is close to random guessing. The project helped me understand how to clean real-world data, test assumptions, compare performance and present findings through Power BI.
