# High Capacity Trading Algorithm

A sophisticated multi-indicator strategy implementing adaptive trend following with signal aggregation for both single and multiple securities trading on QuantConnect.

<span style="color:red;"><strong>This template is for developing and backtesting strategies using multiple technical indicators. It is not intended for immediate live trading.</strong></span>

Authors: Anton Reise, Leif Koesling

## Quick Start Guide

1. **Choose a Version:**
   - **v2 Single-Symbol:** Focused trading on one security with enhanced visualization.
   - **v2 Multi-Symbol:** Simultaneously trade multiple securities.

2. **Setup on QuantConnect:**
   - Create an account at [quantconnect.com](https://www.quantconnect.com).
   - Start a new algorithm project and paste in the appropriate version.

3. **Configure Your Strategy:**
   - Set your trading symbols and adjust signal thresholds.
   - Customize indicator settings (see Critical Configuration below).

4. **Run a Backtest:**
   - Click “Backtest” on QuantConnect.
   - Analyze performance and refine parameters as needed.

## Overview

This repository offers two implementations of the same core strategy:
- **Multi-Symbol Version:** Trades multiple securities with independent signal evaluation.
- **Single-Symbol Version:** Focuses on a single security with enhanced charting.

## Features

- Multi-indicator approach with aggregated signals for precise entries and exits.
- Configurable parameters for indicators, trailing stops, and position sizing.
- Automatic trailing stop management to protect positions.
- Detailed charting for clear performance visualization.

## Critical Configuration & Customization

Customize these parameters to align with your trading objectives. The settings below directly affect trade signal generation and risk management:

| Parameter                  | Description                           | Recommendation                                  |
| -------------------------- | ------------------------------------- | ----------------------------------------------- |
| SYMBOL/SYMBOLS             | Securities to trade                   | Select liquid assets with high trading volume   |
| REQUIRED_ENTRY_SIGNALS     | Entry signal threshold                | Higher = fewer, quality trades                  |
| REQUIRED_EXIT_SIGNALS      | Exit signal threshold                 | Lower = quicker exits                           |
| TRAILING_STOP_PERCENT      | Trailing stop distance                | Set according to asset volatility               |

### Indicator Toggles & Weights

Configure which indicators to use and their respective influence:

```python
# Indicator enable toggles
ENABLE_MA = True      # Moving Average Crossover
ENABLE_STOCH = True   # Stochastic RSI
ENABLE_LBR = True     # LBR Oscillator
ENABLE_MFI = True     # Money Flow Index
ENABLE_VOL = True     # Volume Analysis

# Indicator weights (affect signal aggregation)
MA_WEIGHT = 2.0       
STOCH_WEIGHT = 1.0    
LBR_WEIGHT = 2.0      
MFI_WEIGHT = 1.0      
VOL_WEIGHT = 1.0
```

### Trailing Stop Settings

Configure trailing stops for automatic trade protection:

```python
# Enable trailing stops
ENABLE_TRAILING_STOPS = True

# Set trailing stop percentage (e.g., 5% for moderate volatility)
TRAILING_STOP_PERCENT = 0.05
```

## Indicators Used

The strategy uses the following technical indicators to generate trading signals:

| Indicator                | Description                                                 |
| ------------------------ | ----------------------------------------------------------- |
| Moving Average Crossover | Fast and slow moving averages to identify trend shifts      |
| Stochastic RSI           | Combines RSI and stochastic oscillator for momentum         |
| LBR Oscillator           | Custom oscillator derived from MACD parameters              |
| Money Flow Index (MFI)   | Volume-weighted indicator to gauge buying/selling pressure    |
| Volume Spikes            | Detects abnormal volume surges indicating potential moves     |

## Credits

Developed by:
- Anton Reise
- Leif Koesling

For questions, improvements, or collaboration, please contact the author.
