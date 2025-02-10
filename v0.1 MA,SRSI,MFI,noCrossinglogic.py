from AlgorithmImports import *

class MultiIndicatorStrategy(QCAlgorithm):
    def Initialize(self):
        # Basic settings
        self.SetStartDate(2020, 1, 1)
        self.SetEndDate(2023, 1, 1)
        self.SetCash(100000)

        # Choose several large-cap symbols, each managed independently
        self.symbols = ["IBM", "T", "VZ", "XOM", "PFE", "MRK", "KO", "PEP", "MCD", "WMT"]

        # Dictionaries to hold indicators for each symbol
        self.ma9 = {}
        self.ma20 = {}
        self.stochRsi = {}
        self.mfi = {}

        # Track bar counts (for the 5-bar signal window) and triggers
        self.barCount = {}

        # For each symbol, store buy/sell triggers in the last 5 bars.
        self.buyTriggers = {}
        self.sellTriggers = {}

        # Track whether we are in a position for each symbol (and entry price if desired)
        self.entryPrices = {}

        # Add each symbol at hourly resolution and set up indicators
        for sym in self.symbols:
            equity = self.AddEquity(sym, Resolution.Hour)
            symbol = equity.Symbol

            self.barCount[symbol] = 0

            # Initialize the SMA(9) and SMA(20)
            self.ma9[symbol] = self.SMA(symbol, 59, Resolution.Hour)
            self.ma20[symbol] = self.SMA(symbol, 130, Resolution.Hour)

            # Initialize the Stoch RSI
            self.stochRsi[symbol] = self.SRSI(symbol, 14, 14, 3, 3)

            # Initialize the Money Flow Index
            self.mfi[symbol] = self.MFI(symbol, 14)

            self.buyTriggers[symbol] = {"MA": [], "STOCH": [], "MFI": []}
            self.sellTriggers[symbol] = {"MA": [], "STOCH": [], "MFI": []}

            self.entryPrices[symbol] = None

        self.SetWarmUp(130, Resolution.Hour)

    def OnData(self, data):
        if self.IsWarmingUp:
            return

        for sym in self.symbols:
            if sym not in data.Bars:
                continue

            symbol = self.Securities[sym].Symbol
            self.barCount[symbol] += 1

            if not (self.ma9[symbol].IsReady and self.ma20[symbol].IsReady 
                    and self.stochRsi[symbol].IsReady and self.mfi[symbol].IsReady):
                continue

            ma9_val = self.ma9[symbol].Current.Value
            ma20_val = self.ma20[symbol].Current.Value
            stoch_k = self.stochRsi[symbol].K.Current.Value
            stoch_d = self.stochRsi[symbol].D.Current.Value
            mfi_val = self.mfi[symbol].Current.Value
            price = data.Bars[sym].Close if sym in data.Bars else self.Securities[sym].Price

            # Maintain BUY triggers
            if ma9_val > ma20_val:
                self.buyTriggers[symbol]["MA"].append(self.barCount[symbol])
            if (stoch_k > 20) and (stoch_d > 20):
                self.buyTriggers[symbol]["STOCH"].append(self.barCount[symbol])
            if mfi_val > 20:
                self.buyTriggers[symbol]["MFI"].append(self.barCount[symbol])

            # Maintain SELL triggers
            if ma9_val < ma20_val:
                self.sellTriggers[symbol]["MA"].append(self.barCount[symbol])
            if (stoch_k < 80) and (stoch_d < 80):
                self.sellTriggers[symbol]["STOCH"].append(self.barCount[symbol])
            if mfi_val < 80:
                self.sellTriggers[symbol]["MFI"].append(self.barCount[symbol])

            # Prune old triggers beyond the 5-bar window
            cutoff = self.barCount[symbol] - 4
            for indicatorName in self.buyTriggers[symbol]:
                self.buyTriggers[symbol][indicatorName] = [x for x in self.buyTriggers[symbol][indicatorName] if x >= cutoff]
            for indicatorName in self.sellTriggers[symbol]:
                self.sellTriggers[symbol][indicatorName] = [x for x in self.sellTriggers[symbol][indicatorName] if x >= cutoff]

            # Check if all indicators triggered in the last 5 bars
            all_buy = (
                len(self.buyTriggers[symbol]["MA"]) > 0 and
                len(self.buyTriggers[symbol]["STOCH"]) > 0 and
                len(self.buyTriggers[symbol]["MFI"]) > 0
            )

            all_sell = (
                len(self.sellTriggers[symbol]["MA"]) > 0 and
                len(self.sellTriggers[symbol]["STOCH"]) > 0 and
                len(self.sellTriggers[symbol]["MFI"]) > 0
            )

            invested = self.Portfolio[symbol].Invested

            # Execute trades
            if not invested and all_buy:
                self.SetHoldings(symbol, 0.2)
                self.entryPrices[symbol] = price

            elif invested and all_sell:
                self.Liquidate(symbol)
                self.entryPrices[symbol] = None

            # Plot stock price
            self.Plot(sym, "Price", price)

            # Plot indicators
            self.Plot(sym, "MA9", ma9_val)
            self.Plot(sym, "MA20", ma20_val)
            self.Plot(sym, "StochK", stoch_k)
            self.Plot(sym, "StochD", stoch_d)
            self.Plot(sym, "MFI", mfi_val)
