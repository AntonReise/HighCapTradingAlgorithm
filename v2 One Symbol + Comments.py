from AlgorithmImports import *
import math

# Global Parameters
SYMBOL = "AAPL"
START_DATE = "2021-01-01"
END_DATE = "2022-01-01"
INITIAL_CASH = 100000
TRIGGER_WINDOW = 5
REQUIRED_ENTRY_SIGNALS = 5
REQUIRED_EXIT_SIGNALS = 5
FIRST_TRADE_ALLOCATION = 0.5 #By having it be 0.5, it means that the first trade will be 50% of the portfolio,
REPEAT_TRADE_ALLOCATION = 0.5 #and the second trade will be 100% of the portfolio, limiting the amount of buys/sells to 2. 

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
# Individual charts
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
        
        # Add symbol and warmup
        self._symbol = self.AddEquity(SYMBOL, self.resolution).Symbol
        self.SetWarmUp(50, self.resolution)

        # Initialize Indicators
        self.short_sma = self.SMA(self._symbol, MA_FAST_PERIOD, self.resolution)
        self.long_sma = self.SMA(self._symbol, MA_SLOW_PERIOD, self.resolution)
        self.srsi = self.SRSI(self._symbol, STOCH_PERIOD, STOCH_PERIOD, STOCH_SMOOTH_K, STOCH_SMOOTH_D, self.resolution)
        self.macd = self.MACD(self._symbol, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
        self.mfi = self.MFI(self._symbol, MFI_PERIOD)
        self.sma_vol = self.SMA(self._symbol, VOLUME_LOOKBACK, self.resolution, Field.Volume)

        # Initialize Indicator Signal Lists
        self.ma_indicator_signals = [None] * TRIGGER_WINDOW if ENABLE_MA else []
        self.stoch_indicator_signals = [None] * TRIGGER_WINDOW if ENABLE_STOCH else []
        self.lbr_indicator_signals = [None] * TRIGGER_WINDOW if ENABLE_LBR else []
        self.mfi_indicator_signals = [None] * TRIGGER_WINDOW if ENABLE_MFI else []
        self.vol_indicator_signals = [None] * TRIGGER_WINDOW if ENABLE_VOL else []

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
        if ENABLE_MA:
            self.indicator_signal_lists["MA"] = self.ma_indicator_signals
        if ENABLE_STOCH:
            self.indicator_signal_lists["STOCH"] = self.stoch_indicator_signals
        if ENABLE_LBR:
            self.indicator_signal_lists["LBR"] = self.lbr_indicator_signals
        if ENABLE_MFI:
            self.indicator_signal_lists["MFI"] = self.mfi_indicator_signals
        if ENABLE_VOL:
            self.indicator_signal_lists["VOL"] = self.vol_indicator_signals

        # Create dictionary for indicator weights
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

        self._TrailingStopOrderTicket = None

        self.previous_close = None

        # Charting
        if ENABLE_CHARTING:
            if ENABLE_MA_CHART:
                ma_chart = Chart("MA")
                ma_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
                ma_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
                ma_chart.add_series(Series("9 Period Value", SeriesType.LINE, "$", Color.ORANGE))
                ma_chart.add_series(Series("20 Period Value", SeriesType.LINE, "$", Color.BLUE))
                self.AddChart(ma_chart)

            if ENABLE_STOCH_CHART:
                stochrsi_chart = Chart("STOCHRSI")
                stochrsi_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
                stochrsi_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
                stochrsi_chart.add_series(Series("K Value", SeriesType.LINE, "$", Color.BLUE))
                stochrsi_chart.add_series(Series("D Value", SeriesType.LINE, "$", Color.ORANGE))
                self.AddChart(stochrsi_chart)

            if ENABLE_LBR_CHART:
                lbrosc_chart = Chart("LBROSC")
                lbrosc_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
                lbrosc_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
                lbrosc_chart.add_series(Series("MACD Value", SeriesType.LINE, "$", Color.BLUE))
                lbrosc_chart.add_series(Series("MACD Signal Value", SeriesType.LINE, "$", Color.ORANGE))
                self.AddChart(lbrosc_chart)

            if ENABLE_MFI_CHART:
                mfi_chart = Chart("MFI")
                mfi_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
                mfi_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
                mfi_chart.add_series(Series("MFI Value", SeriesType.LINE, "$", Color.PURPLE))
                self.AddChart(mfi_chart)

            if ENABLE_VOL_CHART:
                volume_chart = Chart("VOLUME")
                volume_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
                volume_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
                volume_chart.add_series(Series("Volume", SeriesType.BAR, "$", Color.BLUE))
                volume_chart.add_series(Series("SMA Volume * Multiplier", SeriesType.LINE, "$", Color.RED))
                self.AddChart(volume_chart)

            if ENABLE_TRADE_CHART:
                trade_chart = Chart("TradeSignals")
                trade_chart.add_series(Series("Price", SeriesType.LINE, "$", Color.WHITE))
                trade_chart.add_series(Series("Entry", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
                trade_chart.add_series(Series("Exit", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
                trade_chart.add_series(Series("Trailing Stop", SeriesType.SCATTER, "$", Color.ORANGE, ScatterMarkerSymbol.CIRCLE))
                self.AddChart(trade_chart)

    def OnData(self, data):
        # Update indicator lists
        if ENABLE_MA:
            self.check_moving_average_crossovers()
        if ENABLE_STOCH:
            self.check_stochrsi_crossovers()
        if ENABLE_LBR:
            self.check_lbr_crossovers()
        if ENABLE_MFI:
            self.check_mfi_crossovers()
        if ENABLE_VOL:
            self.check_volume_spikes(data)

        if self._symbol in data.Bars:
            bar = data.Bars[self._symbol]
            if ENABLE_CHARTING and ENABLE_TRADE_CHART:
                self.Plot("TradeSignals", "Price", bar.Close)

        if not self.IsWarmingUp:
            net_signal = self.calculate_net_signal_value()
            
            # BUY SIGNAL
            if net_signal >= REQUIRED_ENTRY_SIGNALS:
                # If currently short, liquidate first
                if self.Portfolio[self._symbol].Quantity < 0:
                    self.Liquidate(self._symbol)
                    if self._TrailingStopOrderTicket is not None:
                        self._TrailingStopOrderTicket.cancel("Canceled TrailingStopOrder")
                    # Enter a long position at initial allocation
                    self.SetHoldings(self._symbol, FIRST_TRADE_ALLOCATION)
                    self.Debug(f"Liquidated short position and entered long on {self._symbol} for Net Signal {net_signal}. Active signals: {self.active_signals}")
                    # Set trailing stop for long position
                    if ENABLE_TRAILING_STOPS:
                        self._TrailingStopOrderTicket = self.TrailingStopOrder(self._symbol, -self.Portfolio[self._symbol].Quantity, TRAILING_STOP_PERCENT, True)
                else:
                    # If not invested, go long with initial allocation
                    if not self.Portfolio[self._symbol].Invested:
                        self.SetHoldings(self._symbol, FIRST_TRADE_ALLOCATION)
                        self.Debug(f"Entered long trade on {self._symbol} for Net Signal {net_signal}. Active signals: {self.active_signals}")
                        # Set trailing stop for long position
                        if ENABLE_TRAILING_STOPS:
                            self._TrailingStopOrderTicket = self.TrailingStopOrder(self._symbol, -self.Portfolio[self._symbol].Quantity, TRAILING_STOP_PERCENT, True)
                    else:
                        # If already long, increase position by additional allocation
                        current_weight = self.Portfolio[self._symbol].HoldingsValue / self.Portfolio.TotalPortfolioValue
                        new_target = min(current_weight + REPEAT_TRADE_ALLOCATION, 1.0)
                        self.SetHoldings(self._symbol, new_target)
                        self.Debug(f"Increased long position on {self._symbol} to {new_target:.2f} for Net Signal {net_signal}. Active signals: {self.active_signals}")

                # Update trade information
                if self.current_trade is None or self.Portfolio[self._symbol].Quantity > 0:
                    combo_key = ", ".join(sorted(self.active_signals)) if self.active_signals else "NO_SIGNAL"
                    self.current_trade = {
                        "entry_time": self.Time,
                        "entry_price": self.Securities[self._symbol].Price,
                        "quantity": self.Portfolio[self._symbol].Quantity,
                        "active_signals": combo_key
                    }
            
            # SELL SIGNAL
            elif net_signal <= -REQUIRED_EXIT_SIGNALS:
                # If currently long, liquidate first
                if self.Portfolio[self._symbol].Quantity > 0:
                    self.Liquidate(self._symbol)
                    if self._TrailingStopOrderTicket is not None:
                        self._TrailingStopOrderTicket.cancel("Canceled TrailingStopOrder")
                    # Enter a short position at initial allocation
                    self.SetHoldings(self._symbol, -FIRST_TRADE_ALLOCATION)
                    self.Debug(f"Liquidated long position and entered short on {self._symbol} for Net Signal {net_signal}. Active signals: {self.active_signals}")
                    # Set trailing stop for short position
                    if ENABLE_TRAILING_STOPS:
                        self._TrailingStopOrderTicket = self.TrailingStopOrder(self._symbol, -self.Portfolio[self._symbol].Quantity, TRAILING_STOP_PERCENT, True)
                else:
                    # If not invested, go short with initial allocation
                    if not self.Portfolio[self._symbol].Invested:
                        self.SetHoldings(self._symbol, -FIRST_TRADE_ALLOCATION)
                        self.Debug(f"Entered short trade on {self._symbol} for Net Signal {net_signal}. Active signals: {self.active_signals}")
                        # Set trailing stop for short position
                        if ENABLE_TRAILING_STOPS:
                            self._TrailingStopOrderTicket = self.TrailingStopOrder(self._symbol, -self.Portfolio[self._symbol].Quantity, TRAILING_STOP_PERCENT, True)
                    else:
                        # If already short, increase short position by additional allocation
                        current_weight = self.Portfolio[self._symbol].HoldingsValue / self.Portfolio.TotalPortfolioValue
                        new_target = max(current_weight - REPEAT_TRADE_ALLOCATION, -1.0)
                        self.SetHoldings(self._symbol, new_target)
                        self.Debug(f"Increased short position on {self._symbol} to {new_target:.2f} for Net Signal {net_signal}. Active signals: {self.active_signals}")
                

                # Update trade information
                if self.current_trade is None or self.Portfolio[self._symbol].Quantity < 0:
                    combo_key = ", ".join(sorted(self.active_signals)) if self.active_signals else "NO_SIGNAL"
                    self.current_trade = {
                        "entry_time": self.Time,
                        "entry_price": self.Securities[self._symbol].Price,
                        "quantity": self.Portfolio[self._symbol].Quantity,
                        "active_signals": combo_key
                    }

    def check_moving_average_crossovers(self):
        # Update rolling windows for MA values
        self.ma9_window.add(self.short_sma.Current.Value)
        self.ma20_window.add(self.long_sma.Current.Value)

        self.ma9_values.append(self.short_sma.Current.Value)
        if ENABLE_CHARTING and ENABLE_MA_CHART:
            self.Plot("MA", "9 Period Value", self.short_sma.Current.Value)
        self.ma20_values.append(self.long_sma.Current.Value)
        if ENABLE_CHARTING and ENABLE_MA_CHART:
            self.Plot("MA", "20 Period Value", self.long_sma.Current.Value)

        if self.ma9_window[0] > self.ma20_window[0] and self.ma9_window[1] < self.ma20_window[1]:
            self.ma_indicator_signals.append("BUY")
            if ENABLE_CHARTING and ENABLE_MA_CHART:
                self.Plot("MA", "Buy Signal", self.short_sma.Current.Value)
        elif self.ma9_window[0] < self.ma20_window[0] and self.ma9_window[1] > self.ma20_window[1]:
            self.ma_indicator_signals.append("SELL")
            if ENABLE_CHARTING and ENABLE_MA_CHART:
                self.Plot("MA", "Sell Signal", self.short_sma.Current.Value)
        else:
            self.ma_indicator_signals.append(None)

    def check_stochrsi_crossovers(self):
        self.stoch_k_window.add(self.srsi.K.Current.Value)
        self.stoch_d_window.add(self.srsi.D.Current.Value)
        
        self.stoch_k_values.append(self.srsi.K.Current.Value)
        if ENABLE_CHARTING and ENABLE_STOCH_CHART:
            self.Plot("STOCHRSI", "K Value", self.srsi.K.Current.Value)
        self.stoch_d_values.append(self.srsi.D.Current.Value)
        if ENABLE_CHARTING and ENABLE_STOCH_CHART:
            self.Plot("STOCHRSI", "D Value", self.srsi.D.Current.Value)

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
            if ENABLE_CHARTING and ENABLE_STOCH_CHART:
                self.Plot("STOCHRSI", "Buy Signal", self.srsi.D.Current.Value)
        elif d_sell and True in self.stoch_k_cross_window:
            self.stoch_indicator_signals.append("SELL")
            if ENABLE_CHARTING and ENABLE_STOCH_CHART:
                self.Plot("STOCHRSI", "Sell Signal", self.srsi.D.Current.Value)
        elif k_buy and True in self.stoch_k_cross_window:
            self.stoch_indicator_signals.append("BUY")
            if ENABLE_CHARTING and ENABLE_STOCH_CHART:
                self.Plot("STOCHRSI", "Buy Signal", self.srsi.K.Current.Value)
        elif k_sell and True in self.stoch_k_cross_window:
            self.stoch_indicator_signals.append("SELL")
            if ENABLE_CHARTING and ENABLE_STOCH_CHART:
                self.Plot("STOCHRSI", "Sell Signal", self.srsi.K.Current.Value)
        else:
            self.stoch_indicator_signals.append(None)

    def check_lbr_crossovers(self):
        self.lbr_window.add(self.macd.Current.Value)
        self.lbr_signal_window.add(self.macd.Signal.Current.Value) 

        self.lbr_values.append(self.macd.Current.Value)
        if ENABLE_CHARTING and ENABLE_LBR_CHART:
            self.Plot("LBROSC", "MACD Value", self.macd.Current.Value)
        self.lbr_signal_values.append(self.macd.Signal.Current.Value)
        if ENABLE_CHARTING and ENABLE_LBR_CHART:
            self.Plot("LBROSC", "MACD Signal Value", self.macd.Signal.Current.Value)

        if self.lbr_window[0] > self.lbr_signal_window[0] and self.lbr_window[1] < self.lbr_signal_window[1]:
            self.lbr_indicator_signals.append("BUY")
            if ENABLE_CHARTING and ENABLE_LBR_CHART:
                self.Plot("LBROSC", "Buy Signal", self.macd.Signal.Current.Value)
        elif self.lbr_window[0] < self.lbr_signal_window[0] and self.lbr_window[1] > self.lbr_signal_window[1]:
            self.lbr_indicator_signals.append("SELL")
            if ENABLE_CHARTING and ENABLE_LBR_CHART:
                self.Plot("LBROSC", "Sell Signal", self.macd.Current.Value)
        else:
            self.lbr_indicator_signals.append(None)

    def check_mfi_crossovers(self):
        self.mfi_window.add(self.mfi.Current.Value)
        self.mfi_values.append(self.mfi.Current.Value)
        if ENABLE_CHARTING and ENABLE_MFI_CHART:
            self.Plot("MFI", "MFI Value", self.mfi.Current.Value)

        if self.mfi_window[0] > 20 and self.mfi_window[1] < 20:
            self.mfi_indicator_signals.append("BUY")
            if ENABLE_CHARTING and ENABLE_MFI_CHART:
                self.Plot("MFI", "Buy Signal", self.mfi.Current.Value)
        elif self.mfi_window[0] < 80 and self.mfi_window[1] > 80:
            self.mfi_indicator_signals.append("SELL")
            if ENABLE_CHARTING and ENABLE_MFI_CHART:
                self.Plot("MFI", "Sell Signal", self.mfi.Current.Value)
        else:
            self.mfi_indicator_signals.append(None)

    def check_volume_spikes(self, data):
        if self._symbol not in data.Bars:
            return
            
        bar = data.Bars[self._symbol]
        if bar is None:
            return
                
        if self.previous_close is None:
            self.previous_close = bar.Close
            return

        price_change = bar.Close - self.previous_close

        self.vol_values.append(bar.Volume)
        if ENABLE_CHARTING and ENABLE_VOL_CHART:
            self.Plot("VOLUME", "Volume", bar.Volume)
        
        self.vol_sma_values.append(self.sma_vol.Current.Value)
        sma_vol_multiplier = self.sma_vol.Current.Value * VOLUME_SPIKE_MULTIPLIER
        if ENABLE_CHARTING and ENABLE_VOL_CHART:
            self.Plot("VOLUME", "SMA Volume * Multiplier", sma_vol_multiplier)

        if bar.Volume > VOLUME_SPIKE_MULTIPLIER * self.sma_vol.Current.Value:
            if price_change > 0:
                self.vol_indicator_signals.append("BUY")
                if ENABLE_CHARTING and ENABLE_VOL_CHART:
                    self.Plot("VOLUME", "Buy Signal", bar.Volume)
            elif price_change < 0:
                self.vol_indicator_signals.append("SELL")
                if ENABLE_CHARTING and ENABLE_VOL_CHART:
                    self.Plot("VOLUME", "Sell Signal", bar.Volume)
        else:
            self.vol_indicator_signals.append(None)

        self.previous_close = bar.Close
        
    def calculate_net_signal_value(self):
        net_signal = 0.0
        active_signals = []
        for indicator in self.indicator_signal_lists:
            # Look back TRIGGER_WINDOW signals (most recent last)
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
        if orderEvent.Status != OrderStatus.Filled:
            return
            
        # First, retrieve the complete order object
        order = self.Transactions.GetOrderById(orderEvent.OrderId)
        
        # Check if this is a trailing stop order that got filled
        is_trailing_stop = order.Type == OrderType.TrailingStop
        
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
            
            # Plot the entry point
            if ENABLE_CHARTING and ENABLE_TRADE_CHART:
                if is_trailing_stop:
                    self.Plot("TradeSignals", "Trailing Stop", orderEvent.FillPrice)
                    self.Debug(f"Trailing stop buy triggered at {orderEvent.FillPrice}")
                else:
                    self.Plot("TradeSignals", "Entry", orderEvent.FillPrice)
                
        elif orderEvent.Direction == OrderDirection.Sell:
            # Plot the exit point
            if ENABLE_CHARTING and ENABLE_TRADE_CHART:
                if is_trailing_stop:
                    self.Plot("TradeSignals", "Trailing Stop", orderEvent.FillPrice)
                    self.Debug(f"Trailing stop sell triggered at {orderEvent.FillPrice}")
                else:
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
                        "min_return": None,
                        "trailing_stop_exits": 0
                    }
                stats = self.trade_stats[trade_key]
                stats["count"] += 1
                if trade_return > 0:
                    stats["wins"] += 1
                stats["total_return"] += trade_return
                stats["total_pnl"] += pnl
                stats["total_duration"] += duration
                stats["returns"].append(trade_return)
                if is_trailing_stop:
                    stats["trailing_stop_exits"] += 1
                if stats["max_return"] is None or trade_return > stats["max_return"]:
                    stats["max_return"] = trade_return
                if stats["min_return"] is None or trade_return < stats["min_return"]:
                    stats["min_return"] = trade_return
                # Reset current trade since it has now been closed.
                self.current_trade = None

        # Reset trailing stop ticket if this order fill is from our trailing stop
        if is_trailing_stop and self._TrailingStopOrderTicket is not None:
            if self._TrailingStopOrderTicket.OrderId == orderEvent.OrderId:
                self._TrailingStopOrderTicket = None

        self.Debug(f"Order filled for {orderEvent.Symbol} at {orderEvent.FillPrice} as a {orderEvent.Direction} order. Order type: {order.Type}")

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
                
                # Get trailing stop exit stats if available
                trailing_exits = stats.get("trailing_stop_exits", 0)
                trailing_exit_pct = (trailing_exits / count) * 100 if count > 0 else 0
            else:
                win_rate = avg_return = avg_duration = std_dev = trailing_exit_pct = 0
                trailing_exits = 0
                
            self.Debug(f"Trade Stats for combination [{combo}] - Count: {count}, Win Rate: {win_rate:.2f}%, "
                    f"Avg % Return: {avg_return:.2f}%, Total PnL: {stats['total_pnl']:.2f}, "
                    f"Avg Duration (hrs): {avg_duration:.2f}, Max Return: {stats['max_return']}, "
                    f"Min Return: {stats['min_return']}, Std Dev: {std_dev:.2f}, "
                    f"Trailing Stop Exits: {trailing_exits} ({trailing_exit_pct:.2f}%)")
