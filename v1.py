from AlgorithmImports import *
import math

# Global parameters (constants can be kept in uppercase)
SYMBOL = "ORCL"
START_DATE = "2024-01-01"
END_DATE = "2025-01-01"
INITIAL_CASH = 100000
TRIGGER_WINDOW = 1
REQUIRED_SIGNALS = 1
VOLUME_SPIKE_MULTIPLIER = 2
VOLUME_LOOKBACK = 25
TRADE_ALLOCATION = 0.1

# Indicator parameters
MA_FAST_PERIOD = 9
MA_SLOW_PERIOD = 20

STOCH_PERIOD = 14
STOCH_SMOOTH_K = 3
STOCH_SMOOTH_D = 3
STOCH_UPPER = 80
STOCH_LOWER = 20
STOCH_LOOKBACK = 3

MFI_PERIOD = 14
MFI_UPPER = 80
MFI_LOWER = 20

MACD_FAST = 3
MACD_SLOW = 10
MACD_SIGNAL = 16

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
        self.enable_stoch = False
        self.enable_lbr = False
        self.enable_mfi = False
        self.enable_vol = False

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
        stochrsi_chart.add_series(Series("K Value", SeriesType.LINE, "$", Color.ORANGE))
        stochrsi_chart.add_series(Series("D Value", SeriesType.LINE, "$", Color.BLUE))
        self.AddChart(stochrsi_chart)

        lbrosc_chart = Chart("LBROSC")
        lbrosc_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
        lbrosc_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
        lbrosc_chart.add_series(Series("MACD Value", SeriesType.LINE, "$", Color.ORANGE))
        lbrosc_chart.add_series(Series("MACD Signal Value", SeriesType.LINE, "$", Color.BLUE))
        self.AddChart(lbrosc_chart)

        mfi_chart = Chart("MFI")
        mfi_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
        mfi_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
        mfi_chart.add_series(Series("MFI Value", SeriesType.LINE, "$", Color.ORANGE))
        self.AddChart(mfi_chart)

        volume_chart = Chart("VOLUME")
        volume_chart.add_series(Series("Buy Signal", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
        volume_chart.add_series(Series("Sell Signal", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
        volume_chart.add_series(Series("Volume", SeriesType.LINE, "$", Color.ORANGE))
        volume_chart.add_series(Series("SMA Volume * Multiplier", SeriesType.LINE, "$", Color.ORANGE))
        self.AddChart(volume_chart)

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
        
        invested = self.Portfolio[self._symbol].Invested

        if not self.IsWarmingUp:
            net_signal = self.calculate_net_signal_value()
            if not invested and net_signal >= REQUIRED_SIGNALS:
                self.SetHoldings(self._symbol, TRADE_ALLOCATION)
                self.Debug(f"Entered trade on {self._symbol} for Net Signal {net_signal}. Active signals: {self.active_signals}")
            elif invested and net_signal <= -REQUIRED_SIGNALS:
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
        buy_count = 0
        sell_count = 0
        active_signals = []

        for indicator in self.indicator_signal_lists:
            for i in range(TRIGGER_WINDOW):
                if self.indicator_signal_lists[indicator][-(i+1)] == "BUY":
                    buy_count += 1
                    active_signals.append(f"{indicator}:BUY")
                    break
                elif self.indicator_signal_lists[indicator][-(i+1)] == "SELL":
                    sell_count += 1
                    active_signals.append(f"{indicator}:SELL")
                    break

        self.active_signals = active_signals
        return buy_count - sell_count

    def OnEndOfAlgorithm(self):
        # Log the final counts for each indicator's signals
        for key, signal_list in self.indicator_signal_lists.items():
            buy_count = signal_list.count("BUY")
            sell_count = signal_list.count("SELL")
            self.Debug(f"{key} signals - BUY: {buy_count}, SELL: {sell_count}")