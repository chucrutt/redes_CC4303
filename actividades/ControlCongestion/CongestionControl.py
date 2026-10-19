SLOW_START = "slow start"
CONGESTION_AVOIDANCE = "congestion avoidance"


class CongestionControl:
    """Maneja la ventana de congestión según TCP Tahoe (sin fast recovery)."""

    def __init__(self, MSS):
        self.MSS = MSS
        self.current_state = SLOW_START
        # La ventana de congestión se mide en bytes y parte en 1 MSS.
        self.cwnd = MSS
        # No se define hasta el primer timeout.
        self.ssthresh = None

    def get_cwnd(self):
        return self.cwnd

    def get_MSS_in_cwnd(self):
        """Cantidad de MSS completos que caben en la ventana de congestión."""
        # En congestion avoidance cwnd suma fracciones de MSS (por ejemplo 8/3)
        # y la suma puede quedar en 31.999...; se redondea antes de truncar.
        return int(round(self.cwnd / self.MSS, 6))

    def get_ssthresh(self):
        return self.ssthresh

    def is_state_slow_start(self):
        return self.current_state == SLOW_START

    def is_state_congestion_avoidance(self):
        return self.current_state == CONGESTION_AVOIDANCE

    def event_ack_received(self):
        if self.is_state_slow_start():
            self.cwnd += self.MSS
            # El cambio de estado solo es posible una vez definido ssthresh.
            if self.ssthresh is not None and self.cwnd >= self.ssthresh:
                self.current_state = CONGESTION_AVOIDANCE
        else:
            # Additive Increase: tras get_MSS_in_cwnd() ACKs se suma 1 MSS.
            self.cwnd += self.MSS / self.get_MSS_in_cwnd()

    def event_timeout(self):
        # Multiplicative Decrease: en ambos estados se vuelve a slow start.
        self.ssthresh = int(round(self.cwnd / 2, 6))
        self.cwnd = self.MSS
        self.current_state = SLOW_START
