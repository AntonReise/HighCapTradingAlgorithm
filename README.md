# High Capacity Trading Algorithm

A sophisticated multi-indicator strategy implementing adaptive trend following with signal aggregation for both single and multiple securities trading on the QuantConnect platform.

<span style="color:red;"><strong>This is a template for creating a strategy and backtesting with these indicators; it is not intended for immediate trading.</strong></span>

**Authors:** Anton Reise and Leif Koesling

## Quick Start Guide

To get started with this algorithm:

1. **Choose a Version:**

   - v2 Single-Symbol: Use for focused trading on one security with enhanced visualization
   - v2 Multi-Symbol: Use to trade multiple securities simultaneously

2. **Setup on QuantConnect:**

   - Create a QuantConnect account at [quantconnect.com](https://www.quantconnect.com)
   - Create a new algorithm project
   - Copy the appropriate version of the code into your project

3. **Configure Your Strategy:**

   - Set your trading symbols in the global parameters section
   - Adjust entry/exit signal thresholds to match your risk tolerance
   - Customize indicator parameters based on your trading style
   - Set position sizing to align with your risk management approach

4. **Run a Backtest:**
   - Click the "Backtest" button in QuantConnect
   - Review performance, trades, and charts
   - Adjust parameters as needed

## Overview

This repository contains two implementations of the same core strategy:

1. **Multi-Symbol Version** - Trade multiple securities simultaneously with independent signal evaluation
2. **Single-Symbol Version** - Focus on a single security with enhanced charting and visualization

Both versions use a combination of technical indicators to identify trading opportunities. The strategy aggregates signals from multiple indicators to filter out noise and identify higher probability trades, using a configurable threshold-based entry and exit system.

## Features

- **Multi-Indicator Approach:** Combines multiple technical indicators to form trading signals
- **Signal Aggregation:** Requires multiple confirming indicators for trade entries and exits
- **Trailing Stop Management:** Automatically sets trailing stops to protect positions
- **Position Scaling:** Ability to add to existing positions when receiving additional signals
- **Configurable Parameters:** Easily adjust indicator settings, signal thresholds, and allocation sizes
- **Enhanced Visualization:** Track indicator values and trading signals with detailed charts

## Indicators Used

The strategy utilizes the following technical indicators:

| Indicator                | Description                                                 | Signal Generation                                                                                   |
| ------------------------ | ----------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Moving Average Crossover | Fast and slow moving average crossover system               | Buy when fast MA crosses above slow MA, sell when it crosses below                                  |
| Stochastic RSI           | Combines Relative Strength Index with Stochastic oscillator | Buy when both K and D lines cross above lower threshold, sell when both cross below upper threshold |
| LBR Oscillator           | Custom oscillator implemented via MACD parameters           | Buy when oscillator moves above zero, sell when it drops below zero                                 |
| Money Flow Index (MFI)   | Volume-weighted RSI that measures buying/selling pressure   | Buy when MFI rises above lower threshold, sell when it falls below upper threshold                  |
| Volume Spikes            | Identifies abnormal volume conditions                       | Buy on bullish volume spikes, sell on bearish volume spikes                                         |

## Configuration Guide

### Critical Parameters to Customize

These parameters should be customized based on your trading objectives:

| Parameter                | Description                   | Recommendation                                              |
| ------------------------ | ----------------------------- | ----------------------------------------------------------- |
| `SYMBOL`/`SYMBOLS`       | Securities to trade           | Select liquid securities with sufficient trading volume     |
| `REQUIRED_ENTRY_SIGNALS` | Threshold for entering trades | Higher = fewer but potentially higher quality trades        |
| `REQUIRED_EXIT_SIGNALS`  | Threshold for exiting trades  | Lower = faster exits, higher = more room for price movement |
| `TRAILING_STOP_PERCENT`  | Trailing stop percentage      | Based on the volatility of the traded securities            |
| `*_TRADE_ALLOCATION`     | Position sizing parameters    | Align with your risk management strategy                    |

### Indicator Customization

Each indicator can be enabled/disabled and its parameters adjusted:

```python
# Enable/disable indicators
ENABLE_MA = True     # Moving Average Crossover
ENABLE_STOCH = True  # Stochastic RSI
ENABLE_LBR = True    # LBR Oscillator
ENABLE_MFI = True    # Money Flow Index
ENABLE_VOL = True    # Volume Analysis

# Adjust indicator weights
MA_WEIGHT = 2.0      # Customize based on indicator performance
STOCH_WEIGHT = 1.0
LBR_WEIGHT = 2.0
MFI_WEIGHT = 1.0
VOL_WEIGHT = 1.0
```

### Trailing Stop Implementation

The algorithm includes a robust trailing stop system:

- **Automatic Protection:** Trailing stops are placed automatically after entry
- **Configurable Distance:** Set the trailing stop percentage based on the security's volatility
- **Direction Adaptation:** Works for both long and short positions
- **Brokerage Compatible:** Implemented using QuantConnect's native trailing stop orders

To customize trailing stops:

```python
# Enable/disable trailing stops
ENABLE_TRAILING_STOPS = True

# Set trailing stop percentage
TRAILING_STOP_PERCENT = 0.05  # 5% - adjust based on volatility
```

## Strategy Customization Tips

### Finding Optimal Parameters

1. **Start Conservative:**

   - Begin with higher entry signal thresholds
   - Use wider trailing stops
   - Implement smaller position sizes

2. **Systematic Testing:**

   - Test one parameter change at a time
   - Document performance changes with each adjustment
   - Consider market conditions during testing periods

3. **Volatility Adaptation:**
   - Increase trailing stop percentages for more volatile securities
   - Decrease position sizes for higher volatility
   - Adjust indicator parameters based on price action characteristics

### Indicator Selection

Consider disabling or reducing the weight of indicators that don't perform well with your selected securities:

- **Trend Following Securities:** Emphasize MA and LBR indicators
- **Range-Bound Securities:** Emphasize Stochastic RSI and MFI
- **Volatile Securities:** Consider using Volume indicators and wider threshold ranges

## Charting and Visualization

### Multi-Symbol Version

The multi-symbol version creates separate charts for each traded symbol:

- Each symbol gets its own set of charts for clear visualization
- Entry and exit points are marked on price charts
- Indicator values are plotted for analysis

### Single-Symbol Version

The single symbol version includes enhanced charting with:

- Detailed price action and trade signals
- Indicator-specific charts with buy/sell markers
- Volume analysis with spike detection

### Viewing Charts in QuantConnect

1. Run your backtest
2. Click on the "Chart" tab in the backtest results
3. Use the dropdown menu to switch between different charts

## Live Trading Preparation

Before deploying to live trading:

1. **Paper Trading Validation:**

   - Test the strategy in paper trading for at least 1-3 months
   - Verify order execution and trailing stop behavior
   - Ensure signals work as expected in real-time

2. **Brokerage Compatibility:**

   - Confirm your brokerage supports trailing stop orders
   - If not, consider modifications to the algorithm
   - Test order types with small position sizes first

3. **Risk Management:**

   - Implement maximum drawdown limits
   - Consider daily loss limits
   - Start with smaller position sizes than backtest

4. **Monitoring Setup:**
   - Create alerts for unexpected behavior
   - Monitor trade execution quality
   - Track performance vs. backtest expectations

## Credits

This High Capacity Trading Algorithm was developed by:

- **Anton Reise**
- **Leif Koesling**

For questions, improvements, or collaboration, please contact the authors.

---

_Disclaimer: This strategy is provided for educational and research purposes only. Past performance is not indicative of future results. Trade at your own risk._
