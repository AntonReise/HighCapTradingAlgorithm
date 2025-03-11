from AlgorithmImports import *
import math

# Global Parameters
SYMBOLS = ["AAPL", "MSFT"]  # Use as many symbols as needed
START_DATE = "2021-01-01"
END_DATE = "2022-01-01"
INITIAL_CASH = 100000
TRIGGER_WINDOW = 5
REQUIRED_ENTRY_SIGNALS = 5
REQUIRED_EXIT_SIGNALS = 5
FIRST_TRADE_ALLOCATION = 0.1 #By having it be 0.1, it means that the first trade will be 10% of the portfolio,
REPEAT_TRADE_ALLOCATION = 0.1 #and the next trades will increase the portfolio share by 10% respectively. Note: if there are many orders, it will return an error due to a lack of puchasing power (cash).

# Trailing Stop Configuration
ENABLE_TRAILING_STOPS = True  # Set to False to disable trailing stops
TRAILING_STOP_PERCENT = 0.05  # 5% trailing stop

# Set these to False if you want to disable an indicator
ENABLE_MA = True
ENABLE_STOCH = True
ENABLE_LBR = True
ENABLE_MFI = True
ENABLE_VOL = True

# Custom Indicator Signal Weights
MA_WEIGHT = 2.0
STOCH_WEIGHT = 1.0
LBR_WEIGHT = 2.0
MFI_WEIGHT = 1.0
VOL_WEIGHT = 1.0

# Indicator Parameters
# Moving Average
MA_FAST_PERIOD = 9
MA_SLOW_PERIOD = 20

# Stochastic RSI
STOCH_PERIOD = 14
STOCH_SMOOTH_K = 3
STOCH_SMOOTH_D = 3
STOCH_UPPER = 80
STOCH_LOWER = 20
STOCH_LOOKBACK = 3

# Money Flow Index
MFI_PERIOD = 14
MFI_UPPER = 80
MFI_LOWER = 20

# LBR Oscillator
MACD_FAST = 3
MACD_SLOW = 10
MACD_SIGNAL = 16

# Volume Spikes
VOLUME_SPIKE_MULTIPLIER = 2.0
VOLUME_LOOKBACK = 35

# Turn charting on/off 
ENABLE_CHARTING = True
# Individual charts (Can be usefull in cases where free plan limits restrict the number of series, leading to some values missing)
ENABLE_MA_CHART = True
ENABLE_STOCH_CHART = True
ENABLE_LBR_CHART = True
ENABLE_MFI_CHART = True
ENABLE_VOL_CHART = True
ENABLE_TRADE_CHART = True

class HighCapMultiIndicatorStrategy(QCAlgorithm):
    def Initialize(self):
        # Set dates and cash
        start_year, start_month, start_day = map(int, START_DATE.split("-"))
        end_year, end_month, end_day = map(int, END_DATE.split("-"))
        self.SetStartDate(start_year, start_month, start_day)
        self.SetEndDate(end_year, end_month, end_day)
        self.SetCash(INITIAL_CASH)
        self.resolution = Resolution.Hour  # Hourly resolution
        
        # Set brokerage model to ensure trailing stop orders are supported
        self.SetBrokerageModel(BrokerageName.QuantConnectBrokerage)
        
        self.SetWarmUp(50, self.resolution)

        # Initialize symbols and add equities
        self.symbols = []
        for ticker in SYMBOLS:
            symbol = self.AddEquity(ticker, self.resolution).Symbol
            self.symbols.append(symbol)

        # Create dictionaries to hold per-symbol indicators
        self.short_sma = {}
        self.long_sma = {}
        self.srsi = {}
        self.macd = {}
        self.mfi = {}
        self.sma_vol = {}

        # Initialize indicators for each symbol
        for symbol in self.symbols:
            self.short_sma[symbol] = self.SMA(symbol, MA_FAST_PERIOD, self.resolution)
            self.long_sma[symbol] = self.SMA(symbol, MA_SLOW_PERIOD, self.resolution)
            self.srsi[symbol] = self.SRSI(symbol, STOCH_PERIOD, STOCH_PERIOD, STOCH_SMOOTH_K, STOCH_SMOOTH_D, self.resolution)
            self.macd[symbol] = self.MACD(symbol, MACD_FAST, MACD_SLOW, MACD_SIGNAL, MovingAverageType.Simple, self.resolution)
            self.mfi[symbol] = self.MFI(symbol, MFI_PERIOD)
            self.sma_vol[symbol] = self.SMA(symbol, VOLUME_LOOKBACK, self.resolution, Field.Volume)

        # Initialize per-symbol indicator signal lists
        self.ma_indicator_signals = {}
        self.stoch_indicator_signals = {}
        self.lbr_indicator_signals = {}
        self.mfi_indicator_signals = {}
        self.vol_indicator_signals = {}

        # Also keep per-symbol indicator value lists (for potential debugging/charting)
        self.ma9_values = {}
        self.ma20_values = {}
        self.stoch_k_values = {}
        self.stoch_d_values = {}
        self.lbr_values = {}
        self.lbr_signal_values = {}
        self.mfi_values = {}
        self.vol_values = {}
        self.vol_sma_values = {}

        # For each symbol, initialize lists and rolling windows
        self.ma9_window = {}
        self.ma20_window = {}
        self.stoch_k_window = {}
        self.stoch_d_window = {}
        self.stoch_k_cross_window = {}
        self.stoch_d_cross_window = {}
        self.lbr_window = {}
        self.lbr_signal_window = {}
        self.mfi_window = {}
        self.previous_close = {}

        for symbol in self.symbols:
            if ENABLE_MA:
                self.ma_indicator_signals[symbol] = [None] * TRIGGER_WINDOW
            if ENABLE_STOCH:
                self.stoch_indicator_signals[symbol] = [None] * TRIGGER_WINDOW
            if ENABLE_LBR:
                self.lbr_indicator_signals[symbol] = [None] * TRIGGER_WINDOW
            if ENABLE_MFI:
                self.mfi_indicator_signals[symbol] = [None] * TRIGGER_WINDOW
            if ENABLE_VOL:
                self.vol_indicator_signals[symbol] = [None] * TRIGGER_WINDOW

            self.ma9_values[symbol] = []
            self.ma20_values[symbol] = []
            self.stoch_k_values[symbol] = []
            self.stoch_d_values[symbol] = []
            self.lbr_values[symbol] = []
            self.lbr_signal_values[symbol] = []
            self.mfi_values[symbol] = []
            self.vol_values[symbol] = []
            self.vol_sma_values[symbol] = []

            self.ma9_window[symbol] = RollingWindow[float](2)
            self.ma20_window[symbol] = RollingWindow[float](2)
            self.stoch_k_window[symbol] = RollingWindow[float](2)
            self.stoch_d_window[symbol] = RollingWindow[float](2)
            self.stoch_k_cross_window[symbol] = RollingWindow[bool](STOCH_LOOKBACK)
            self.stoch_d_cross_window[symbol] = RollingWindow[bool](STOCH_LOOKBACK)
            self.lbr_window[symbol] = RollingWindow[float](2)
            self.lbr_signal_window[symbol] = RollingWindow[float](2)
            self.mfi_window[symbol] = RollingWindow[float](2)
            self.previous_close[symbol] = None

        # Build dictionary of indicator signal lists per symbol
        self.indicator_signal_lists = {}
        for symbol in self.symbols:
            self.indicator_signal_lists[symbol] = {}
            if ENABLE_MA:
                self.indicator_signal_lists[symbol]["MA"] = self.ma_indicator_signals[symbol]
            if ENABLE_STOCH:
                self.indicator_signal_lists[symbol]["STOCH"] = self.stoch_indicator_signals[symbol]
            if ENABLE_LBR:
                self.indicator_signal_lists[symbol]["LBR"] = self.lbr_indicator_signals[symbol]
            if ENABLE_MFI:
                self.indicator_signal_lists[symbol]["MFI"] = self.mfi_indicator_signals[symbol]
            if ENABLE_VOL:
                self.indicator_signal_lists[symbol]["VOL"] = self.vol_indicator_signals[symbol]

        # Create dictionary for indicator weights (remains unchanged)
        self.indicator_weights = {}
        if ENABLE_MA:
            self.indicator_weights["MA"] = MA_WEIGHT
        if ENABLE_STOCH:
            self.indicator_weights["STOCH"] = STOCH_WEIGHT
        if ENABLE_LBR:
            self.indicator_weights["LBR"] = LBR_WEIGHT
        if ENABLE_MFI:
            self.indicator_weights["MFI"] = MFI_WEIGHT
        if ENABLE_VOL:
            self.indicator_weights["VOL"] = VOL_WEIGHT

        # Trade tracking dictionaries (per symbol)
        self.trade_stats = {symbol: {} for symbol in self.symbols}
        self.current_trades = {symbol: None for symbol in self.symbols}
        
        # Create dictionary to track trailing stop order tickets for each symbol
        self._TrailingStopOrderTicket = {symbol: None for symbol in self.symbols}

        # Charting: Create a separate chart for each indicator per symbol
        for symbol in self.symbols:
            sym_str = symbol.Value
            
            if ENABLE_CHARTING:
                # MA Chart
                if ENABLE_MA_CHART:
                    ma_chart = Chart(f"{sym_str}_MA")
                    ma_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
                    ma_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
                    ma_chart.add_series(Series("9 Period Value", SeriesType.LINE, "$", Color.ORANGE))
                    ma_chart.add_series(Series("20 Period Value", SeriesType.LINE, "$", Color.BLUE))
                    self.AddChart(ma_chart)

                # STOCHRSI Chart
                if ENABLE_STOCH_CHART:
                    stochrsi_chart = Chart(f"{sym_str}_STOCHRSI")
                    stochrsi_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
                    stochrsi_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
                    stochrsi_chart.add_series(Series("K Value", SeriesType.LINE, "$", Color.BLUE))
                    stochrsi_chart.add_series(Series("D Value", SeriesType.LINE, "$", Color.ORANGE))
                    self.AddChart(stochrsi_chart)

                # LBROSC Chart
                if ENABLE_LBR_CHART:
                    lbrosc_chart = Chart(f"{sym_str}_LBROSC")
                    lbrosc_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
                    lbrosc_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
                    lbrosc_chart.add_series(Series("MACD Value", SeriesType.LINE, "$", Color.BLUE))
                    lbrosc_chart.add_series(Series("MACD Signal Value", SeriesType.LINE, "$", Color.ORANGE))
                    self.AddChart(lbrosc_chart)

                # MFI Chart
                if ENABLE_MFI_CHART:
                    mfi_chart = Chart(f"{sym_str}_MFI")
                    mfi_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
                    mfi_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
                    mfi_chart.add_series(Series("MFI Value", SeriesType.LINE, "$", Color.PURPLE))
                    self.AddChart(mfi_chart)

                # VOLUME Chart
                if ENABLE_VOL_CHART:
                    volume_chart = Chart(f"{sym_str}_VOLUME")
                    volume_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
                    volume_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
                    volume_chart.add_series(Series("Volume", SeriesType.BAR, "$", Color.BLUE))
                    volume_chart.add_series(Series("SMA Volume * Multiplier", SeriesType.LINE, "$", Color.RED))
                    self.AddChart(volume_chart)

                # Trade Signals Chart
                if ENABLE_TRADE_CHART:
                    trade_chart = Chart(f"{sym_str}_TradeSignals")
                    trade_chart.add_series(Series("Price", SeriesType.LINE, "$", Color.WHITE))
                    trade_chart.add_series(Series("Entry", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
                    trade_chart.add_series(Series("Exit", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
                    trade_chart.add_series(Series("Trailing Stop", SeriesType.SCATTER, "$", Color.ORANGE, ScatterMarkerSymbol.CIRCLE))
                    self.AddChart(trade_chart)

    def OnData(self, data):
        # Process each symbol independently
        for symbol in self.symbols:
            if symbol not in data.Bars:
                continue

            bar = data.Bars[symbol]
            # Plot current price on trade signals chart for this symbol
            if ENABLE_CHARTING and ENABLE_TRADE_CHART:
                self.Plot(f"{symbol.Value}_TradeSignals", "Price", bar.Close)

            if ENABLE_MA:
                self.check_moving_average_crossovers(symbol, bar)
            if ENABLE_STOCH:
                self.check_stochrsi_crossovers(symbol, bar)
            if ENABLE_LBR:
                self.check_lbr_crossovers(symbol, bar)
            if ENABLE_MFI:
                self.check_mfi_crossovers(symbol, bar)
            if ENABLE_VOL:
                self.check_volume_spikes(symbol, bar)

            if not self.IsWarmingUp:
                net_signal = self.calculate_net_signal_value(symbol)
                
                # BUY SIGNAL
                if net_signal >= REQUIRED_ENTRY_SIGNALS:
                    # If currently short, liquidate first
                    if self.Portfolio[symbol].Quantity < 0:
                        self.Liquidate(symbol)
                        # Cancel any existing trailing stop order
                        if self._TrailingStopOrderTicket[symbol] is not None:
                            self._TrailingStopOrderTicket[symbol].cancel("canceled TrailingStopOrder")
                        # Enter a long position at initial allocation
                        self.SetHoldings(symbol, FIRST_TRADE_ALLOCATION)
                        self.Debug(f"Liquidated short position and entered long on {symbol} for Net Signal {net_signal}. Active signals: {self.active_signals}")
                        # Set trailing stop for long position
                        if ENABLE_TRAILING_STOPS:
                            self._TrailingStopOrderTicket[symbol] = self.TrailingStopOrder(symbol, -self.Portfolio[symbol].Quantity, TRAILING_STOP_PERCENT, True)
                    else:
                        # If not invested, go long with initial allocation
                        if not self.Portfolio[symbol].Invested:
                            self.SetHoldings(symbol, FIRST_TRADE_ALLOCATION)
                            self.Debug(f"Entered long trade on {symbol} for Net Signal {net_signal}. Active signals: {self.active_signals}")
                            # Set trailing stop for long position
                            if ENABLE_TRAILING_STOPS:
                                self._TrailingStopOrderTicket[symbol] = self.TrailingStopOrder(symbol, -self.Portfolio[symbol].Quantity, TRAILING_STOP_PERCENT, True)
                        else:
                            # If already long, increase position by additional allocation
                            current_weight = self.Portfolio[symbol].HoldingsValue / self.Portfolio.TotalPortfolioValue
                            new_target = min(current_weight + REPEAT_TRADE_ALLOCATION, 1.0)
                            self.SetHoldings(symbol, new_target)
                            self.Debug(f"Increased long position on {symbol} to {new_target:.2f} for Net Signal {net_signal}. Active signals: {self.active_signals}")
                    
                    # Update trade information
                    if self.current_trades[symbol] is None or self.Portfolio[symbol].Quantity > 0:
                        combo_key = ", ".join(sorted(self.active_signals)) if self.active_signals else "NO_SIGNAL"
                        self.current_trades[symbol] = {
                            "entry_time": self.Time,
                            "entry_price": self.Securities[symbol].Price,
                            "quantity": self.Portfolio[symbol].Quantity,
                            "active_signals": combo_key
                        }
                
                # SELL SIGNAL
                elif net_signal <= -REQUIRED_EXIT_SIGNALS:
                    # If currently long, liquidate first
                    if self.Portfolio[symbol].Quantity > 0:
                        self.Liquidate(symbol)
                        # Cancel any existing trailing stop order
                        if self._TrailingStopOrderTicket[symbol] is not None:
                            self._TrailingStopOrderTicket[symbol].cancel("canceled TrailingStopOrder")
                        # Enter a short position at initial allocation
                        self.SetHoldings(symbol, -FIRST_TRADE_ALLOCATION)
                        self.Debug(f"Liquidated long position and entered short on {symbol} for Net Signal {net_signal}. Active signals: {self.active_signals}")
                        # Set trailing stop for short position
                        if ENABLE_TRAILING_STOPS:
                            self._TrailingStopOrderTicket[symbol] = self.TrailingStopOrder(symbol, -self.Portfolio[symbol].Quantity, TRAILING_STOP_PERCENT, True)
                    else:
                        # If not invested, go short with initial allocation
                        if not self.Portfolio[symbol].Invested:
                            self.SetHoldings(symbol, -FIRST_TRADE_ALLOCATION)
                            self.Debug(f"Entered short trade on {symbol} for Net Signal {net_signal}. Active signals: {self.active_signals}")
                            # Set trailing stop for short position
                            if ENABLE_TRAILING_STOPS:
                                self._TrailingStopOrderTicket[symbol] = self.TrailingStopOrder(symbol, -self.Portfolio[symbol].Quantity, TRAILING_STOP_PERCENT, True)
                        else:
                            # If already short, increase short position by additional allocation
                            current_weight = self.Portfolio[symbol].HoldingsValue / self.Portfolio.TotalPortfolioValue
                            new_target = max(current_weight - REPEAT_TRADE_ALLOCATION, -1.0)
                            self.SetHoldings(symbol, new_target)
                            self.Debug(f"Increased short position on {symbol} to {new_target:.2f} for Net Signal {net_signal}. Active signals: {self.active_signals}")
                    
                    
                    # Update trade information
                    if self.current_trades[symbol] is None or self.Portfolio[symbol].Quantity < 0:
                        combo_key = ", ".join(sorted(self.active_signals)) if self.active_signals else "NO_SIGNAL"
                        self.current_trades[symbol] = {
                            "entry_time": self.Time,
                            "entry_price": self.Securities[symbol].Price,
                            "quantity": self.Portfolio[symbol].Quantity,
                            "active_signals": combo_key
                        }

    def check_moving_average_crossovers(self, symbol, bar):
        # Update rolling windows for MA values
        self.ma9_window[symbol].add(self.short_sma[symbol].Current.Value)
        self.ma20_window[symbol].add(self.long_sma[symbol].Current.Value)

        self.ma9_values[symbol].append(self.short_sma[symbol].Current.Value)
        if ENABLE_CHARTING and ENABLE_MA_CHART:
            self.Plot(f"{symbol.Value}_MA", "9 Period Value", self.short_sma[symbol].Current.Value)
        self.ma20_values[symbol].append(self.long_sma[symbol].Current.Value)
        if ENABLE_CHARTING and ENABLE_MA_CHART:
            self.Plot(f"{symbol.Value}_MA", "20 Period Value", self.long_sma[symbol].Current.Value)

        if self.ma9_window[symbol][0] > self.ma20_window[symbol][0] and self.ma9_window[symbol][1] < self.ma20_window[symbol][1]:
            self.ma_indicator_signals[symbol].append("BUY")
            if ENABLE_CHARTING and ENABLE_MA_CHART:
                self.Plot(f"{symbol.Value}_MA", "Buy Signal", self.short_sma[symbol].Current.Value)
        elif self.ma9_window[symbol][0] < self.ma20_window[symbol][0] and self.ma9_window[symbol][1] > self.ma20_window[symbol][1]:
            self.ma_indicator_signals[symbol].append("SELL")
            if ENABLE_CHARTING and ENABLE_MA_CHART:
                self.Plot(f"{symbol.Value}_MA", "Sell Signal", self.short_sma[symbol].Current.Value)
        else:
            self.ma_indicator_signals[symbol].append(None)

    def check_stochrsi_crossovers(self, symbol, bar):
        self.stoch_k_window[symbol].add(self.srsi[symbol].K.Current.Value)
        self.stoch_d_window[symbol].add(self.srsi[symbol].D.Current.Value)

        self.stoch_k_values[symbol].append(self.srsi[symbol].K.Current.Value)
        if ENABLE_CHARTING and ENABLE_STOCH_CHART:
            self.Plot(f"{symbol.Value}_STOCHRSI", "K Value", self.srsi[symbol].K.Current.Value)
        self.stoch_d_values[symbol].append(self.srsi[symbol].D.Current.Value)
        if ENABLE_CHARTING and ENABLE_STOCH_CHART:
            self.Plot(f"{symbol.Value}_STOCHRSI", "D Value", self.srsi[symbol].D.Current.Value)

        k_buy = k_sell = d_buy = d_sell = False

        if self.stoch_k_window[symbol][0] > 20 and self.stoch_k_window[symbol][1] < 20:
            self.stoch_k_cross_window[symbol].add(True)
            k_buy = True
        elif self.stoch_k_window[symbol][0] < 80 and self.stoch_k_window[symbol][1] > 80:
            self.stoch_k_cross_window[symbol].add(True)
            k_sell = True
        else:
            self.stoch_k_cross_window[symbol].add(False)

        if self.stoch_d_window[symbol][0] > 20 and self.stoch_d_window[symbol][1] < 20:
            self.stoch_d_cross_window[symbol].add(True)
            d_buy = True
        elif self.stoch_d_window[symbol][0] < 80 and self.stoch_d_window[symbol][1] > 80:
            self.stoch_d_cross_window[symbol].add(True)
            d_sell = True
        else:
            self.stoch_d_cross_window[symbol].add(False)

        if d_buy and True in self.stoch_k_cross_window[symbol]:
            self.stoch_indicator_signals[symbol].append("BUY")
            if ENABLE_CHARTING and ENABLE_STOCH_CHART:
                self.Plot(f"{symbol.Value}_STOCHRSI", "Buy Signal", self.srsi[symbol].D.Current.Value)
        elif d_sell and True in self.stoch_k_cross_window[symbol]:
            self.stoch_indicator_signals[symbol].append("SELL")
            if ENABLE_CHARTING and ENABLE_STOCH_CHART:
                self.Plot(f"{symbol.Value}_STOCHRSI", "Sell Signal", self.srsi[symbol].D.Current.Value)
        elif k_buy and True in self.stoch_k_cross_window[symbol]:
            self.stoch_indicator_signals[symbol].append("BUY")
            if ENABLE_CHARTING and ENABLE_STOCH_CHART:
                self.Plot(f"{symbol.Value}_STOCHRSI", "Buy Signal", self.srsi[symbol].K.Current.Value)
        elif k_sell and True in self.stoch_k_cross_window[symbol]:
            self.stoch_indicator_signals[symbol].append("SELL")
            if ENABLE_CHARTING and ENABLE_STOCH_CHART:
                self.Plot(f"{symbol.Value}_STOCHRSI", "Sell Signal", self.srsi[symbol].K.Current.Value)
        else:
            self.stoch_indicator_signals[symbol].append(None)

    def check_lbr_crossovers(self, symbol, bar):
        self.lbr_window[symbol].add(self.macd[symbol].Current.Value)
        self.lbr_signal_window[symbol].add(self.macd[symbol].Signal.Current.Value)

        self.lbr_values[symbol].append(self.macd[symbol].Current.Value)
        if ENABLE_CHARTING and ENABLE_LBR_CHART:
            self.Plot(f"{symbol.Value}_LBROSC", "MACD Value", self.macd[symbol].Current.Value)
        self.lbr_signal_values[symbol].append(self.macd[symbol].Signal.Current.Value)
        if ENABLE_CHARTING and ENABLE_LBR_CHART:
            self.Plot(f"{symbol.Value}_LBROSC", "MACD Signal Value", self.macd[symbol].Signal.Current.Value)

        if self.lbr_window[symbol][0] > self.lbr_signal_window[symbol][0] and self.lbr_window[symbol][1] < self.lbr_signal_window[symbol][1]:
            self.lbr_indicator_signals[symbol].append("BUY")
            if ENABLE_CHARTING and ENABLE_LBR_CHART:
                self.Plot(f"{symbol.Value}_LBROSC", "Buy Signal", self.macd[symbol].Signal.Current.Value)
        elif self.lbr_window[symbol][0] < self.lbr_signal_window[symbol][0] and self.lbr_window[symbol][1] > self.lbr_signal_window[symbol][1]:
            self.lbr_indicator_signals[symbol].append("SELL")
            if ENABLE_CHARTING and ENABLE_LBR_CHART:
                self.Plot(f"{symbol.Value}_LBROSC", "Sell Signal", self.macd[symbol].Signal.Current.Value)
        else:
            self.lbr_indicator_signals[symbol].append(None)

    def check_mfi_crossovers(self, symbol, bar):
        self.mfi_window[symbol].add(self.mfi[symbol].Current.Value)
        self.mfi_values[symbol].append(self.mfi[symbol].Current.Value)
        if ENABLE_CHARTING and ENABLE_MFI_CHART:
            self.Plot(f"{symbol.Value}_MFI", "MFI Value", self.mfi[symbol].Current.Value)

        if self.mfi_window[symbol][0] > 20 and self.mfi_window[symbol][1] < 20:
            self.mfi_indicator_signals[symbol].append("BUY")
            if ENABLE_CHARTING and ENABLE_MFI_CHART:
                self.Plot(f"{symbol.Value}_MFI", "Buy Signal", self.mfi[symbol].Current.Value)
        elif self.mfi_window[symbol][0] < 80 and self.mfi_window[symbol][1] > 80:
            self.mfi_indicator_signals[symbol].append("SELL")
            if ENABLE_CHARTING and ENABLE_MFI_CHART:
                self.Plot(f"{symbol.Value}_MFI", "Sell Signal", self.mfi[symbol].Current.Value)
        else:
            self.mfi_indicator_signals[symbol].append(None)

    def check_volume_spikes(self, symbol, bar):
        if bar is None:
            return

        if self.previous_close[symbol] is None:
            self.previous_close[symbol] = bar.Close
            return

        price_change = bar.Close - self.previous_close[symbol]

        self.vol_values[symbol].append(bar.Volume)
        if ENABLE_CHARTING and ENABLE_VOL_CHART:
            self.Plot(f"{symbol.Value}_VOLUME", "Volume", bar.Volume)

        self.vol_sma_values[symbol].append(self.sma_vol[symbol].Current.Value)
        sma_vol_multiplier = self.sma_vol[symbol].Current.Value * VOLUME_SPIKE_MULTIPLIER
        if ENABLE_CHARTING and ENABLE_VOL_CHART:
            self.Plot(f"{symbol.Value}_VOLUME", "SMA Volume * Multiplier", sma_vol_multiplier)

        if bar.Volume > VOLUME_SPIKE_MULTIPLIER * self.sma_vol[symbol].Current.Value:
            if price_change > 0:
                self.vol_indicator_signals[symbol].append("BUY")
                if ENABLE_CHARTING and ENABLE_VOL_CHART:
                    self.Plot(f"{symbol.Value}_VOLUME", "Buy Signal", bar.Volume)
            elif price_change < 0:
                self.vol_indicator_signals[symbol].append("SELL")
                if ENABLE_CHARTING and ENABLE_VOL_CHART:
                    self.Plot(f"{symbol.Value}_VOLUME", "Sell Signal", bar.Volume)
        else:
            self.vol_indicator_signals[symbol].append(None)

        self.previous_close[symbol] = bar.Close

    def calculate_net_signal_value(self, symbol):
        net_signal = 0.0
        active_signals = []
        for indicator, signals in self.indicator_signal_lists[symbol].items():
            # Look back TRIGGER_WINDOW signals (most recent last)
            for i in range(TRIGGER_WINDOW):
                signal = signals[-(i+1)]
                if signal == "BUY":
                    net_signal += self.indicator_weights[indicator]
                    active_signals.append(f"{indicator}:BUY")
                    break
                elif signal == "SELL":
                    net_signal -= self.indicator_weights[indicator]
                    active_signals.append(f"{indicator}:SELL")
                    break
        self.active_signals = active_signals
        return net_signal

    def OnOrderEvent(self, orderEvent):
        if orderEvent.Status != OrderStatus.Filled:
            return

        symbol = orderEvent.Symbol
        # First, retrieve the complete order object
        order = self.Transactions.GetOrderById(orderEvent.OrderId)
        
        # Check if this is a trailing stop order that got filled
        is_trailing_stop = order.Type == OrderType.TrailingStop
        
        if orderEvent.Direction == OrderDirection.Buy:
            if self.current_trades[symbol] is None:
                combo_key = ", ".join(sorted(self.active_signals)) if self.active_signals else "NO_SIGNAL"
                self.current_trades[symbol] = {
                    "entry_time": self.Time,
                    "entry_price": orderEvent.FillPrice,
                    "quantity": orderEvent.FillQuantity,
                    "active_signals": combo_key
                }
            
            # Plot the entry point with different marker for trailing stop entries
            if ENABLE_CHARTING and ENABLE_TRADE_CHART:
                if is_trailing_stop:
                    self.Plot(f"{symbol.Value}_TradeSignals", "Trailing Stop", orderEvent.FillPrice)
                    self.Debug(f"Trailing stop buy triggered at {orderEvent.FillPrice} for {symbol}")
                else:
                    self.Plot(f"{symbol.Value}_TradeSignals", "Entry", orderEvent.FillPrice)
                
        elif orderEvent.Direction == OrderDirection.Sell:
            # Plot the exit point with different marker for trailing stop exits
            if ENABLE_CHARTING and ENABLE_TRADE_CHART:
                if is_trailing_stop:
                    self.Plot(f"{symbol.Value}_TradeSignals", "Trailing Stop", orderEvent.FillPrice)
                    self.Debug(f"Trailing stop sell triggered at {orderEvent.FillPrice} for {symbol}")
                else:
                    self.Plot(f"{symbol.Value}_TradeSignals", "Exit", orderEvent.FillPrice)
                
            if self.current_trades[symbol] is not None:
                exit_price = orderEvent.FillPrice
                entry_price = self.current_trades[symbol]["entry_price"]
                quantity = self.current_trades[symbol]["quantity"]
                base_value = entry_price * quantity
                trade_return = 0 if base_value == 0 else ((exit_price * quantity) - base_value) / base_value * 100
                pnl = (exit_price * quantity) - (entry_price * quantity)
                trade_key = self.current_trades[symbol]["active_signals"] if self.current_trades[symbol]["active_signals"] else "NO_SIGNAL"
                
                if trade_key not in self.trade_stats[symbol]:
                    self.trade_stats[symbol][trade_key] = {
                        "count": 0,
                        "wins": 0,
                        "total_return": 0.0,
                        "total_pnl": 0.0,
                        "total_duration": 0.0,
                        "returns": [],
                        "max_return": None,
                        "min_return": None,
                        "trailing_stop_exits": 0
                    }
                
                stats = self.trade_stats[symbol][trade_key]
                stats["count"] += 1
                if trade_return > 0:
                    stats["wins"] += 1
                stats["total_return"] += trade_return
                stats["total_pnl"] += pnl
                duration = (self.Time - self.current_trades[symbol]["entry_time"]).total_seconds() / 3600.0
                stats["total_duration"] += duration
                stats["returns"].append(trade_return)
                
                # Track trailing stop exits
                if is_trailing_stop:
                    stats["trailing_stop_exits"] += 1
                    
                stats["max_return"] = trade_return if stats["max_return"] is None or trade_return > stats["max_return"] else stats["max_return"]
                stats["min_return"] = trade_return if stats["min_return"] is None or trade_return < stats["min_return"] else stats["min_return"]
                
                self.current_trades[symbol] = None

        # Reset trailing stop ticket if this order fill is from our trailing stop
        if is_trailing_stop and symbol in self._TrailingStopOrderTicket:
            if self._TrailingStopOrderTicket[symbol] is not None and self._TrailingStopOrderTicket[symbol].OrderId == orderEvent.OrderId:
                self._TrailingStopOrderTicket[symbol] = None

        self.Debug(f"Order filled for {symbol} at {orderEvent.FillPrice} as a {orderEvent.Direction} order. Order type: {order.Type}")

    def OnEndOfAlgorithm(self):
        # Log final signal counts and trade stats for each symbol
        for symbol in self.symbols:
            for key, signals in self.indicator_signal_lists[symbol].items():
                buy_count = signals.count("BUY")
                sell_count = signals.count("SELL")
                self.Debug(f"{symbol.Value} {key} signals - BUY: {buy_count}, SELL: {sell_count}")
            for combo, stats in self.trade_stats[symbol].items():
                count = stats["count"]
                if count > 0:
                    win_rate = (stats["wins"] / count) * 100
                    avg_return = stats["total_return"] / count
                    avg_duration = stats["total_duration"] / count
                    mean = avg_return
                    variance = sum((r - mean) ** 2 for r in stats["returns"]) / count
                    std_dev = math.sqrt(variance)
                else:
                    win_rate = avg_return = avg_duration = std_dev = 0
                
                # Calculate trailing stop exit percentage if any trailing stop exits occurred
                trailing_stop_exit_pct = 0
                if count > 0 and "trailing_stop_exits" in stats:
                    trailing_stop_exit_pct = (stats["trailing_stop_exits"] / count) * 100
                    
                self.Debug(f"{symbol.Value} Trade Stats for combination [{combo}] - Count: {count}, Win Rate: {win_rate:.2f}%, "
                           f"Avg % Return: {avg_return:.2f}%, Total PnL: {stats['total_pnl']:.2f}, "
                           f"Avg Duration (hrs): {avg_duration:.2f}, Max Return: {stats['max_return']}, "
                           f"Min Return: {stats['min_return']}, Std Dev: {std_dev:.2f}, "
                           f"Trailing Stop Exits: {stats.get('trailing_stop_exits', 0)} ({trailing_stop_exit_pct:.2f}%)")
