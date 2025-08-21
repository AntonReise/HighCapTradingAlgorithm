from AlgorithmImports import *
import math

class SignalMode:
    WEIGHTED = "WEIGHTED"
    COUNT = "COUNT"
SYMBOLS = ["AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "NFLX", "AVGO"]
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
MAX_ALLOCATION_PER_SYMBOL = 0.25
ENABLE_TRAILING_STOPS = True
TRAILING_STOP_PERCENT = 0.15
ENABLE_MA = True
ENABLE_STOCH = False
ENABLE_LBR = True# MACD
ENABLE_MFI = False
ENABLE_VOL = False
MA_WEIGHT = 1.0
STOCH_WEIGHT = 1.0
LBR_WEIGHT = 1.0
MFI_WEIGHT = 1.0
VOL_WEIGHT = 1.0
MA_FAST_PERIOD = 50
MA_SLOW_PERIOD = 200
STOCH_PERIOD = 14
STOCH_SMOOTH_K = 3
STOCH_SMOOTH_D = 3
STOCH_UPPER = 80
STOCH_LOWER = 20
STOCH_LOOKBACK = 3
MFI_PERIOD = 14
MFI_UPPER = 80
MFI_LOWER = 20
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
VOLUME_SPIKE_MULTIPLIER = 2.0
VOLUME_LOOKBACK = 35
ENABLE_CHARTING = True
ENABLE_MA_CHART = True
ENABLE_STOCH_CHART = False
ENABLE_LBR_CHART = True
ENABLE_MFI_CHART = False
ENABLE_VOL_CHART = False
ENABLE_TRADE_CHART = True

class HighCapMultiIndicatorStrategy(QCAlgorithm):
    def Initialize(self):
        start_year, start_month, start_day = map(int, START_DATE.split("-"))
        end_year, end_month, end_day = map(int, END_DATE.split("-"))
        self.set_start_date(start_year, start_month, start_day)
        self.set_end_date(end_year, end_month, end_day)
        self.set_cash(INITIAL_CASH)
        self.resolution = Resolution.DAILY
        
        self.set_brokerage_model(BrokerageName.QUANT_CONNECT_BROKERAGE)
        
        self.set_warm_up(50, self.resolution)

        self.symbols = []
        for ticker in SYMBOLS:
            symbol = self.add_equity(ticker, self.resolution).Symbol
            self.symbols.append(symbol)

        self.short_sma_indicators = {}
        self.long_sma_indicators = {}
        self.srsi_indicators = {}
        self.macd_indicators = {}
        self.mfi_indicators = {}
        self.sma_vol_indicators = {}

        for symbol in self.symbols:
            if ENABLE_MA:
                self.short_sma_indicators[symbol] = self.sma(symbol, MA_FAST_PERIOD, self.resolution)
                self.long_sma_indicators[symbol] = self.sma(symbol, MA_SLOW_PERIOD, self.resolution)
            if ENABLE_STOCH:
                self.srsi_indicators[symbol] = self.srsi(symbol, STOCH_PERIOD, STOCH_PERIOD, STOCH_SMOOTH_K, STOCH_SMOOTH_D, MovingAverageType.SIMPLE, self.resolution)
            if ENABLE_LBR:
                self.macd_indicators[symbol] = self.macd(symbol, MACD_FAST, MACD_SLOW, MACD_SIGNAL, MovingAverageType.SIMPLE, self.resolution)
            if ENABLE_MFI:
                self.mfi_indicators[symbol] = self.mfi(symbol, MFI_PERIOD)
            if ENABLE_VOL:
                self.sma_vol_indicators[symbol] = self.sma(symbol, VOLUME_LOOKBACK, self.resolution, Field.VOLUME)

        self.ma_indicator_signals = {}
        self.stoch_indicator_signals = {}
        self.lbr_indicator_signals = {}
        self.mfi_indicator_signals = {}
        self.vol_indicator_signals = {}

        self.ma9_values = {}
        self.ma20_values = {}
        self.stoch_k_values = {}
        self.stoch_d_values = {}
        self.lbr_values = {}
        self.lbr_signal_values = {}
        self.mfi_values = {}
        self.vol_values = {}
        self.vol_sma_values = {}

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

        self.trade_stats = {symbol: {} for symbol in self.symbols}
        self.current_trades = {symbol: None for symbol in self.symbols}
        
        self._TrailingStopOrderTicket = {symbol: None for symbol in self.symbols}

        for symbol in self.symbols:
            sym_str = symbol.Value
            
            if ENABLE_CHARTING:
                if ENABLE_MA_CHART:
                    ma_chart = Chart(f"{sym_str}_MA")
                    ma_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
                    ma_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
                    ma_chart.add_series(Series("9 Period Value", SeriesType.LINE, "$", Color.ORANGE))
                    ma_chart.add_series(Series("20 Period Value", SeriesType.LINE, "$", Color.BLUE))
                    self.add_chart(ma_chart)

                if ENABLE_STOCH_CHART:
                    stochrsi_chart = Chart(f"{sym_str}_STOCHRSI")
                    stochrsi_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
                    stochrsi_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
                    stochrsi_chart.add_series(Series("K Value", SeriesType.LINE, "$", Color.BLUE))
                    stochrsi_chart.add_series(Series("D Value", SeriesType.LINE, "$", Color.ORANGE))
                    self.add_chart(stochrsi_chart)

                if ENABLE_LBR_CHART:
                    lbrosc_chart = Chart(f"{sym_str}_LBROSC")
                    lbrosc_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
                    lbrosc_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
                    lbrosc_chart.add_series(Series("MACD Value", SeriesType.LINE, "$", Color.BLUE))
                    lbrosc_chart.add_series(Series("MACD Signal Value", SeriesType.LINE, "$", Color.ORANGE))
                    self.add_chart(lbrosc_chart)

                if ENABLE_MFI_CHART:
                    mfi_chart = Chart(f"{sym_str}_MFI")
                    mfi_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
                    mfi_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
                    mfi_chart.add_series(Series("MFI Value", SeriesType.LINE, "$", Color.PURPLE))
                    self.add_chart(mfi_chart)

                if ENABLE_VOL_CHART:
                    volume_chart = Chart(f"{sym_str}_VOLUME")
                    volume_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
                    volume_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
                    volume_chart.add_series(Series("Volume", SeriesType.BAR, "$", Color.BLUE))
                    volume_chart.add_series(Series("SMA Volume * Multiplier", SeriesType.LINE, "$", Color.RED))
                    self.add_chart(volume_chart)

                if ENABLE_TRADE_CHART:
                    trade_chart = Chart(f"{sym_str}_TradeSignals")
                    trade_chart.add_series(Series("Price", SeriesType.LINE, "$", Color.WHITE))
                    trade_chart.add_series(Series("Entry", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
                    trade_chart.add_series(Series("Exit", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
                    trade_chart.add_series(Series("Trailing Stop", SeriesType.SCATTER, "$", Color.ORANGE, ScatterMarkerSymbol.CIRCLE))
                    self.add_chart(trade_chart)

    def OnData(self, data):
        for symbol in self.symbols:
            if symbol not in data.Bars:
                continue

            bar = data.Bars[symbol]
            if ENABLE_CHARTING and ENABLE_TRADE_CHART:
                self.plot(f"{symbol.Value}_TradeSignals", "Price", bar.Close)

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

            if not self.is_warming_up:
                net_signal = self.calculate_net_signal_value(symbol)
                
                if SIGNAL_CALCULATION_MODE == SignalMode.WEIGHTED:
                    entry_threshold = WEIGHTED_SCORE_THRESHOLD
                    exit_threshold = -WEIGHTED_SCORE_THRESHOLD
                else: # COUNT
                    entry_threshold = REQUIRED_ENTRY_SIGNALS
                    exit_threshold = -REQUIRED_EXIT_SIGNALS

                if net_signal >= entry_threshold:
                    if self.portfolio[symbol].quantity < 0:
                        self.liquidate(symbol)
                        if self._TrailingStopOrderTicket[symbol] is not None:
                            self._TrailingStopOrderTicket[symbol].cancel("canceled TrailingStopOrder")
                        self.set_holdings(symbol, FIRST_TRADE_ALLOCATION)
                        self.debug(f"Liquidated short position and entered long on {symbol} for Net Signal {net_signal}. Active signals: {self.active_signals}")
                        if ENABLE_TRAILING_STOPS:
                            self._TrailingStopOrderTicket[symbol] = self.trailing_stop_order(symbol, -self.portfolio[symbol].quantity, TRAILING_STOP_PERCENT, True)
                    else:
                        if not self.portfolio[symbol].invested:
                            self.set_holdings(symbol, FIRST_TRADE_ALLOCATION)
                            self.debug(f"Entered long trade on {symbol} for Net Signal {net_signal}. Active signals: {self.active_signals}")
                            if ENABLE_TRAILING_STOPS:
                                self._TrailingStopOrderTicket[symbol] = self.trailing_stop_order(symbol, -self.portfolio[symbol].quantity, TRAILING_STOP_PERCENT, True)
                        else:
                            current_weight = self.portfolio[symbol].holdings_value / self.portfolio.total_portfolio_value
                            new_target = min(current_weight + REPEAT_TRADE_ALLOCATION, MAX_ALLOCATION_PER_SYMBOL)
                            self.set_holdings(symbol, new_target)
                            self.debug(f"Increased long position on {symbol} to {new_target:.2f} for Net Signal {net_signal}. Active signals: {self.active_signals}")
                    
                    if self.current_trades[symbol] is None or self.portfolio[symbol].quantity > 0:
                        combo_key = ", ".join(sorted(self.active_signals)) if self.active_signals else "NO_SIGNAL"
                        self.current_trades[symbol] = {
                            "entry_time": self.time,
                            "entry_price": self.securities[symbol].price,
                            "quantity": self.portfolio[symbol].quantity,
                            "active_signals": combo_key
                        }
                
                elif net_signal <= exit_threshold:
                    if self.portfolio[symbol].quantity > 0:
                        self.liquidate(symbol)
                        if self._TrailingStopOrderTicket[symbol] is not None:
                            self._TrailingStopOrderTicket[symbol].cancel("canceled TrailingStopOrder")
                        self.set_holdings(symbol, -FIRST_TRADE_ALLOCATION)
                        self.debug(f"Liquidated long position and entered short on {symbol} for Net Signal {net_signal}. Active signals: {self.active_signals}")
                        if ENABLE_TRAILING_STOPS:
                            self._TrailingStopOrderTicket[symbol] = self.trailing_stop_order(symbol, -self.portfolio[symbol].quantity, TRAILING_STOP_PERCENT, True)
                    else:
                        if not self.portfolio[symbol].invested:
                            self.set_holdings(symbol, -FIRST_TRADE_ALLOCATION)
                            self.debug(f"Entered short trade on {symbol} for Net Signal {net_signal}. Active signals: {self.active_signals}")
                            if ENABLE_TRAILING_STOPS:
                                self._TrailingStopOrderTicket[symbol] = self.trailing_stop_order(symbol, -self.portfolio[symbol].quantity, TRAILING_STOP_PERCENT, True)
                        else:
                            current_weight = self.portfolio[symbol].holdings_value / self.portfolio.total_portfolio_value
                            new_target = max(current_weight - REPEAT_TRADE_ALLOCATION, -1.0)
                            self.set_holdings(symbol, new_target)
                            self.debug(f"Increased short position on {symbol} to {new_target:.2f} for Net Signal {net_signal}. Active signals: {self.active_signals}")
                    
                    
                    if self.current_trades[symbol] is None or self.portfolio[symbol].quantity < 0:
                        combo_key = ", ".join(sorted(self.active_signals)) if self.active_signals else "NO_SIGNAL"
                        self.current_trades[symbol] = {
                            "entry_time": self.time,
                            "entry_price": self.securities[symbol].price,
                            "quantity": self.portfolio[symbol].quantity,
                            "active_signals": combo_key
                        }

    def check_moving_average_crossovers(self, symbol, bar):
        short_sma = self.short_sma_indicators[symbol].Current.Value
        long_sma = self.long_sma_indicators[symbol].Current.Value
        self.ma9_window[symbol].add(short_sma)
        self.ma20_window[symbol].add(long_sma)

        self.ma9_values[symbol].append(short_sma)
        if ENABLE_CHARTING and ENABLE_MA_CHART:
            self.plot(f"{symbol.Value}_MA", "9 Period Value", short_sma)
        self.ma20_values[symbol].append(long_sma)
        if ENABLE_CHARTING and ENABLE_MA_CHART:
            self.plot(f"{symbol.Value}_MA", "20 Period Value", long_sma)

        signal = None
        if self.ma9_window[symbol][0] > self.ma20_window[symbol][0] and self.ma9_window[symbol][1] < self.ma20_window[symbol][1]:
            signal = "BUY"
        elif self.ma9_window[symbol][0] < self.ma20_window[symbol][0] and self.ma9_window[symbol][1] > self.ma20_window[symbol][1]:
            signal = "SELL"
        
        self.ma_indicator_signals[symbol].append(signal)
        if signal and ENABLE_CHARTING and ENABLE_MA_CHART:
            self.plot(f"{symbol.Value}_MA", f"{signal.capitalize()} Signal", short_sma)

    def check_stochrsi_crossovers(self, symbol, bar):
        self.stoch_k_window[symbol].add(self.srsi_indicators[symbol].K.Current.Value)
        self.stoch_d_window[symbol].add(self.srsi_indicators[symbol].D.Current.Value)

        self.stoch_k_values[symbol].append(self.srsi_indicators[symbol].K.Current.Value)
        if ENABLE_CHARTING and ENABLE_STOCH_CHART:
            self.plot(f"{symbol.Value}_STOCHRSI", "K Value", self.srsi_indicators[symbol].K.Current.Value)
        self.stoch_d_values[symbol].append(self.srsi_indicators[symbol].D.Current.Value)
        if ENABLE_CHARTING and ENABLE_STOCH_CHART:
            self.plot(f"{symbol.Value}_STOCHRSI", "D Value", self.srsi_indicators[symbol].D.Current.Value)

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
                self.plot(f"{symbol.Value}_STOCHRSI", "Buy Signal", self.srsi_indicators[symbol].D.Current.Value)
        elif d_sell and True in self.stoch_k_cross_window[symbol]:
            self.stoch_indicator_signals[symbol].append("SELL")
            if ENABLE_CHARTING and ENABLE_STOCH_CHART:
                self.plot(f"{symbol.Value}_STOCHRSI", "Sell Signal", self.srsi_indicators[symbol].D.Current.Value)
        elif k_buy and True in self.stoch_k_cross_window[symbol]:
            self.stoch_indicator_signals[symbol].append("BUY")
            if ENABLE_CHARTING and ENABLE_STOCH_CHART:
                self.plot(f"{symbol.Value}_STOCHRSI", "Buy Signal", self.srsi_indicators[symbol].K.Current.Value)
        elif k_sell and True in self.stoch_k_cross_window[symbol]:
            self.stoch_indicator_signals[symbol].append("SELL")
            if ENABLE_CHARTING and ENABLE_STOCH_CHART:
                self.plot(f"{symbol.Value}_STOCHRSI", "Sell Signal", self.srsi_indicators[symbol].K.Current.Value)
        else:
            self.stoch_indicator_signals[symbol].append(None)

    def check_lbr_crossovers(self, symbol, bar):
        macd_val = self.macd_indicators[symbol].Current.Value
        signal_val = self.macd_indicators[symbol].Signal.Current.Value
        self.lbr_window[symbol].add(macd_val)
        self.lbr_signal_window[symbol].add(signal_val)

        self.lbr_values[symbol].append(macd_val)
        if ENABLE_CHARTING and ENABLE_LBR_CHART:
            self.plot(f"{symbol.Value}_LBROSC", "MACD Value", macd_val)
        self.lbr_signal_values[symbol].append(signal_val)
        if ENABLE_CHARTING and ENABLE_LBR_CHART:
            self.plot(f"{symbol.Value}_LBROSC", "MACD Signal Value", signal_val)

        signal = None
        if self.lbr_window[symbol][0] > self.lbr_signal_window[symbol][0] and self.lbr_window[symbol][1] < self.lbr_signal_window[symbol][1]:
            signal = "BUY"
        elif self.lbr_window[symbol][0] < self.lbr_signal_window[symbol][0] and self.lbr_window[symbol][1] > self.lbr_signal_window[symbol][1]:
            signal = "SELL"

        self.lbr_indicator_signals[symbol].append(signal)
        if signal and ENABLE_CHARTING and ENABLE_LBR_CHART:
            self.plot(f"{symbol.Value}_LBROSC", f"{signal.capitalize()} Signal", signal_val)

    def check_mfi_crossovers(self, symbol, bar):
        self.mfi_window[symbol].add(self.mfi_indicators[symbol].Current.Value)
        self.mfi_values[symbol].append(self.mfi_indicators[symbol].Current.Value)
        if ENABLE_CHARTING and ENABLE_MFI_CHART:
            self.plot(f"{symbol.Value}_MFI", "MFI Value", self.mfi_indicators[symbol].Current.Value)

        if self.mfi_window[symbol][0] > 20 and self.mfi_window[symbol][1] < 20:
            self.mfi_indicator_signals[symbol].append("BUY")
            if ENABLE_CHARTING and ENABLE_MFI_CHART:
                self.plot(f"{symbol.Value}_MFI", "Buy Signal", self.mfi_indicators[symbol].Current.Value)
        elif self.mfi_window[symbol][0] < 80 and self.mfi_window[symbol][1] > 80:
            self.mfi_indicator_signals[symbol].append("SELL")
            if ENABLE_CHARTING and ENABLE_MFI_CHART:
                self.plot(f"{symbol.Value}_MFI", "Sell Signal", self.mfi_indicators[symbol].Current.Value)
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
            self.plot(f"{symbol.Value}_VOLUME", "Volume", bar.Volume)

        self.vol_sma_values[symbol].append(self.sma_vol_indicators[symbol].Current.Value)
        sma_vol_multiplier = self.sma_vol_indicators[symbol].Current.Value * VOLUME_SPIKE_MULTIPLIER
        if ENABLE_CHARTING and ENABLE_VOL_CHART:
            self.plot(f"{symbol.Value}_VOLUME", "SMA Volume * Multiplier", sma_vol_multiplier)

        if bar.Volume > VOLUME_SPIKE_MULTIPLIER * self.sma_vol_indicators[symbol].Current.Value:
            if price_change > 0:
                self.vol_indicator_signals[symbol].append("BUY")
                if ENABLE_CHARTING and ENABLE_VOL_CHART:
                    self.plot(f"{symbol.Value}_VOLUME", "Buy Signal", bar.Volume)
            elif price_change < 0:
                self.vol_indicator_signals[symbol].append("SELL")
                if ENABLE_CHARTING and ENABLE_VOL_CHART:
                    self.plot(f"{symbol.Value}_VOLUME", "Sell Signal", bar.Volume)
        else:
            self.vol_indicator_signals[symbol].append(None)

        self.previous_close[symbol] = bar.Close

    def calculate_net_signal_value(self, symbol):
        net_signal = 0.0
        active_signals = []
        for indicator, signals in self.indicator_signal_lists[symbol].items():
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

    def OnOrderEvent(self, orderEvent):
        if orderEvent.Status != OrderStatus.FILLED:
            return

        symbol = orderEvent.Symbol
        order = self.transactions.get_order_by_id(orderEvent.OrderId)
        
        is_trailing_stop = order.type == OrderType.TRAILING_STOP
        
        if orderEvent.Direction == OrderDirection.BUY:
            if self.current_trades[symbol] is None:
                combo_key = ", ".join(sorted(self.active_signals)) if self.active_signals else "NO_SIGNAL"
                self.current_trades[symbol] = {
                    "entry_time": self.time,
                    "entry_price": orderEvent.FillPrice,
                    "quantity": orderEvent.FillQuantity,
                    "active_signals": combo_key
                }
            
            if ENABLE_CHARTING and ENABLE_TRADE_CHART:
                if is_trailing_stop:
                    self.plot(f"{symbol.Value}_TradeSignals", "Trailing Stop", orderEvent.FillPrice)
                    self.debug(f"Trailing stop buy triggered at {orderEvent.FillPrice} for {symbol}")
                else:
                    self.plot(f"{symbol.Value}_TradeSignals", "Entry", orderEvent.FillPrice)
                
        elif orderEvent.Direction == OrderDirection.SELL:
            if ENABLE_CHARTING and ENABLE_TRADE_CHART:
                if is_trailing_stop:
                    self.plot(f"{symbol.Value}_TradeSignals", "Trailing Stop", orderEvent.FillPrice)
                    self.debug(f"Trailing stop sell triggered at {orderEvent.FillPrice} for {symbol}")
                else:
                    self.plot(f"{symbol.Value}_TradeSignals", "Exit", orderEvent.FillPrice)
                
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
                duration = (self.time - self.current_trades[symbol]["entry_time"]).total_seconds() / 3600.0
                stats["total_duration"] += duration
                stats["returns"].append(trade_return)
                
                if is_trailing_stop:
                    stats["trailing_stop_exits"] += 1
                    
                stats["max_return"] = trade_return if stats["max_return"] is None or trade_return > stats["max_return"] else stats["max_return"]
                stats["min_return"] = trade_return if stats["min_return"] is None or trade_return < stats["min_return"] else stats["min_return"]
                
                self.current_trades[symbol] = None

        if is_trailing_stop and symbol in self._TrailingStopOrderTicket:
            if self._TrailingStopOrderTicket[symbol] is not None and self._TrailingStopOrderTicket[symbol].OrderId == orderEvent.OrderId:
                self._TrailingStopOrderTicket[symbol] = None

        self.debug(f"Order filled for {symbol} at {orderEvent.FillPrice} as a {orderEvent.Direction} order. Order type: {order.type}")

    def OnEndOfAlgorithm(self):
        for symbol in self.symbols:
            for key, signals in self.indicator_signal_lists[symbol].items():
                buy_count = signals.count("BUY")
                sell_count = signals.count("SELL")
                self.debug(f"{symbol.Value} {key} signals - BUY: {buy_count}, SELL: {sell_count}")
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
                
                trailing_stop_exit_pct = 0
                if count > 0 and "trailing_stop_exits" in stats:
                    trailing_stop_exit_pct = (stats["trailing_stop_exits"] / count) * 100
                    
                self.debug(f"{symbol.Value} Trade Stats for combination [{combo}] - Count: {count}, Win Rate: {win_rate:.2f}%, "
                           f"Avg % Return: {avg_return:.2f}%, Total PnL: {stats['total_pnl']:.2f}, "
                           f"Avg Duration (hrs): {avg_duration:.2f}, Max Return: {stats['max_return']}, "
                           f"Min Return: {stats['min_return']}, Std Dev: {std_dev:.2f}, "
                           f"Trailing Stop Exits: {stats.get('trailing_stop_exits', 0)} ({trailing_stop_exit_pct:.2f}%)")
