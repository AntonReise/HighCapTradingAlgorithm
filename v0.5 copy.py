from AlgorithmImports import *
from collections import deque

class MultiIndicatorStrategy(QCAlgorithm):
    def Initialize(self):
        # Basic settings
        self.SetStartDate(2024, 1, 1)
        self.SetEndDate(2025, 1, 1)
        self.SetCash(100000)

        # Strategy parameters
        self.requiredSignals = 3          # Net signal threshold for triggering trades
        self.triggerWindow = 10           # Number of bars within which signals must appear
        self.useNetSignalCancellation = True  # Toggle to use net signal cancellation logic
        
        # Volume indicator parameters
        self.volumeSpikeMultiplier = 1.5  # Adjustable multiple for spike detection
        self.volumeLookback = 25          # Lookback period (in bars) for computing average volume
        
        # Trade allocation per position (reducing exposure; recommended lower than 20%)
        self.tradeAllocation = 0.1
        
        # List of large-cap symbols to trade
        self.symbols = ["JPM"]
                        #, "BAC", "GS"   # Financials
                        #"PFE", "MRK", "JNJ",   # Healthcare
                        #"XOM", "CVX",          # Energy
                        #"KO", "PEP", "PG",     # Consumer Goods
                        #"WMT", "TGT", "AMZN"]  # Retail
        
        # Dictionaries to hold indicators for each symbol
        self.ma9 = {}          # Moving Average (fast)
        self.ma20 = {}         # Moving Average (slow)
        self.stochRsi = {}     # Stochastic RSI
        self.mfi = {}          # Money Flow Index
        self.macd_lbr = {}     # LBR_OSC implemented via MACD
        
        # Initialize dictionaries for tracking state
        self.barCount = {}         # Count of bars processed per symbol
        self.buyTriggers = {}      # Dictionary of lists to store trigger bar numbers (per indicator)
        self.sellTriggers = {}     # Fixed the syntax error here
        self.entryPrices = {}      # Track entry price per symbol
        
        # Initialize counter dictionaries
        self.MABuyCounter = {}
        self.MASellCounter = {}
        self.LBROSCbuyCounter = {}
        self.LBROSCsellCounter = {}
        self.MFIbuyCounter = {}
        self.MFIsellCounter = {}
        self.SRSIbuyCounter = {}
        self.SRSIsellCounter = {}
        self.VOLUMEbuyCounter = {}
        self.VOLUMEsellCounter = {}
        
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
            self.ma9[symbol] = self.SMA(symbol, 9, Resolution.Hour)
            self.ma20[symbol] = self.SMA(symbol, 20, Resolution.Hour)
            
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

            # Initialize counters
            self.MABuyCounter[symbol] = 0
            self.MASellCounter[symbol] = 0
            self.LBROSCbuyCounter[symbol] = 0
            self.LBROSCsellCounter[symbol] = 0
            self.MFIbuyCounter[symbol] = 0
            self.MFIsellCounter[symbol] = 0
            self.SRSIbuyCounter[symbol] = 0
            self.SRSIsellCounter[symbol] = 0
            self.VOLUMEbuyCounter[symbol] = 0
            self.VOLUMEsellCounter[symbol] = 0
            
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

            # Process only if all indicators are ready
            if not (self.ma9[symbol].IsReady and self.ma20[symbol].IsReady and
                    self.stochRsi[symbol].IsReady and self.mfi[symbol].IsReady and
                    self.macd_lbr[symbol].IsReady):
                if self.barCount[symbol] == 1:  # Only show once at start
                    self.Debug(f"Warming up {sym}")
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
                    self.MABuyCounter[symbol] += 1
                # Fast MA crossing below slow MA generates a sell signal.
                if self.lastMa9[symbol] >= self.lastMa20[symbol] and ma9_val < ma20_val:
                    self.sellTriggers[symbol]["MA"].append(self.barCount[symbol])
                    self.MASellCounter[symbol] += 1
            
            # ---------------------------
            # Stochastic RSI Crosses
            # ---------------------------
            if self.lastStochK[symbol] is not None and self.lastStochD[symbol] is not None:
                # Both lines crossing upward through 20 produce a buy signal.
                if (self.lastStochK[symbol] <= 20 and stoch_k > 20 and
                    self.lastStochD[symbol] <= 20 and stoch_d > 20):
                    self.buyTriggers[symbol]["STOCH"].append(self.barCount[symbol])
                    self.SRSIbuyCounter[symbol] += 1
                # Both lines crossing downward through 80 produce a sell signal.
                if (self.lastStochK[symbol] >= 80 and stoch_k < 80 and
                    self.lastStochD[symbol] >= 80 and stoch_d < 80):
                    self.sellTriggers[symbol]["STOCH"].append(self.barCount[symbol])
                    self.SRSIsellCounter[symbol] += 1
            # ---------------------------
            # Money Flow Index (MFI) Crosses
            # ---------------------------
            if self.lastMfi[symbol] is not None:
                # MFI crossing upward through 20 produces a buy signal.
                if self.lastMfi[symbol] <= 20 and mfi_val > 20:
                    self.buyTriggers[symbol]["MFI"].append(self.barCount[symbol])
                    self.MFIbuyCounter[symbol] += 1
                # MFI crossing downward through 80 produces a sell signal.
                if self.lastMfi[symbol] >= 80 and mfi_val < 80:
                    self.sellTriggers[symbol]["MFI"].append(self.barCount[symbol])
                    self.MFIsellCounter[symbol] += 1
            
            # ---------------------------
            # LBR_OSC Indicator (via MACD Crossovers)
            # ---------------------------
            if self.lastMacdFast[symbol] is not None and self.lastMacdSlow[symbol] is not None:
                # MACD fast line crossing above slow line produces a buy signal.
                if self.lastMacdFast[symbol] <= self.lastMacdSlow[symbol] and macd_fast > macd_slow:
                    self.buyTriggers[symbol]["LBR"].append(self.barCount[symbol])
                    self.LBROSCbuyCounter[symbol] += 1
                # MACD fast line crossing below slow line produces a sell signal.
                if self.lastMacdFast[symbol] >= self.lastMacdSlow[symbol] and macd_fast < macd_slow:
                    self.sellTriggers[symbol]["LBR"].append(self.barCount[symbol])
                    self.LBROSCsellCounter[symbol] += 1
                    
            
            # ---------------------------
            # Volume Spike Indicator
            # ---------------------------
            # For bullish (up) candles, check if volume is significantly above average.
            if bar.Close > bar.Open:
                avgVolume = self.ComputeAverageVolume(self.volumeUp[symbol])
                if avgVolume is not None and bar.Volume >= self.volumeSpikeMultiplier * avgVolume:
                    self.buyTriggers[symbol]["VOL"].append(self.barCount[symbol])
                    self.VOLUMEbuyCounter[symbol] += 1
            # For bearish (down) candles, check similarly.
            elif bar.Close < bar.Open:
                avgVolume = self.ComputeAverageVolume(self.volumeDown[symbol])
                if avgVolume is not None and bar.Volume >= self.volumeSpikeMultiplier * avgVolume:
                    self.sellTriggers[symbol]["VOL"].append(self.barCount[symbol])
                    self.VOLUMEsellCounter[symbol] += 1
            
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
                active_signals = []
                for ind in indicators:
                    buyList = self.buyTriggers[symbol][ind]
                    sellList = self.sellTriggers[symbol][ind]
                    if buyList or sellList:
                        latestBuy = max(buyList) if buyList else -float('inf')
                        latestSell = max(sellList) if sellList else -float('inf')
                        if latestBuy > latestSell:
                            netSignal += 1
                            active_signals.append(f"{ind}:BUY")
                        elif latestSell > latestBuy:
                            netSignal -= 1
                            active_signals.append(f"{ind}:SELL")
                
                shouldBuy = netSignal >= self.requiredSignals
                shouldSell = netSignal <= -self.requiredSignals

                if shouldBuy or shouldSell:
                    self.Debug(f"[{bar.Time}] {sym} - Bar {self.barCount[symbol]}")
                    self.Debug(f"Symbol: {sym}, NetSignal: {netSignal}, shouldBuy: {shouldBuy}, shouldSell: {shouldSell}")
                    self.Debug(f"{sym} Signals: {', '.join(active_signals)} | Net: {netSignal}")

            else:
                buyCount = sum(1 for ind in indicators if len(self.buyTriggers[symbol][ind]) > 0)
                sellCount = sum(1 for ind in indicators if len(self.sellTriggers[symbol][ind]) > 0)
                netSignal = buyCount - sellCount
                shouldBuy = buyCount >= self.requiredSignals
                shouldSell = sellCount >= self.requiredSignals

                if shouldBuy or shouldSell:
                    self.Debug(f"[{bar.Time}] {sym} - Bar {self.barCount[symbol]}")
                    self.Debug(f"Symbol: {sym}, NetSignal: {netSignal}, shouldBuy: {shouldBuy}, shouldSell: {shouldSell}")
            
            # ---------------------------
            # Trade Execution
            # ---------------------------
            invested = self.Portfolio[symbol].Invested
            if not invested and shouldBuy:
                self.Debug(f"[{bar.Time}] BUY executed for {sym} at ${price:0.2f}")
                self.SetHoldings(symbol, self.tradeAllocation)
                self.entryPrices[symbol] = price
            elif invested and shouldSell:
                self.Debug(f"[{bar.Time}] SELL executed for {sym} at ${price:0.2f}")
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
        if bar.Close > bar.Open:
            self.volumeUp[symbol].append(bar.Volume)
        elif bar.Close < bar.Open:
            self.volumeDown[symbol].append(bar.Volume)
        # If the candle is neutral (Close == Open), do not update either window.

    def OnEndOfAlgorithm(self):
        """Display final statistics for each symbol"""
        self.Debug("\n=== FINAL TRADING STATISTICS ===")
        
        for sym in self.symbols:
            symbol = self.Securities[sym].Symbol
            stats = self.Portfolio[symbol]
            
            # Combine all statistics into fewer, more concise lines
            self.Debug(f"\n{sym} Summary:")
            self.Debug("Signal Counts (Buy/Sell):")
            self.Debug(f"MA: {self.MABuyCounter[symbol]}/{self.MASellCounter[symbol]} | " +
                      f"RSI: {self.SRSIbuyCounter[symbol]}/{self.SRSIsellCounter[symbol]} | " +
                      f"MFI: {self.MFIbuyCounter[symbol]}/{self.MFIsellCounter[symbol]} | " +
                      f"VOL: {self.VOLUMEbuyCounter[symbol]}/{self.VOLUMEsellCounter[symbol]} | " +
                      f"LBR: {self.LBROSCbuyCounter[symbol]}/{self.LBROSCsellCounter[symbol]}")
            
            total_buy_signals = (self.MABuyCounter[symbol] + self.SRSIbuyCounter[symbol] + 
                               self.MFIbuyCounter[symbol] + self.VOLUMEbuyCounter[symbol] + 
                               self.LBROSCbuyCounter[symbol])
            total_sell_signals = (self.MASellCounter[symbol] + self.SRSIsellCounter[symbol] + 
                                self.MFIsellCounter[symbol] + self.VOLUMEsellCounter[symbol] + 
                                self.LBROSCsellCounter[symbol])
            
            self.Debug(f"Total Signals - Buy: {total_buy_signals}, Sell: {total_sell_signals}")
            self.Debug(f"Performance - Trades: {stats.TotalSaleVolume}, Profit: ${stats.Profit:0.2f}, Avg Price: ${stats.AveragePrice:0.2f}")
