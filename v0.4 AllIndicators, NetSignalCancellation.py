from AlgorithmImports import *
from collections import deque

class MultiIndicatorStrategy(QCAlgorithm):
    def Initialize(self):
        # Basic settings
        self.SetStartDate(2000, 1, 1)
        self.SetEndDate(2015, 1, 1)
        self.SetCash(100000)

        # Strategy parameters
        self.requiredSignals = 2          # Net signal threshold for triggering trades
        self.triggerWindow = 10           # Number of bars within which signals must appear
        self.useNetSignalCancellation = True  # Toggle to use net signal cancellation logic
        
        # Volume indicator parameters
        self.volumeSpikeMultiplier = 2.0  # Adjustable multiple for spike detection
        self.volumeLookback = 20          # Lookback period (in bars) for computing average volume
        
        # Trade allocation per position (reducing exposure; recommended lower than 20%)
        self.tradeAllocation = 0.1
        
        # List of large-cap symbols to trade
        self.symbols = ["JPM", "BAC", "GS",   # Financials
                        "PFE", "MRK", "JNJ",   # Healthcare
                        "XOM", "CVX",          # Energy
                        "KO", "PEP", "PG",     # Consumer Goods
                        "WMT", "TGT", "AMZN"]  # Retail
        
        # Dictionaries to hold indicators for each symbol
        self.ma9 = {}          # Moving Average (fast)
        self.ma20 = {}         # Moving Average (slow)
        self.stochRsi = {}     # Stochastic RSI
        self.mfi = {}          # Money Flow Index
        self.macd_lbr = {}     # LBR_OSC implemented via MACD
        
        # Dictionaries for tracking state
        self.barCount = {}         # Count of bars processed per symbol
        self.buyTriggers = {}      # Dictionary of lists to store trigger bar numbers (per indicator)
        self.sellTriggers = {}     # Fixed the syntax error here
        self.entryPrices = {}      # Track entry price per symbol
        
        # Previous indicator values for crossover detection
        self.lastMa9 = {}
        self.lastMa20 = {}
        self.lastStochK = {}
        self.lastStochD = {}
        self.lastMfi = {}
        self.lastMacdFast = {}
        self.lastMacdSlow = {}
        
        # Rolling windows for volume calculations (separate for bullish and bearish candles)
        self.volumeUp = {}
        self.volumeDown = {}
        
        # Add each symbol and initialize indicators and data structures
        for sym in self.symbols:
            equity = self.AddEquity(sym, Resolution.Hour)
            symbol = equity.Symbol
            
            self.barCount[symbol] = 0
            
            # Moving averages approximating 9-day and 20-day periods (using hourly bars)
            self.ma9[symbol] = self.SMA(symbol, 59, Resolution.Hour)
            self.ma20[symbol] = self.SMA(symbol, 130, Resolution.Hour)
            
            # Stochastic RSI and Money Flow Index
            self.stochRsi[symbol] = self.SRSI(symbol, 14, 14, 3, 3)
            self.mfi[symbol] = self.MFI(symbol, 14)
            
            # LBR_OSC using MACD (fast=3, slow=10, signal=16, with exponential averages)
            self.macd_lbr[symbol] = self.MACD(symbol, 3, 10, 16, MovingAverageType.Exponential, Resolution.Hour)
            
            # Initialize trigger dictionaries for each indicator
            self.buyTriggers[symbol] = {"MA": [], "STOCH": [], "MFI": [], "VOL": [], "LBR": []}
            self.sellTriggers[symbol] = {"MA": [], "STOCH": [], "MFI": [], "VOL": [], "LBR": []}
            
            # Entry price tracking
            self.entryPrices[symbol] = None
            
            # Initialize previous values (set to None)
            self.lastMa9[symbol] = None
            self.lastMa20[symbol] = None
            self.lastStochK[symbol] = None
            self.lastStochD[symbol] = None
            self.lastMfi[symbol] = None
            self.lastMacdFast[symbol] = None
            self.lastMacdSlow[symbol] = None
            
            # Initialize rolling windows for volume (bullish and bearish candles)
            from collections import deque
            self.volumeUp[symbol] = deque(maxlen=self.volumeLookback)
            self.volumeDown[symbol] = deque(maxlen=self.volumeLookback)
        
        # Set warm-up period: must be at least as long as the longest indicator lookback
        warmupBars = max(130, self.volumeLookback)
        self.SetWarmUp(warmupBars, Resolution.Hour)

    def OnData(self, data):
        if self.IsWarmingUp:
            return
        
        for sym in self.symbols:
            if sym not in data.Bars:
                continue
            
            symbol = self.Securities[sym].Symbol
            self.barCount[symbol] += 1
            bar = data.Bars[sym]
            price = bar.Close
            
            # Process only if all indicators are ready.
            if not (self.ma9[symbol].IsReady and self.ma20[symbol].IsReady and
                    self.stochRsi[symbol].IsReady and self.mfi[symbol].IsReady and
                    self.macd_lbr[symbol].IsReady):
                # Even if indicators are not ready, update the volume windows.
                self.UpdateVolumeRollingWindow(symbol, bar)
                continue
            
            # Retrieve current indicator values.
            ma9_val = self.ma9[symbol].Current.Value
            ma20_val = self.ma20[symbol].Current.Value
            stoch_k = self.stochRsi[symbol].K.Current.Value
            stoch_d = self.stochRsi[symbol].D.Current.Value
            mfi_val = self.mfi[symbol].Current.Value
            macd_fast = self.macd_lbr[symbol].Fast.Current.Value
            macd_slow = self.macd_lbr[symbol].Slow.Current.Value
            
            # ---------------------------
            # Moving Averages (MA) Cross Detection
            # ---------------------------
            if self.lastMa9[symbol] is not None and self.lastMa20[symbol] is not None:
                # Fast MA (ma9) crossing above slow MA (ma20) generates a buy signal.
                if self.lastMa9[symbol] <= self.lastMa20[symbol] and ma9_val > ma20_val:
                    self.buyTriggers[symbol]["MA"].append(self.barCount[symbol])
                # Fast MA crossing below slow MA generates a sell signal.
                if self.lastMa9[symbol] >= self.lastMa20[symbol] and ma9_val < ma20_val:
                    self.sellTriggers[symbol]["MA"].append(self.barCount[symbol])
            
            # ---------------------------
            # Stochastic RSI Crosses
            # ---------------------------
            if self.lastStochK[symbol] is not None and self.lastStochD[symbol] is not None:
                # Both lines crossing upward through 20 produce a buy signal.
                if (self.lastStochK[symbol] <= 20 and stoch_k > 20 and
                    self.lastStochD[symbol] <= 20 and stoch_d > 20):
                    self.buyTriggers[symbol]["STOCH"].append(self.barCount[symbol])
                # Both lines crossing downward through 80 produce a sell signal.
                if (self.lastStochK[symbol] >= 80 and stoch_k < 80 and
                    self.lastStochD[symbol] >= 80 and stoch_d < 80):
                    self.sellTriggers[symbol]["STOCH"].append(self.barCount[symbol])
            
            # ---------------------------
            # Money Flow Index (MFI) Crosses
            # ---------------------------
            if self.lastMfi[symbol] is not None:
                # MFI crossing upward through 20 produces a buy signal.
                if self.lastMfi[symbol] <= 20 and mfi_val > 20:
                    self.buyTriggers[symbol]["MFI"].append(self.barCount[symbol])
                # MFI crossing downward through 80 produces a sell signal.
                if self.lastMfi[symbol] >= 80 and mfi_val < 80:
                    self.sellTriggers[symbol]["MFI"].append(self.barCount[symbol])
            
            # ---------------------------
            # LBR_OSC Indicator (via MACD Crossovers)
            # ---------------------------
            if self.lastMacdFast[symbol] is not None and self.lastMacdSlow[symbol] is not None:
                # MACD fast line crossing above slow line produces a buy signal.
                if self.lastMacdFast[symbol] <= self.lastMacdSlow[symbol] and macd_fast > macd_slow:
                    self.buyTriggers[symbol]["LBR"].append(self.barCount[symbol])
                # MACD fast line crossing below slow line produces a sell signal.
                if self.lastMacdFast[symbol] >= self.lastMacdSlow[symbol] and macd_fast < macd_slow:
                    self.sellTriggers[symbol]["LBR"].append(self.barCount[symbol])
            
            # ---------------------------
            # Volume Spike Indicator
            # ---------------------------
            # For bullish (up) candles, check if volume is significantly above average.
            if bar.Close > bar.Open:
                avgVolume = self.ComputeAverageVolume(self.volumeUp[symbol])
                if avgVolume is not None and bar.Volume >= self.volumeSpikeMultiplier * avgVolume:
                    self.buyTriggers[symbol]["VOL"].append(self.barCount[symbol])
            # For bearish (down) candles, check similarly.
            elif bar.Close < bar.Open:
                avgVolume = self.ComputeAverageVolume(self.volumeDown[symbol])
                if avgVolume is not None and bar.Volume >= self.volumeSpikeMultiplier * avgVolume:
                    self.sellTriggers[symbol]["VOL"].append(self.barCount[symbol])
            
            # Update the volume rolling windows with the current bar's volume data.
            self.UpdateVolumeRollingWindow(symbol, bar)
            
            # ---------------------------
            # Prune Old Triggers Outside the Trigger Window
            # ---------------------------
            cutoff = self.barCount[symbol] - (self.triggerWindow - 1)
            for key in self.buyTriggers[symbol]:
                self.buyTriggers[symbol][key] = [t for t in self.buyTriggers[symbol][key] if t >= cutoff]
            for key in self.sellTriggers[symbol]:
                self.sellTriggers[symbol][key] = [t for t in self.sellTriggers[symbol][key] if t >= cutoff]
            
            # ---------------------------
            # Signal Aggregation Across Indicators
            # ---------------------------
            indicators = ["MA", "STOCH", "MFI", "VOL", "LBR"]
            netSignal = 0
            if self.useNetSignalCancellation:
                # For each indicator, consider only the most recent signal in the trigger window.
                for ind in indicators:
                    buyList = self.buyTriggers[symbol][ind]
                    sellList = self.sellTriggers[symbol][ind]
                    if buyList or sellList:
                        latestBuy = max(buyList) if buyList else -float('inf')
                        latestSell = max(sellList) if sellList else -float('inf')
                        # Use the most recent signal from this indicator.
                        if latestBuy > latestSell:
                            netSignal += 1
                        elif latestSell > latestBuy:
                            netSignal -= 1
                        # If equal (rare), no contribution.
                shouldBuy = netSignal >= self.requiredSignals
                shouldSell = netSignal <= -self.requiredSignals
            else:
                # Old logic: each indicator contributes once if any signal exists.
                buyCount = sum(1 for ind in indicators if len(self.buyTriggers[symbol][ind]) > 0)
                sellCount = sum(1 for ind in indicators if len(self.sellTriggers[symbol][ind]) > 0)
                netSignal = buyCount - sellCount
                shouldBuy = netSignal >= self.requiredSignals
                shouldSell = netSignal <= -self.requiredSignals
            
            # ---------------------------
            # Trade Execution
            # ---------------------------
            invested = self.Portfolio[symbol].Invested
            if not invested and shouldBuy:
                self.SetHoldings(symbol, self.tradeAllocation)
                self.entryPrices[symbol] = price
            elif invested and shouldSell:
                self.Liquidate(symbol)
                self.entryPrices[symbol] = None
            
            # ---------------------------
            # Plotting for Diagnostics
            # ---------------------------
            self.Plot(sym, "Price", price)
            self.Plot(sym, "MA9", ma9_val)
            self.Plot(sym, "MA20", ma20_val)
            self.Plot(sym, "StochK", stoch_k)
            self.Plot(sym, "StochD", stoch_d)
            self.Plot(sym, "MFI", mfi_val)
            self.Plot(sym, "MACD Fast", macd_fast)
            self.Plot(sym, "MACD Slow", macd_slow)
            self.Plot(sym, "NetSignal", netSignal)
            
            # ---------------------------
            # Update Previous Indicator Values for Next Bar
            # ---------------------------
            self.lastMa9[symbol] = ma9_val
            self.lastMa20[symbol] = ma20_val
            self.lastStochK[symbol] = stoch_k
            self.lastStochD[symbol] = stoch_d
            self.lastMfi[symbol] = mfi_val
            self.lastMacdFast[symbol] = macd_fast
            self.lastMacdSlow[symbol] = macd_slow

    def ComputeAverageVolume(self, volumeWindow):
        # Return the average volume from the provided rolling window (if not empty)
        if len(volumeWindow) == 0:
            return None
        return float(sum(volumeWindow)) / len(volumeWindow)

    def UpdateVolumeRollingWindow(self, symbol, bar):
        # Update the volume rolling windows.
        # For an up candle (bullish), update the bullish volume window.
        if bar.Close > bar.Open:
            self.volumeUp[symbol].append(bar.Volume)
        # For a down candle (bearish), update the bearish volume window.
        elif bar.Close < bar.Open:
            self.volumeDown[symbol].append(bar.Volume)
        # If the candle is neutral (Close equals Open), do not update either window.
