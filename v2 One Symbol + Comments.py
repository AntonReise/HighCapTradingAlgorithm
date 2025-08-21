from AlgorithmImports import *
import math

class SignalMode:
    WEIGHTED = "WEIGHTED"
    COUNT = "COUNT"
    
# Global Parameters
SYMBOLS = ["AAPL"]
START_DATE = "2015-01-01"
END_DATE = "2025-08-01"
INITIAL_CASH = 1000000
TRIGGER_WINDOW = 1
SIGNAL_CALCULATION_MODE = SignalMode.COUNT
WEIGHTED_THRESHOLD_FACTOR = 1.0   # kept for completeness (ignored in COUNT mode)
REQUIRED_ENTRY_SIGNALS = 2
REQUIRED_EXIT_SIGNALS = 2
FIRST_TRADE_ALLOCATION = 0.25
REPEAT_TRADE_ALLOCATION = 0.0
MAX_ALLOCATION_PER_SYMBOL = 1.0 # For single symbol, this can be 1.0 to allow full portfolio usage

# Trailing Stop Configuration
ENABLE_TRAILING_STOPS = True  # Set to False to disable trailing stops
TRAILING_STOP_PERCENT = 0.15  # 15% trailing stop

# Set these to False if you want to disable an indicator
ENABLE_MA = True
ENABLE_STOCH = False
ENABLE_LBR = True # MACD
ENABLE_MFI = False
ENABLE_VOL = False

# Custom Indicator Signal Weights
MA_WEIGHT = 1.0
STOCH_WEIGHT = 1.0
LBR_WEIGHT = 1.0
MFI_WEIGHT = 1.0
VOL_WEIGHT = 1.0

# Indicator Parameters
# Moving Average
MA_FAST_PERIOD = 50
MA_SLOW_PERIOD = 200

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
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# Volume Spikes
VOLUME_SPIKE_MULTIPLIER = 2.0
VOLUME_LOOKBACK = 35

# Turn charting on/off
ENABLE_CHARTING = True
# Individual charts
ENABLE_MA_CHART = True
ENABLE_STOCH_CHART = False
ENABLE_LBR_CHART = True
ENABLE_MFI_CHART = False
ENABLE_VOL_CHART = False
ENABLE_TRADE_CHART = True

SERIES_BUY_SIGNAL = "Buy Signal"
SERIES_SELL_SIGNAL = "Sell Signal"
SERIES_TRAILING_STOP = "Trailing Stop"

class HighCapMultiIndicatorStrategy(QCAlgorithm):
    def Initialize(self):
        # Set dates and cash
        start_year, start_month, start_day = map(int, START_DATE.split("-"))
        end_year, end_month, end_day = map(int, END_DATE.split("-"))
        self.SetStartDate(start_year, start_month, start_day)
        self.SetEndDate(end_year, end_month, end_day)
        self.SetCash(INITIAL_CASH)
        self.resolution = Resolution.Daily  # Daily resolution
        
        # Set brokerage model to ensure trailing stop orders are supported
        self.SetBrokerageModel(BrokerageName.QuantConnectBrokerage)
        
        self.symbols = []
        for ticker in SYMBOLS:
            symbol = self.AddEquity(ticker, self.resolution).Symbol
            self.symbols.append(symbol)

        self.SetWarmUp(50, self.resolution)

        # Initialize Indicators
        self.short_sma_indicators = {}
        self.long_sma_indicators = {}
        self.srsi_indicators = {}
        self.macd_indicators = {}
        self.mfi_indicators = {}
        self.sma_vol_indicators = {}

        for symbol in self.symbols:
            if ENABLE_MA:
                self.short_sma_indicators[symbol] = self.SMA(symbol, MA_FAST_PERIOD, self.resolution)
                self.long_sma_indicators[symbol] = self.SMA(symbol, MA_SLOW_PERIOD, self.resolution)
            if ENABLE_STOCH:
                self.srsi_indicators[symbol] = self.SRSI(symbol, STOCH_PERIOD, STOCH_PERIOD, STOCH_SMOOTH_K, STOCH_SMOOTH_D, MovingAverageType.Simple, self.resolution)
            if ENABLE_LBR:
                self.macd_indicators[symbol] = self.MACD(symbol, MACD_FAST, MACD_SLOW, MACD_SIGNAL, MovingAverageType.Simple, self.resolution)
            if ENABLE_MFI:
                self.mfi_indicators[symbol] = self.MFI(symbol, MFI_PERIOD, self.resolution)
            if ENABLE_VOL:
                self.sma_vol_indicators[symbol] = self.SMA(symbol, VOLUME_LOOKBACK, self.resolution, Field.Volume)

        # Initialize Indicator Signal Lists
        self.ma_indicator_signals = {}
        self.stoch_indicator_signals = {}
        self.lbr_indicator_signals = {}
        self.mfi_indicator_signals = {}
        self.vol_indicator_signals = {}

        # Initialize Indicator Values Lists
        self.ma9_values = {}
        self.ma20_values = {}
        self.stoch_k_values = {}
        self.stoch_d_values = {}
        self.lbr_values = {}
        self.lbr_signal_values = {}
        self.mfi_values = {}
        self.vol_values = {}
        self.vol_sma_values = {}

        # Create Rolling Windows for Crossover Detection
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
            if ENABLE_MA: self.ma_indicator_signals[symbol] = [None] * TRIGGER_WINDOW
            if ENABLE_STOCH: self.stoch_indicator_signals[symbol] = [None] * TRIGGER_WINDOW
            if ENABLE_LBR: self.lbr_indicator_signals[symbol] = [None] * TRIGGER_WINDOW
            if ENABLE_MFI: self.mfi_indicator_signals[symbol] = [None] * TRIGGER_WINDOW
            if ENABLE_VOL: self.vol_indicator_signals[symbol] = [None] * TRIGGER_WINDOW

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

        # Build the dictionary of active indicator signal lists
        self.indicator_signal_lists = {}
        for symbol in self.symbols:
            self.indicator_signal_lists[symbol] = {}
            if ENABLE_MA: self.indicator_signal_lists[symbol]["MA"] = self.ma_indicator_signals[symbol]
            if ENABLE_STOCH: self.indicator_signal_lists[symbol]["STOCH"] = self.stoch_indicator_signals[symbol]
            if ENABLE_LBR: self.indicator_signal_lists[symbol]["LBR"] = self.lbr_indicator_signals[symbol]
            if ENABLE_MFI: self.indicator_signal_lists[symbol]["MFI"] = self.mfi_indicator_signals[symbol]
            if ENABLE_VOL: self.indicator_signal_lists[symbol]["VOL"] = self.vol_indicator_signals[symbol]

        # Create dictionary for indicator weights
        self.indicator_weights = {}
        if ENABLE_MA: self.indicator_weights["MA"] = MA_WEIGHT
        if ENABLE_STOCH: self.indicator_weights["STOCH"] = STOCH_WEIGHT
        if ENABLE_LBR: self.indicator_weights["LBR"] = LBR_WEIGHT
        if ENABLE_MFI: self.indicator_weights["MFI"] = MFI_WEIGHT
        if ENABLE_VOL: self.indicator_weights["VOL"] = VOL_WEIGHT

        self.trade_stats = {symbol: {} for symbol in self.symbols}
        self.current_trades = dict.fromkeys(self.symbols)
        self._TrailingStopOrderTicket = {symbol: None for symbol in self.symbols}

        # Charting
        for symbol in self.symbols:
            sym_str = symbol.Value
            if ENABLE_CHARTING:
                if ENABLE_MA_CHART:
                    ma_chart = Chart(f"{sym_str}_MA")
                    ma_chart.add_series(Series(SERIES_BUY_SIGNAL, SeriesType.Scatter, "$", Color.Green, ScatterMarkerSymbol.Triangle))
                    ma_chart.add_series(Series(SERIES_SELL_SIGNAL, SeriesType.Scatter, "$", Color.Red, ScatterMarkerSymbol.TriangleDown))
                    ma_chart.add_series(Series("Fast MA", SeriesType.Line, "$", Color.Orange))
                    ma_chart.add_series(Series("Slow MA", SeriesType.Line, "$", Color.Blue))
                    self.AddChart(ma_chart)

                if ENABLE_STOCH_CHART:
                    stochrsi_chart = Chart(f"{sym_str}_STOCHRSI")
                    stochrsi_chart.add_series(Series(SERIES_BUY_SIGNAL, SeriesType.Scatter, "$", Color.Green, ScatterMarkerSymbol.Triangle))
                    stochrsi_chart.add_series(Series(SERIES_SELL_SIGNAL, SeriesType.Scatter, "$", Color.Red, ScatterMarkerSymbol.TriangleDown))
                    stochrsi_chart.add_series(Series("K Value", SeriesType.Line, "$", Color.Blue))
                    stochrsi_chart.add_series(Series("D Value", SeriesType.Line, "$", Color.Orange))
                    self.AddChart(stochrsi_chart)

                if ENABLE_LBR_CHART:
                    lbrosc_chart = Chart(f"{sym_str}_LBROSC")
                    lbrosc_chart.add_series(Series(SERIES_BUY_SIGNAL, SeriesType.Scatter, "$", Color.Green, ScatterMarkerSymbol.Triangle))
                    lbrosc_chart.add_series(Series(SERIES_SELL_SIGNAL, SeriesType.Scatter, "$", Color.Red, ScatterMarkerSymbol.TriangleDown))
                    lbrosc_chart.add_series(Series("MACD Value", SeriesType.Line, "$", Color.Blue))
                    lbrosc_chart.add_series(Series("MACD Signal Value", SeriesType.Line, "$", Color.Orange))
                    self.AddChart(lbrosc_chart)

                if ENABLE_MFI_CHART:
                    mfi_chart = Chart(f"{sym_str}_MFI")
                    mfi_chart.add_series(Series(SERIES_BUY_SIGNAL, SeriesType.Scatter, "$", Color.Purple, ScatterMarkerSymbol.Triangle))
                    mfi_chart.add_series(Series(SERIES_SELL_SIGNAL, SeriesType.Scatter, "$", Color.Red, ScatterMarkerSymbol.TriangleDown))
                    mfi_chart.add_series(Series("MFI Value", SeriesType.Line, "$", Color.Purple))
                    self.AddChart(mfi_chart)

                if ENABLE_VOL_CHART:
                    volume_chart = Chart(f"{sym_str}_VOLUME")
                    volume_chart.add_series(Series(SERIES_BUY_SIGNAL, SeriesType.Scatter, "$", Color.Green, ScatterMarkerSymbol.Triangle))
                    volume_chart.add_series(Series(SERIES_SELL_SIGNAL, SeriesType.Scatter, "$", Color.Red, ScatterMarkerSymbol.TriangleDown))
                    volume_chart.add_series(Series("Volume", SeriesType.Bar, "$", Color.Blue))
                    volume_chart.add_series(Series("SMA Volume * Multiplier", SeriesType.Line, "$", Color.Red))
                    self.AddChart(volume_chart)

                if ENABLE_TRADE_CHART:
                    trade_chart = Chart(f"{sym_str}_TradeSignals")
                    trade_chart.add_series(Series("Price", SeriesType.Line, "$", Color.White))
                    trade_chart.add_series(Series("Entry", SeriesType.Scatter, "$", Color.Green, ScatterMarkerSymbol.Triangle))
                    trade_chart.add_series(Series("Exit", SeriesType.Scatter, "$", Color.Red, ScatterMarkerSymbol.TriangleDown))
                    trade_chart.add_series(Series(SERIES_TRAILING_STOP, SeriesType.Scatter, "$", Color.Orange, ScatterMarkerSymbol.Circle))
                    self.AddChart(trade_chart)

    def OnData(self, data):
        for symbol in self.symbols:
            if symbol not in data.Bars:
                continue
                
            bar = data.Bars[symbol]
            if ENABLE_CHARTING and ENABLE_TRADE_CHART:
                self.Plot(f"{symbol.Value}_TradeSignals", "Price", bar.Close)

            # Update indicator lists
            if ENABLE_MA: self.check_moving_average_crossovers(symbol, bar)
            if ENABLE_STOCH: self.check_stochrsi_crossovers(symbol, bar)
            if ENABLE_LBR: self.check_lbr_crossovers(symbol, bar)
            if ENABLE_MFI: self.check_mfi_crossovers(symbol, bar)
            if ENABLE_VOL: self.check_volume_spikes(symbol, bar)

            if not self.IsWarmingUp:
                net_signal = self.calculate_net_signal_value(symbol)
                
                if SIGNAL_CALCULATION_MODE == SignalMode.WEIGHTED:
                    entry_threshold = WEIGHTED_THRESHOLD_FACTOR
                    exit_threshold = -WEIGHTED_THRESHOLD_FACTOR
                else: # COUNT
                    entry_threshold = REQUIRED_ENTRY_SIGNALS
                    exit_threshold = -REQUIRED_EXIT_SIGNALS
                
                # BUY SIGNAL
                if net_signal >= entry_threshold:
                    # If currently short, liquidate first
                    if self.Portfolio[symbol].Quantity < 0:
                        self.Liquidate(symbol)
                        if self._TrailingStopOrderTicket[symbol] is not None:
                            self._TrailingStopOrderTicket[symbol].Cancel("Canceled TrailingStopOrder")
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
                            new_target = min(current_weight + REPEAT_TRADE_ALLOCATION, MAX_ALLOCATION_PER_SYMBOL)
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
                elif net_signal <= exit_threshold:
                    # If currently long, liquidate first
                    if self.Portfolio[symbol].Quantity > 0:
                        self.Liquidate(symbol)
                        if self._TrailingStopOrderTicket[symbol] is not None:
                            self._TrailingStopOrderTicket[symbol].Cancel("Canceled TrailingStopOrder")
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
                            new_target = max(current_weight - REPEAT_TRADE_ALLOCATION, -MAX_ALLOCATION_PER_SYMBOL)
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
        short_sma = self.short_sma_indicators[symbol].Current.Value
        long_sma = self.long_sma_indicators[symbol].Current.Value
        self.ma9_window[symbol].add(short_sma)
        self.ma20_window[symbol].add(long_sma)

        self.ma9_values[symbol].append(short_sma)
        if ENABLE_CHARTING and ENABLE_MA_CHART:
            self.Plot(f"{symbol.Value}_MA", "Fast MA", short_sma)
        self.ma20_values[symbol].append(long_sma)
        if ENABLE_CHARTING and ENABLE_MA_CHART:
            self.Plot(f"{symbol.Value}_MA", "Slow MA", long_sma)

        signal = None
        if self.ma9_window[symbol][0] > self.ma20_window[symbol][0] and self.ma9_window[symbol][1] < self.ma20_window[symbol][1]:
            signal = "BUY"
        elif self.ma9_window[symbol][0] < self.ma20_window[symbol][0] and self.ma9_window[symbol][1] > self.ma20_window[symbol][1]:
            signal = "SELL"
        
        self.ma_indicator_signals[symbol].append(signal)
        if signal and ENABLE_CHARTING and ENABLE_MA_CHART:
            self.Plot(f"{symbol.Value}_MA", f"{signal.capitalize()} Signal", short_sma)

    def check_stochrsi_crossovers(self, symbol, bar):
        self.stoch_k_window[symbol].add(self.srsi_indicators[symbol].K.Current.Value)
        self.stoch_d_window[symbol].add(self.srsi_indicators[symbol].D.Current.Value)
        
        self.stoch_k_values[symbol].append(self.srsi_indicators[symbol].K.Current.Value)
        if ENABLE_CHARTING and ENABLE_STOCH_CHART:
            self.Plot(f"{symbol.Value}_STOCHRSI", "K Value", self.srsi_indicators[symbol].K.Current.Value)
        self.stoch_d_values[symbol].append(self.srsi_indicators[symbol].D.Current.Value)
        if ENABLE_CHARTING and ENABLE_STOCH_CHART:
            self.Plot(f"{symbol.Value}_STOCHRSI", "D Value", self.srsi_indicators[symbol].D.Current.Value)

        # Initialize local flags
        k_buy = k_sell = d_buy = d_sell = False

        if self.stoch_k_window[symbol][0] > STOCH_LOWER and self.stoch_k_window[symbol][1] < STOCH_LOWER:
            self.stoch_k_cross_window[symbol].add(True)
            k_buy = True
        elif self.stoch_k_window[symbol][0] < STOCH_UPPER and self.stoch_k_window[symbol][1] > STOCH_UPPER:
            self.stoch_k_cross_window[symbol].add(True)
            k_sell = True
        else:
            self.stoch_k_cross_window[symbol].add(False)
        
        if self.stoch_d_window[symbol][0] > STOCH_LOWER and self.stoch_d_window[symbol][1] < STOCH_LOWER:
            self.stoch_d_cross_window[symbol].add(True)
            d_buy = True
        elif self.stoch_d_window[symbol][0] < STOCH_UPPER and self.stoch_d_window[symbol][1] > STOCH_UPPER:
            self.stoch_d_cross_window[symbol].add(True)
            d_sell = True
        else:
            self.stoch_d_cross_window[symbol].add(False)
        
        signal = None
        plot_val = None
        if d_buy and True in self.stoch_k_cross_window[symbol]:
            signal = "BUY"
            plot_val = self.srsi_indicators[symbol].D.Current.Value
        elif d_sell and True in self.stoch_k_cross_window[symbol]:
            signal = "SELL"
            plot_val = self.srsi_indicators[symbol].D.Current.Value
        elif k_buy and True in self.stoch_k_cross_window[symbol]:
            signal = "BUY"
            plot_val = self.srsi_indicators[symbol].K.Current.Value
        elif k_sell and True in self.stoch_k_cross_window[symbol]:
            signal = "SELL"
            plot_val = self.srsi_indicators[symbol].K.Current.Value

        self.stoch_indicator_signals[symbol].append(signal)
        if signal and ENABLE_CHARTING and ENABLE_STOCH_CHART:
            self.Plot(f"{symbol.Value}_STOCHRSI", f"{signal.capitalize()} Signal", plot_val)

    def check_lbr_crossovers(self, symbol, bar):
        macd_val = self.macd_indicators[symbol].Current.Value
        signal_val = self.macd_indicators[symbol].Signal.Current.Value
        self.lbr_window[symbol].add(macd_val)
        self.lbr_signal_window[symbol].add(signal_val) 

        self.lbr_values[symbol].append(macd_val)
        if ENABLE_CHARTING and ENABLE_LBR_CHART:
            self.Plot(f"{symbol.Value}_LBROSC", "MACD Value", macd_val)
        self.lbr_signal_values[symbol].append(signal_val)
        if ENABLE_CHARTING and ENABLE_LBR_CHART:
            self.Plot(f"{symbol.Value}_LBROSC", "MACD Signal Value", signal_val)

        signal = None
        plot_val = None
        if self.lbr_window[symbol][0] > self.lbr_signal_window[symbol][0] and self.lbr_window[symbol][1] < self.lbr_signal_window[symbol][1]:
            signal = "BUY"
            plot_val = signal_val
        elif self.lbr_window[symbol][0] < self.lbr_signal_window[symbol][0] and self.lbr_window[symbol][1] > self.lbr_signal_window[symbol][1]:
            signal = "SELL"
            plot_val = macd_val
        
        self.lbr_indicator_signals[symbol].append(signal)
        if signal and ENABLE_CHARTING and ENABLE_LBR_CHART:
            self.Plot(f"{symbol.Value}_LBROSC", f"{signal.capitalize()} Signal", plot_val)

    def check_mfi_crossovers(self, symbol, bar):
        mfi_val = self.mfi_indicators[symbol].Current.Value
        self.mfi_window[symbol].add(mfi_val)
        self.mfi_values[symbol].append(mfi_val)
        if ENABLE_CHARTING and ENABLE_MFI_CHART:
            self.Plot(f"{symbol.Value}_MFI", "MFI Value", mfi_val)

        signal = None
        if self.mfi_window[symbol][0] > MFI_LOWER and self.mfi_window[symbol][1] < MFI_LOWER:
            signal = "BUY"
        elif self.mfi_window[symbol][0] < MFI_UPPER and self.mfi_window[symbol][1] > MFI_UPPER:
            signal = "SELL"

        self.mfi_indicator_signals[symbol].append(signal)
        if signal and ENABLE_CHARTING and ENABLE_MFI_CHART:
            self.Plot(f"{symbol.Value}_MFI", f"{signal.capitalize()} Signal", mfi_val)

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
        
        self.vol_sma_values[symbol].append(self.sma_vol_indicators[symbol].Current.Value)
        sma_vol_multiplier = self.sma_vol_indicators[symbol].Current.Value * VOLUME_SPIKE_MULTIPLIER
        if ENABLE_CHARTING and ENABLE_VOL_CHART:
            self.Plot(f"{symbol.Value}_VOLUME", "SMA Volume * Multiplier", sma_vol_multiplier)

        signal = None
        if bar.Volume > VOLUME_SPIKE_MULTIPLIER * self.sma_vol_indicators[symbol].Current.Value:
            if price_change > 0:
                signal = "BUY"
            elif price_change < 0:
                signal = "SELL"
        
        self.vol_indicator_signals[symbol].append(signal)
        if signal and ENABLE_CHARTING and ENABLE_VOL_CHART:
            self.Plot(f"{symbol.Value}_VOLUME", f"{signal.capitalize()} Signal", bar.Volume)

        self.previous_close[symbol] = bar.Close
        
    def calculate_net_signal_value(self, symbol):
        net_signal = 0.0
        active_signals = []
        for indicator, signals in self.indicator_signal_lists[symbol].items():
            # Look back TRIGGER_WINDOW signals (most recent last)
            for i in range(TRIGGER_WINDOW):
                signal = signals[-(i+1)]
                if signal == "BUY":
                    if SIGNAL_CALCULATION_MODE == SignalMode.WEIGHTED:
                        net_signal += self.indicator_weights[indicator]
                    else: # COUNT
                        net_signal += 1
                    active_signals.append(f"{indicator}:BUY")
                    break
                elif signal == "SELL":
                    if SIGNAL_CALCULATION_MODE == SignalMode.WEIGHTED:
                        net_signal -= self.indicator_weights[indicator]
                    else: # COUNT
                        net_signal -= 1
                    active_signals.append(f"{indicator}:SELL")
                    break
        self.active_signals = active_signals
        return net_signal

    def OnOrderEvent(self, order_event):
        if order_event.Status != OrderStatus.Filled:
            return
            
        symbol = order_event.Symbol
        order = self.Transactions.GetOrderById(order_event.OrderId)
        is_trailing_stop = order.Type == OrderType.TrailingStop
        
        if order_event.Direction == OrderDirection.Buy:
            # Only record trade entry if not already in an open trade
            if self.current_trades[symbol] is None:
                combo_key = ", ".join(sorted(self.active_signals)) if self.active_signals else "NO_SIGNAL"
                self.current_trades[symbol] = {
                    "entry_time": self.Time,
                    "entry_price": order_event.FillPrice,
                    "quantity": order_event.FillQuantity,
                    "active_signals": combo_key
                }
            
            if ENABLE_CHARTING and ENABLE_TRADE_CHART:
                if is_trailing_stop:
                    self.Plot(f"{symbol.Value}_TradeSignals", SERIES_TRAILING_STOP, order_event.FillPrice)
                    self.Debug(f"Trailing stop buy triggered at {order_event.FillPrice} for {symbol}")
                else:
                    self.Plot(f"{symbol.Value}_TradeSignals", "Entry", order_event.FillPrice)
                
        elif order_event.Direction == OrderDirection.Sell:
            if ENABLE_CHARTING and ENABLE_TRADE_CHART:
                if is_trailing_stop:
                    self.Plot(f"{symbol.Value}_TradeSignals", SERIES_TRAILING_STOP, order_event.FillPrice)
                    self.Debug(f"Trailing stop sell triggered at {order_event.FillPrice} for {symbol}")
                else:
                    self.Plot(f"{symbol.Value}_TradeSignals", "Exit", order_event.FillPrice)
                
            # Only if a trade was recorded as open, record the exit and update stats
            if self.current_trades[symbol] is not None:
                exit_price = order_event.FillPrice
                entry_price = self.current_trades[symbol]["entry_price"]
                quantity = self.current_trades[symbol]["quantity"]
                # Calculate percentage return
                base_value = entry_price * quantity
                trade_return = 0 if base_value == 0 else ((exit_price * quantity) - base_value) / base_value * 100
                pnl = (exit_price * quantity) - (entry_price * quantity)
                duration = (self.Time - self.current_trades[symbol]["entry_time"]).total_seconds() / 3600.0
                trade_key = self.current_trades[symbol]["active_signals"] if self.current_trades[symbol]["active_signals"] else "NO_SIGNAL"

                if trade_key not in self.trade_stats[symbol]:
                    self.trade_stats[symbol][trade_key] = {
                        "count": 0, "wins": 0, "total_return": 0.0, "total_pnl": 0.0,
                        "total_duration": 0.0, "returns": [], "max_return": None,
                        "min_return": None, "trailing_stop_exits": 0
                    }
                stats = self.trade_stats[symbol][trade_key]
                stats["count"] += 1
                if trade_return > 0: stats["wins"] += 1
                stats["total_return"] += trade_return
                stats["total_pnl"] += pnl
                stats["total_duration"] += duration
                stats["returns"].append(trade_return)
                if is_trailing_stop: stats["trailing_stop_exits"] += 1
                if stats["max_return"] is None or trade_return > stats["max_return"]: stats["max_return"] = trade_return
                if stats["min_return"] is None or trade_return < stats["min_return"]: stats["min_return"] = trade_return
                
                # Reset current trade since it has now been closed.
                self.current_trades[symbol] = None

        # Reset trailing stop ticket if this order fill is from our trailing stop
        if is_trailing_stop and symbol in self._TrailingStopOrderTicket:
            if self._TrailingStopOrderTicket[symbol] is not None and self._TrailingStopOrderTicket[symbol].OrderId == order_event.OrderId:
                self._TrailingStopOrderTicket[symbol] = None

        self.Debug(f"Order filled for {order_event.Symbol} at {order_event.FillPrice} as a {order_event.Direction} order. Order type: {order.Type}")

    def OnEndOfAlgorithm(self):
        for symbol in self.symbols:
            # Log final counts for each indicator's signals
            for key, signal_list in self.indicator_signal_lists[symbol].items():
                buy_count = signal_list.count("BUY")
                sell_count = signal_list.count("SELL")
                self.Debug(f"{symbol.Value} {key} signals - BUY: {buy_count}, SELL: {sell_count}")
            
            for combo, stats in self.trade_stats[symbol].items():
                count = stats["count"]
                if count > 0:
                    win_rate = (stats["wins"] / count) * 100
                    avg_return = stats["total_return"] / count
                    avg_duration = stats["total_duration"] / count
                    # Calculate standard deviation of trade returns
                    mean = avg_return
                    variance = sum((r - mean) ** 2 for r in stats["returns"]) / count
                    std_dev = math.sqrt(variance)
                    
                    # Get trailing stop exit stats if available
                    trailing_exits = stats.get("trailing_stop_exits", 0)
                    trailing_exit_pct = (trailing_exits / count) * 100
                else:
                    win_rate = avg_return = avg_duration = std_dev = trailing_exit_pct = 0
                    trailing_exits = 0
                    
                self.Debug(f"{symbol.Value} Trade Stats for combination [{combo}] - Count: {count}, Win Rate: {win_rate:.2f}%, "
                        f"Avg % Return: {avg_return:.2f}%, Total PnL: {stats['total_pnl']:.2f}, "
                        f"Avg Duration (hrs): {avg_duration:.2f}, Max Return: {stats.get('max_return', 'N/A')}, "
                        f"Min Return: {stats.get('min_return', 'N/A')}, Std Dev: {std_dev:.2f}, "
                        f"Trailing Stop Exits: {trailing_exits} ({trailing_exit_pct:.2f}%)")
