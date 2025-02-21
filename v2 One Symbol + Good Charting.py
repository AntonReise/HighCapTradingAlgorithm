from AlgorithmImports import *
import math

# Global Parameters
SYMBOL = "AAPL"
START_DATE = "2021-01-01"
END_DATE = "2022-01-01"
INITIAL_CASH = 100000
TRIGGER_WINDOW = 5
REQUIRED_ENTRY_SIGNALS = 5
REQUIRED_EXIT_SIGNALS = 4
TRADE_ALLOCATION = 1

# Indicator Parameters
# Moving Averate
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

# Custom Indicator Signal Weights
MA_WEIGHT = 2.0
STOCH_WEIGHT = 1.0
LBR_WEIGHT = 2.0
MFI_WEIGHT = 1.0
VOL_WEIGHT = 1.0

class HighCapMultiIndicatorStrategy(QCAlgorithm):
    def Initialize(self):
        # Set dates and cash
        start_year, start_month, start_day = map(int, START_DATE.split("-"))
        end_year, end_month, end_day = map(int, END_DATE.split("-"))
        self.SetStartDate(start_year, start_month, start_day)
        self.SetEndDate(end_year, end_month, end_day)
        self.SetCash(INITIAL_CASH)
        self.resolution = Resolution.Hour  # Hourly resolution
        # Add symbol and warmup
        self._symbol = self.AddEquity(SYMBOL, self.resolution).Symbol
        self.SetWarmUp(50, self.resolution)

        # Set these to False if you want to disable an indicator
        self.enable_ma = True
        self.enable_stoch = True
        self.enable_lbr = True
        self.enable_mfi = True
        self.enable_vol = True

        # Initialize Indicators
        self.short_sma = self.sma(self._symbol, MA_FAST_PERIOD, self.resolution)
        self.long_sma = self.sma(self._symbol, MA_SLOW_PERIOD, self.resolution)
        self._srsi = self.srsi(self._symbol, STOCH_PERIOD, STOCH_PERIOD, STOCH_SMOOTH_K, STOCH_SMOOTH_D, self.resolution)
        self._macd = self.macd(self._symbol, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
        self._mfi = self.mfi(self._symbol, MFI_PERIOD)
        self._sma_vol = self.sma(self._symbol, VOLUME_LOOKBACK, self.resolution, Field.Volume)

        # Initialize Indicator Signal Lists
        self.ma_indicator_signals = [None] * TRIGGER_WINDOW if self.enable_ma else []
        self.stoch_indicator_signals = [None] * TRIGGER_WINDOW if self.enable_stoch else []
        self.lbr_indicator_signals = [None] * TRIGGER_WINDOW if self.enable_lbr else []
        self.mfi_indicator_signals = [None] * TRIGGER_WINDOW if self.enable_mfi else []
        self.vol_indicator_signals = [None] * TRIGGER_WINDOW if self.enable_vol else []

        # Initialize Indicator Values Lists
        self.ma9_values = [0] * TRIGGER_WINDOW
        self.ma20_values = [0] * TRIGGER_WINDOW
        self.stoch_k_values = [0] * TRIGGER_WINDOW
        self.stoch_d_values = [0] * TRIGGER_WINDOW
        self.lbr_values = [0] * TRIGGER_WINDOW
        self.lbr_signal_values = [0] * TRIGGER_WINDOW
        self.mfi_values = [0] * TRIGGER_WINDOW
        self.vol_values = [0] * TRIGGER_WINDOW
        self.vol_sma_values = [0] * TRIGGER_WINDOW

        # Build the dictionary of active indicator signal lists
        self.indicator_signal_lists = {}
        if self.enable_ma:
            self.indicator_signal_lists["MA"] = self.ma_indicator_signals
        if self.enable_stoch:
            self.indicator_signal_lists["STOCH"] = self.stoch_indicator_signals
        if self.enable_lbr:
            self.indicator_signal_lists["LBR"] = self.lbr_indicator_signals
        if self.enable_mfi:
            self.indicator_signal_lists["MFI"] = self.mfi_indicator_signals
        if self.enable_vol:
            self.indicator_signal_lists["VOL"] = self.vol_indicator_signals

        # Create dictionary for indicator weights
        self.indicator_weights = {}
        if self.enable_ma:
            self.indicator_weights["MA"] = MA_WEIGHT
        if self.enable_stoch:
            self.indicator_weights["STOCH"] = STOCH_WEIGHT
        if self.enable_lbr:
            self.indicator_weights["LBR"] = LBR_WEIGHT
        if self.enable_mfi:
            self.indicator_weights["MFI"] = MFI_WEIGHT
        if self.enable_vol:
            self.indicator_weights["VOL"] = VOL_WEIGHT

        self.trade_stats = {}

        self.current_trade = None

        # Create Rolling Windows for Crossover Detection
        self.ma9_window = RollingWindow[float](2)
        self.ma20_window = RollingWindow[float](2)
        self.stoch_k_window = RollingWindow[float](2)
        self.stoch_d_window = RollingWindow[float](2)
        self.stoch_k_cross_window = RollingWindow[bool](STOCH_LOOKBACK)
        self.stoch_d_cross_window = RollingWindow[bool](STOCH_LOOKBACK)
        self.lbr_window = RollingWindow[float](2)
        self.lbr_signal_window = RollingWindow[float](2)
        self.mfi_window = RollingWindow[float](2)

        self.previous_close = None

        # Charting
        ma_chart = Chart("MA")
        ma_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
        ma_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
        ma_chart.add_series(Series("9 Period Value", SeriesType.LINE, "$", Color.ORANGE))
        ma_chart.add_series(Series("20 Period Value", SeriesType.LINE, "$", Color.BLUE))
        self.AddChart(ma_chart)

        stochrsi_chart = Chart("STOCHRSI")
        stochrsi_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
        stochrsi_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
        stochrsi_chart.add_series(Series("K Value", SeriesType.LINE, "$", Color.BLUE))
        stochrsi_chart.add_series(Series("D Value", SeriesType.LINE, "$", Color.ORANGE))
        self.AddChart(stochrsi_chart)

        lbrosc_chart = Chart("LBROSC")
        lbrosc_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
        lbrosc_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
        lbrosc_chart.add_series(Series("MACD Value", SeriesType.LINE, "$", Color.BLUE))
        lbrosc_chart.add_series(Series("MACD Signal Value", SeriesType.LINE, "$", Color.ORANGE))
        self.AddChart(lbrosc_chart)

        mfi_chart = Chart("MFI")
        mfi_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
        mfi_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
        mfi_chart.add_series(Series("MFI Value", SeriesType.LINE, "$", Color.PURPLE))
        self.AddChart(mfi_chart)

        volume_chart = Chart("VOLUME")
        volume_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
        volume_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
        volume_chart.add_series(Series("Volume", SeriesType.BAR, "$", Color.BLUE))
        volume_chart.add_series(Series("SMA Volume * Multiplier", SeriesType.LINE, "$", Color.RED))
        self.AddChart(volume_chart)

        trade_chart = Chart("TradeSignals")
        trade_chart.add_series(Series("Price", SeriesType.LINE, "$", Color.WHITE))
        trade_chart.add_series(Series("Entry", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
        trade_chart.add_series(Series("Exit", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
        self.AddChart(trade_chart)

    def OnData(self, data):
        # Update indicator lists
        if self.enable_ma:
            self.check_moving_average_crossovers()
        if self.enable_stoch:
            self.check_stochrsi_crossovers()
        if self.enable_lbr:
            self.check_lbr_crossovers()
        if self.enable_mfi:
            self.check_mfi_crossovers()
        if self.enable_vol:
            self.check_volume_spikes(data)

        if self._symbol in data.Bars:
            bar = data.Bars[self._symbol]
            self.Plot("TradeSignals", "Price", bar.Close)

        invested = self.Portfolio[self._symbol].Invested

        if not self.IsWarmingUp:
            net_signal = self.calculate_net_signal_value()
            if not invested and net_signal >= REQUIRED_ENTRY_SIGNALS:
                self.SetHoldings(self._symbol, TRADE_ALLOCATION)
                self.Debug(f"Entered trade on {self._symbol} for Net Signal {net_signal}. Active signals: {self.active_signals}")
                if self.current_trade is None:
                    combo_key = ", ".join(sorted(self.active_signals)) if self.active_signals else "NO_SIGNAL"
                    self.current_trade = {
                        "entry_time": self.Time,
                        "entry_price": self.Securities[self._symbol].Price,
                        "quantity": self.Portfolio[self._symbol].Quantity,
                        "active_signals": combo_key
                    }
            elif invested and net_signal <= -REQUIRED_EXIT_SIGNALS:
                self.Liquidate(self._symbol)
                self.Debug(f"Liquidated {self._symbol} for Net Signal {net_signal}. Active signals: {self.active_signals}")

    def check_moving_average_crossovers(self):
        self.ma9_window.add(self.short_sma.Current.Value)
        self.ma20_window.add(self.long_sma.Current.Value)

        self.ma9_values.append(self.short_sma.Current.Value)
        self.Plot("MA", "9 Period Value", self.short_sma.Current.Value)
        self.ma20_values.append(self.long_sma.Current.Value)
        self.Plot("MA", "20 Period Value", self.long_sma.Current.Value)

        if self.ma9_window[0] > self.ma20_window[0] and self.ma9_window[1] < self.ma20_window[1]:
            self.ma_indicator_signals.append("BUY")
            self.Plot("MA", "Buy Signal", self.short_sma.Current.Value)
        elif self.ma9_window[0] < self.ma20_window[0] and self.ma9_window[1] > self.ma20_window[1]:
            self.ma_indicator_signals.append("SELL")
            self.Plot("MA", "Sell Signal", self.short_sma.Current.Value)
        else:
            self.ma_indicator_signals.append(None)

    def check_stochrsi_crossovers(self):
        self.stoch_k_window.add(self._srsi.K.Current.Value)
        self.stoch_d_window.add(self._srsi.D.Current.Value)
        
        self.stoch_k_values.append(self._srsi.K.Current.Value)
        self.Plot("STOCHRSI", "K Value", self._srsi.K.Current.Value)
        self.stoch_d_values.append(self._srsi.D.Current.Value)
        self.Plot("STOCHRSI", "D Value", self._srsi.D.Current.Value)

        # Initialize local flags
        k_buy = k_sell = d_buy = d_sell = False

        if self.stoch_k_window[0] > 20 and self.stoch_k_window[1] < 20:
            self.stoch_k_cross_window.add(True)
            k_buy = True
        elif self.stoch_k_window[0] < 80 and self.stoch_k_window[1] > 80:
            self.stoch_k_cross_window.add(True)
            k_sell = True
        else:
            self.stoch_k_cross_window.add(False)
        
        if self.stoch_d_window[0] > 20 and self.stoch_d_window[1] < 20:
            self.stoch_d_cross_window.add(True)
            d_buy = True
        elif self.stoch_d_window[0] < 80 and self.stoch_d_window[1] > 80:
            self.stoch_d_cross_window.add(True)
            d_sell = True
        else:
            self.stoch_d_cross_window.add(False)
        
        if d_buy and True in self.stoch_k_cross_window:
            self.stoch_indicator_signals.append("BUY")
            self.Plot("STOCHRSI", "Buy Signal", self._srsi.D.Current.Value)
        elif d_sell and True in self.stoch_k_cross_window:
            self.stoch_indicator_signals.append("SELL")
            self.Plot("STOCHRSI", "Sell Signal", self._srsi.D.Current.Value)
        elif k_buy and True in self.stoch_k_cross_window:
            self.stoch_indicator_signals.append("BUY")
            self.Plot("STOCHRSI", "Buy Signal", self._srsi.K.Current.Value)
        elif k_sell and True in self.stoch_k_cross_window:
            self.stoch_indicator_signals.append("SELL")
            self.Plot("STOCHRSI", "Sell Signal", self._srsi.K.Current.Value)
        else:
            self.stoch_indicator_signals.append(None)

    def check_lbr_crossovers(self):
        self.lbr_window.add(self._macd.Current.Value)
        self.lbr_signal_window.add(self._macd.Signal.Current.Value) 

        self.lbr_values.append(self._macd.Current.Value)
        self.Plot("LBROSC", "MACD Value", self._macd.Current.Value)
        self.lbr_signal_values.append(self._macd.Signal.Current.Value)
        self.Plot("LBROSC", "MACD Signal Value", self._macd.Signal.Current.Value)

        if self.lbr_window[0] > self.lbr_signal_window[0] and self.lbr_window[1] < self.lbr_signal_window[1]:
            self.lbr_indicator_signals.append("BUY")
            self.Plot("LBROSC", "Buy Signal", self._macd.Signal.Current.Value)
        elif self.lbr_window[0] < self.lbr_signal_window[0] and self.lbr_window[1] > self.lbr_signal_window[1]:
            self.lbr_indicator_signals.append("SELL")
            self.Plot("LBROSC", "Sell Signal", self._macd.Signal.Current.Value)
        else:
            self.lbr_indicator_signals.append(None)

    def check_mfi_crossovers(self):
        self.mfi_window.add(self._mfi.Current.Value)
        self.mfi_values.append(self._mfi.Current.Value)
        self.Plot("MFI", "MFI Value", self._mfi.Current.Value)

        if self.mfi_window[0] > 20 and self.mfi_window[1] < 20:
            self.mfi_indicator_signals.append("BUY")
            self.Plot("MFI", "Buy Signal", self._mfi.Current.Value)
        elif self.mfi_window[0] < 80 and self.mfi_window[1] > 80:
            self.mfi_indicator_signals.append("SELL")
            self.Plot("MFI", "Sell Signal", self._mfi.Current.Value)
        else:
            self.mfi_indicator_signals.append(None)

    def check_volume_spikes(self, data):
        if not data.ContainsKey(self._symbol):
            return

        bar = data[self._symbol]
        if bar is None:
            return
            
        if self.previous_close is None:
            self.previous_close = bar.Close
            return

        price_change = bar.Close - self.previous_close

        self.vol_values.append(bar.Volume)
        self.Plot("VOLUME", "Volume", bar.Volume)
        
        self.vol_sma_values.append(self._sma_vol.Current.Value)
        sma_vol_multiplier = self._sma_vol.Current.Value * VOLUME_SPIKE_MULTIPLIER
        self.Plot("VOLUME", "SMA Volume * Multiplier", sma_vol_multiplier)

        if bar.Volume > VOLUME_SPIKE_MULTIPLIER * self._sma_vol.Current.Value:
            if price_change > 0:
                self.vol_indicator_signals.append("BUY")
                self.Plot("VOLUME", "Buy Signal", bar.Volume)
            elif price_change < 0:
                self.vol_indicator_signals.append("SELL")
                self.Plot("VOLUME", "Sell Signal", bar.Volume)
        else:
            self.vol_indicator_signals.append(None)

        self.previous_close = bar.Close
        
    def calculate_net_signal_value(self):
        net_signal = 0.0
        active_signals = []
        for indicator in self.indicator_signal_lists:
            for i in range(TRIGGER_WINDOW):
                signal = self.indicator_signal_lists[indicator][-(i+1)]
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
        if orderEvent.Status == OrderStatus.Filled:
            if orderEvent.Direction == OrderDirection.Buy:
                # Only record trade entry if not already in an open trade
                if self.current_trade is None:
                    combo_key = ", ".join(sorted(self.active_signals)) if self.active_signals else "NO_SIGNAL"
                    self.current_trade = {
                        "entry_time": self.Time,
                        "entry_price": orderEvent.FillPrice,
                        "quantity": orderEvent.FillQuantity,
                        "active_signals": combo_key
                    }
                self.Plot("TradeSignals", "Entry", orderEvent.FillPrice)
            elif orderEvent.Direction == OrderDirection.Sell:
                self.Plot("TradeSignals", "Exit", orderEvent.FillPrice)
                # Only if a trade was recorded as open, record the exit and update stats
                if self.current_trade is not None:
                    exit_price = orderEvent.FillPrice
                    entry_price = self.current_trade["entry_price"]
                    quantity = self.current_trade["quantity"]
                    # Calculate percentage return
                    base_value = entry_price * quantity
                    if base_value == 0:
                        # Avoid division by zero;
                        trade_return = 0
                    else:
                        trade_return = ((exit_price * quantity) - base_value) / base_value * 100
                    pnl = (exit_price * quantity) - (entry_price * quantity)
                    duration = (self.Time - self.current_trade["entry_time"]).total_seconds() / 3600.0
                    trade_key = self.current_trade["active_signals"] if self.current_trade["active_signals"] else "NO_SIGNAL"
                    if trade_key not in self.trade_stats:
                        self.trade_stats[trade_key] = {
                            "count": 0,
                            "wins": 0,
                            "total_return": 0.0,
                            "total_pnl": 0.0,
                            "total_duration": 0.0,
                            "returns": [],
                            "max_return": None,
                            "min_return": None
                        }
                    stats = self.trade_stats[trade_key]
                    stats["count"] += 1
                    if trade_return > 0:
                        stats["wins"] += 1
                    stats["total_return"] += trade_return
                    stats["total_pnl"] += pnl
                    stats["total_duration"] += duration
                    stats["returns"].append(trade_return)
                    if stats["max_return"] is None or trade_return > stats["max_return"]:
                        stats["max_return"] = trade_return
                    if stats["min_return"] is None or trade_return < stats["min_return"]:
                        stats["min_return"] = trade_return
                    # Reset current trade since it has now been closed.
                    self.current_trade = None

            self.Debug(f"Order filled for {orderEvent.Symbol} at {orderEvent.FillPrice} as a {orderEvent.Direction} order.")

    def OnEndOfAlgorithm(self):
        # Log final counts for each indicator's signals
        for key, signal_list in self.indicator_signal_lists.items():
            buy_count = signal_list.count("BUY")
            sell_count = signal_list.count("SELL")
            self.Debug(f"{key} signals - BUY: {buy_count}, SELL: {sell_count}")
        for combo, stats in self.trade_stats.items():
            count = stats["count"]
            if count > 0:
                win_rate = (stats["wins"] / count) * 100
                avg_return = stats["total_return"] / count
                avg_duration = stats["total_duration"] / count
                # Calculate standard deviation of trade returns
                mean = avg_return
                variance = sum((r - mean) ** 2 for r in stats["returns"]) / count
                std_dev = math.sqrt(variance)
            else:
                win_rate = avg_return = avg_duration = std_dev = 0
            self.Debug(f"Trade Stats for combination [{combo}] - Count: {count}, Win Rate: {win_rate:.2f}%, "
                    f"Avg % Return: {avg_return:.2f}%, Total PnL: {stats['total_pnl']:.2f}, "
                    f"Avg Duration (hrs): {avg_duration:.2f}, Max Return: {stats['max_return']}, "
                    f"Min Return: {stats['min_return']}, Std Dev: {std_dev:.2f}")
