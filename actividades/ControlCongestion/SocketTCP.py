import random
import sys
import time

from CongestionControl import CongestionControl
from slidingWindowCC import SlidingWindowCC
from socketUDP import SocketUDP

# Header TCP simplificado en texto: "SYN|ACK|FIN|SEQ|", con cada flag igual a
# "0" o "1" y SEQ escrito con 10 dígitos, por ejemplo "1|0|0|0000000042|".
# Como todos los headers tienen el mismo largo, los datos empiezan siempre en
# la posición HEADER_SIZE del segmento.
SEQ_DIGITS = 10
HEADER_SIZE = len("0|0|0|" + "0" * SEQ_DIGITS + "|")
MAX_DATA_SIZE = 16
# El socket UDP interno solo necesita espacio para un segmento completo.
UDP_BUFFER_SIZE = HEADER_SIZE + MAX_DATA_SIZE

TIMEOUT = 1.5
MAX_CLOSE_TIMEOUTS = 3
LAST_ACK_REPETITIONS = 3

# Go-Back-N: ventana fija sin control de congestión y MSS con control.
GO_BACK_N_WINDOW_SIZE = 8
GO_BACK_N_MSS = 8

# Timers de SocketUDP: el 0 mide los timeouts de los datos. SocketUDP inicia
# un timer en cada sendto, así que los ACK usan el timer 1 y lo detienen
# apenas se envían, porque un ACK no espera respuesta.
DATA_TIMER = 0
ACK_TIMER = 1

DEBUG = True


def debug(message):
    """Imprime mensajes de debug en stderr para no mezclarlos con los datos."""
    if DEBUG:
        print(f"(debug) {message}", file=sys.stderr, flush=True)


def describe(segment):
    """Representa un segmento de forma corta para el modo debug."""
    flags = []
    if segment["syn"]:
        flags.append("SYN")
    if segment["fin"]:
        flags.append("FIN")
    if segment["ack"]:
        flags.append("ACK")
    if not flags:
        flags.append("DATA")
    text = f"[{'+'.join(flags)} seq={segment['seq']}"
    if segment["data"]:
        text += f" data={segment['data']!r}"
    return text + "]"


class SocketTCP:
    def __init__(self):
        self.socketUDP = SocketUDP()
        self.socketUDP.settimeout(TIMEOUT)
        self.socketUDP.set_timer_list_length(2)
        # Indica si el timer de datos está corriendo (o ya venció) y hay que
        # detenerlo antes de volver a usarlo.
        self.data_timer_on = False
        self.local_address = None
        self.destination_address = None
        # Próximo número de secuencia que este socket enviará.
        self.seq = None
        # Próximo número de secuencia que se espera recibir de la contraparte.
        self.expected_seq = None
        # Seq del ACK final del handshake, por si hay que reenviarlo.
        self.handshake_ack_seq = None
        # Bytes del mensaje actual que todavía no se entregan con recv.
        self.message_pending = 0
        # Bytes ya recibidos que no cupieron en el buff_size de recv.
        self.recv_buffer = b""
        # Segmentos recibidos antes de tiempo (ACK implícito del handshake).
        self.pending_segments = []
        # Conexiones ya aceptadas, para ignorar SYN retransmitidos.
        self.accepted_connections = []
        # Control de congestión de Go-Back-N.
        self.congestion_controler = CongestionControl(GO_BACK_N_MSS)
        self.congestion_control_on = True
        # Cantidad de segmentos enviados por este socket (incluye retransmisiones y ACKs).
        self.number_of_sent_segments = 0

    def set_congestion_control(self, congestion_control_on):
        self.congestion_control_on = congestion_control_on

    @staticmethod
    def parse_segment(segment):
        """Convierte un segmento en bytes a un diccionario."""
        if len(segment) < HEADER_SIZE:
            raise ValueError("El segmento es más corto que el header")
        header = segment[:HEADER_SIZE].decode()
        syn, ack, fin, seq, _ = header.split("|")
        return {
            "syn": syn == "1",
            "ack": ack == "1",
            "fin": fin == "1",
            "seq": int(seq),
            "data": segment[HEADER_SIZE:],
        }

    @staticmethod
    def create_segment(parsed_segment):
        """Convierte un diccionario como el de parse_segment a bytes."""
        syn = "1" if parsed_segment.get("syn") else "0"
        ack = "1" if parsed_segment.get("ack") else "0"
        fin = "1" if parsed_segment.get("fin") else "0"
        seq = str(parsed_segment.get("seq", 0) % 10**SEQ_DIGITS).zfill(SEQ_DIGITS)
        data = parsed_segment.get("data", b"")
        if len(data) > MAX_DATA_SIZE:
            raise ValueError(f"Un segmento lleva a lo más {MAX_DATA_SIZE} bytes de datos")
        header = f"{syn}|{ack}|{fin}|{seq}|"
        return header.encode() + data

    @staticmethod
    def _segment(syn=False, ack=False, fin=False, seq=0, data=b""):
        return {"syn": syn, "ack": ack, "fin": fin, "seq": seq, "data": data}

    @staticmethod
    def divide_message(message, chunk_size):
        chunks = []
        for start in range(0, len(message), chunk_size):
            chunks.append(message[start:start + chunk_size])
        return chunks

    def _send_segment(self, segment, address=None):
        """Envía un segmento que espera respuesta e inicia el timer de datos.

        Si el timer ya estaba corriendo, SocketUDP no lo reinicia.
        """
        if address is None:
            address = self.destination_address
        self.number_of_sent_segments += 1
        self.socketUDP.sendto(self.create_segment(segment), address, timer_index=DATA_TIMER)
        self.data_timer_on = True

    def _send_ack(self, seq):
        """Envía un ACK. Como no espera respuesta, su timer se detiene de inmediato."""
        segment = self._segment(ack=True, seq=seq)
        self.number_of_sent_segments += 1
        self.socketUDP.sendto(self.create_segment(segment), self.destination_address, timer_index=ACK_TIMER)
        self.socketUDP.stop_timer(ACK_TIMER)

    def _stop_data_timer(self):
        if self.data_timer_on:
            self.socketUDP.stop_timer(DATA_TIMER)
            self.data_timer_on = False

    def _recv_segment(self):
        """Recibe un segmento; primero entrega los que quedaron pendientes.

        Retorna (None, address) si el segmento no se puede interpretar.
        Lanza TimeoutError si vence un timer.
        """
        if self.pending_segments:
            return self.pending_segments.pop(0)
        raw_segment, address = self.socketUDP.recvfrom(UDP_BUFFER_SIZE)
        try:
            return self.parse_segment(raw_segment), address
        except ValueError:
            return None, address

    def _recv_segment_without_timer(self):
        """Recibe un segmento cuando no se espera ningún timeout."""
        while True:
            try:
                return self._recv_segment()
            except TimeoutError:
                # Un timer que quedó corriendo no debe interrumpir la espera.
                self._stop_data_timer()

    def _handle_unexpected(self, segment):
        """Responde segmentos fuera de lugar que indican que se perdió un ACK."""
        if segment["syn"] and segment["ack"] and self.handshake_ack_seq is not None:
            # La contraparte no recibió el último ACK del handshake.
            debug(f"Recibido {describe(segment)} repetido, reenviando ACK del handshake")
            self._send_ack(self.handshake_ack_seq)
        elif not (segment["syn"] or segment["ack"] or segment["fin"]) and self.expected_seq is not None:
            # Datos repetidos o fuera de orden: se repite el ACK acumulado.
            debug(f"Recibido {describe(segment)} fuera de orden, reenviando ACK seq={self.expected_seq}")
            self._send_ack(self.expected_seq)
        else:
            debug(f"Ignorando {describe(segment)}")

    def bind(self, address):
        self.socketUDP.bind(address)
        self.local_address = address

    def connect(self, address):
        """Lado del cliente del 3-way handshake."""
        initial_seq = random.randint(0, 100)
        syn = self._segment(syn=True, seq=initial_seq)

        while True:
            debug(f"Enviando {describe(syn)} a {address}")
            self._send_segment(syn, address)
            try:
                # Se ignora todo lo que no sea el SYN+ACK esperado.
                while True:
                    syn_ack, server_address = self._recv_segment()
                    if syn_ack is not None and syn_ack["syn"] and syn_ack["ack"] and syn_ack["seq"] == initial_seq + 1:
                        break
                self._stop_data_timer()
                break
            except TimeoutError:
                self._stop_data_timer()
                debug("Timeout esperando SYN+ACK, retransmitiendo SYN")

        # El SYN+ACK viene desde el nuevo socket creado por accept.
        self.destination_address = server_address
        self.handshake_ack_seq = initial_seq + 2
        self.seq = self.handshake_ack_seq
        self.expected_seq = self.handshake_ack_seq
        debug(f"Recibido {describe(syn_ack)} desde {server_address}, enviando ACK seq={self.seq}")
        self._send_ack(self.handshake_ack_seq)

    def accept(self):
        """Lado del servidor del 3-way handshake."""
        while True:
            syn, client_address = self._recv_segment_without_timer()
            if syn is None or not syn["syn"] or syn["ack"]:
                continue
            if (client_address, syn["seq"]) in self.accepted_connections:
                debug(f"Ignorando {describe(syn)} de una conexión ya aceptada")
                continue
            break

        initial_seq = syn["seq"]
        debug(f"Recibido {describe(syn)} desde {client_address}")

        # El nuevo socket usa el primer puerto libre después del que escucha.
        connection = SocketTCP()
        new_port = self.local_address[1] + 1
        while True:
            try:
                connection.bind((self.local_address[0], new_port))
                break
            except OSError:
                new_port += 1
        connection.destination_address = client_address
        connection.congestion_control_on = self.congestion_control_on

        syn_ack = self._segment(syn=True, ack=True, seq=initial_seq + 1)
        handshake_ack_seq = initial_seq + 2

        while True:
            debug(f"Enviando {describe(syn_ack)} desde {connection.local_address}")
            connection._send_segment(syn_ack)
            try:
                # Cualquier segmento sin SYN con seq inicial+2 confirma el
                # handshake: el ACK final, o el primer segmento de datos si
                # ese ACK se perdió.
                while True:
                    confirmation, _ = connection._recv_segment()
                    if confirmation is not None and not confirmation["syn"] and confirmation["seq"] == handshake_ack_seq:
                        break
                connection._stop_data_timer()
                break
            except TimeoutError:
                connection._stop_data_timer()
                debug("Timeout esperando ACK del handshake, retransmitiendo SYN+ACK")

        if confirmation["ack"] and not confirmation["data"]:
            debug(f"Recibido {describe(confirmation)}, handshake completo")
        else:
            # ACK implícito: el segmento se guarda para que recv lo procese.
            debug(f"Recibido {describe(confirmation)} sin ACK previo, se asume el ACK perdido")
            connection.pending_segments.append((confirmation, client_address))

        connection.seq = handshake_ack_seq
        connection.expected_seq = handshake_ack_seq
        self.accepted_connections.append((client_address, initial_seq))
        return connection, connection.local_address

    def send(self, message, mode="stop_and_wait"):
        if mode == "stop_and_wait":
            self.send_using_stop_and_wait(message)
        elif mode == "go_back_n":
            self.send_using_go_back_n(message)
        else:
            raise ValueError(f"Modo desconocido: {mode}")

    def recv(self, buff_size, mode="stop_and_wait"):
        if mode == "stop_and_wait":
            return self.recv_using_stop_and_wait(buff_size)
        if mode == "go_back_n":
            return self.recv_using_go_back_n(buff_size)
        raise ValueError(f"Modo desconocido: {mode}")

    def _send_reliable(self, data):
        """Envía un segmento de datos con Stop & Wait."""
        segment = self._segment(seq=self.seq, data=data)
        expected_ack = self.seq + len(data)

        while True:
            debug(f"Enviando {describe(segment)}")
            self._send_segment(segment)
            try:
                while True:
                    ack, _ = self._recv_segment()
                    if ack is None:
                        continue
                    if ack["ack"] and not ack["syn"] and not ack["fin"] and ack["seq"] == expected_ack:
                        break
                    self._handle_unexpected(ack)
                self._stop_data_timer()
                break
            except TimeoutError:
                self._stop_data_timer()
                debug(f"Timeout esperando ACK seq={expected_ack}, retransmitiendo")
        self.seq = expected_ack

    def send_using_stop_and_wait(self, message):
        """Envía el largo del mensaje y luego el mensaje en trozos de 16 bytes."""
        self._send_reliable(str(len(message)).encode())
        for chunk in self.divide_message(message, MAX_DATA_SIZE):
            self._send_reliable(chunk)

    def _debug_congestion(self, event, window_size):
        if not self.congestion_control_on:
            return
        cc = self.congestion_controler
        if cc.is_state_slow_start():
            state = "slow start"
        else:
            state = "congestion avoidance"
        debug(
            f"[CC] {event}: estado={state}, cwnd={cc.get_cwnd():g} B, "
            f"ssthresh={cc.get_ssthresh()}, window_size={window_size}"
        )

    @staticmethod
    def _window_end(data_window):
        """Seq siguiente al último elemento con datos de la ventana."""
        end = None
        for index in range(data_window.window_size):
            data = data_window.get_data(index)
            if data is None:
                break
            end = data_window.get_sequence_number(index) + len(data)
        return end

    def _send_window_from(self, data_window, first_seq):
        """Envía los elementos de la ventana con seq >= first_seq.

        Retorna el seq siguiente al último elemento enviado.
        """
        next_seq = first_seq
        for index in range(data_window.window_size):
            data = data_window.get_data(index)
            if data is None:
                break
            seq = data_window.get_sequence_number(index)
            if seq < first_seq:
                continue
            segment = self._segment(seq=seq, data=data)
            debug(f"Enviando {describe(segment)}")
            self._send_segment(segment)
            next_seq = seq + len(data)
        return next_seq

    @staticmethod
    def _acked_steps(data_window, ack_seq):
        """Cantidad de elementos al inicio de la ventana confirmados por ack_seq."""
        steps = 0
        for index in range(data_window.window_size):
            data = data_window.get_data(index)
            if data is None or data_window.get_sequence_number(index) + len(data) > ack_seq:
                break
            steps = index + 1
        return steps

    def send_using_go_back_n(self, message):
        """Envía el mensaje con Go-Back-N y, opcionalmente, control de congestión."""
        message_length = str(len(message)).encode()
        data_list = [message_length] + self.divide_message(message, GO_BACK_N_MSS)
        final_seq = self.seq
        for data in data_list:
            final_seq += len(data)

        if self.congestion_control_on:
            window_size = self.congestion_controler.get_MSS_in_cwnd()
        else:
            window_size = GO_BACK_N_WINDOW_SIZE
        data_window = SlidingWindowCC(window_size, data_list, self.seq)
        self._debug_congestion("inicio", window_size)

        # El timer de datos parte con el primer segmento enviado y cubre a
        # todos los segmentos de la ventana que aún no se confirman.
        next_seq_to_send = self._send_window_from(data_window, self.seq)

        while data_window.get_data(0) is not None:
            try:
                ack, _ = self._recv_segment()
            except TimeoutError:
                # Timeout: se reenvía la ventana completa (Go-Back-N).
                self._stop_data_timer()
                base_seq = data_window.get_sequence_number(0)
                debug(f"Timeout esperando ACK de seq={base_seq}, retransmitiendo la ventana")
                if self.congestion_control_on:
                    self.congestion_controler.event_timeout()
                    window_size = self.congestion_controler.get_MSS_in_cwnd()
                    data_window.update_window_size(window_size)
                    self._debug_congestion("timeout", window_size)
                next_seq_to_send = self._send_window_from(data_window, base_seq)
                continue

            if ack is None:
                continue
            base_seq = data_window.get_sequence_number(0)
            is_new_ack = ack["ack"] and not ack["syn"] and not ack["fin"] and base_seq < ack["seq"] <= final_seq
            if not is_new_ack:
                self._handle_unexpected(ack)
                continue

            debug(f"Recibido {describe(ack)}")
            # Si la ventana se achicó, el ACK puede confirmar elementos que ya no
            # están en ella: se avanza la ventana completa hasta alcanzarlo.
            moves = 0
            while True:
                steps = self._acked_steps(data_window, ack["seq"])
                if steps == 0:
                    break
                data_window.move_window(steps)
                moves += 1
            if moves > 1:
                debug(f"ACK seq={ack['seq']} más allá de la ventana, se avanzó {moves} veces")

            if self.congestion_control_on:
                self.congestion_controler.event_ack_received()
                window_size = self.congestion_controler.get_MSS_in_cwnd()
                data_window.update_window_size(window_size)
                self._debug_congestion("ACK", window_size)

            if data_window.get_data(0) is None:
                break
            # Los elementos que entraron a la ventana se envían seguidos. Si hay
            # nuevos envíos se reinicia el timer; si no, sigue corriendo.
            if self._window_end(data_window) > next_seq_to_send:
                self._stop_data_timer()
                first_seq = max(next_seq_to_send, data_window.get_sequence_number(0))
                next_seq_to_send = self._send_window_from(data_window, first_seq)

        self._stop_data_timer()
        self.seq = final_seq

    def _recv_in_order(self):
        """Recibe el siguiente segmento de datos en orden y lo confirma.

        Los segmentos repetidos o fuera de orden se descartan y se responde
        con el ACK acumulado, lo que sirve tanto para Stop & Wait como para
        Go-Back-N.
        """
        while True:
            segment, _ = self._recv_segment_without_timer()
            if segment is None:
                continue
            is_data = not (segment["syn"] or segment["ack"] or segment["fin"])
            if is_data and segment["seq"] == self.expected_seq:
                break
            self._handle_unexpected(segment)

        self.expected_seq += len(segment["data"])
        debug(f"Recibido {describe(segment)}, enviando ACK seq={self.expected_seq}")
        self._send_ack(self.expected_seq)
        return segment["data"]

    def _recv_message(self, buff_size):
        if self.message_pending == 0:
            # Comienza un mensaje nuevo: su primer segmento trae el largo.
            self.message_pending = int(self._recv_in_order().decode())

        target = min(self.message_pending, buff_size)
        while len(self.recv_buffer) < target:
            self.recv_buffer += self._recv_in_order()

        # Lo que sobra queda guardado para la siguiente llamada a recv.
        data = self.recv_buffer[:target]
        self.recv_buffer = self.recv_buffer[target:]
        self.message_pending -= target
        return data

    def recv_using_stop_and_wait(self, buff_size):
        """Retorna a lo más buff_size bytes del mensaje que envía la contraparte."""
        return self._recv_message(buff_size)

    def recv_using_go_back_n(self, buff_size):
        """El receptor de Go-Back-N es igual al de Stop & Wait: acepta solo el
        segmento esperado y responde siempre con el ACK acumulado."""
        return self._recv_message(buff_size)

    def _close_socket(self):
        self._stop_data_timer()
        self.socketUDP.close()

    def close(self):
        """Cierre de conexión desde el lado que lo inicia (Host A)."""
        fin = self._segment(fin=True, seq=self.seq)
        fin_ack = None
        timeouts = 0

        while fin_ack is None and timeouts < MAX_CLOSE_TIMEOUTS:
            debug(f"Enviando {describe(fin)}")
            self._send_segment(fin)
            try:
                while True:
                    segment, _ = self._recv_segment()
                    if segment is None:
                        continue
                    if segment["fin"] and segment["ack"] and segment["seq"] == self.seq + 1:
                        fin_ack = segment
                        break
                    self._handle_unexpected(segment)
                self._stop_data_timer()
            except TimeoutError:
                self._stop_data_timer()
                timeouts += 1
                debug(f"Timeout {timeouts}/{MAX_CLOSE_TIMEOUTS} esperando FIN+ACK")

        if fin_ack is None:
            debug("No llegó FIN+ACK, se asume que la contraparte cerró")
            self._close_socket()
            return

        debug(f"Recibido {describe(fin_ack)}, enviando [ACK seq={self.seq + 2}] {LAST_ACK_REPETITIONS} veces")
        for repetition in range(LAST_ACK_REPETITIONS):
            if repetition > 0:
                time.sleep(TIMEOUT)
            self._send_ack(self.seq + 2)
        debug("Conexión cerrada")
        self._close_socket()

    def recv_close(self):
        """Cierre de conexión desde el lado que recibe el FIN (Host B)."""
        while True:
            fin, _ = self._recv_segment_without_timer()
            if fin is None:
                continue
            if fin["fin"] and not fin["ack"]:
                break
            self._handle_unexpected(fin)

        debug(f"Recibido {describe(fin)}")
        fin_ack = self._segment(fin=True, ack=True, seq=fin["seq"] + 1)
        last_ack = None
        timeouts = 0

        while last_ack is None and timeouts < MAX_CLOSE_TIMEOUTS:
            debug(f"Enviando {describe(fin_ack)}")
            self._send_segment(fin_ack)
            try:
                while True:
                    segment, _ = self._recv_segment()
                    if segment is not None and segment["ack"] and not segment["fin"] and segment["seq"] == fin["seq"] + 2:
                        last_ack = segment
                        break
                self._stop_data_timer()
            except TimeoutError:
                self._stop_data_timer()
                timeouts += 1
                debug(f"Timeout {timeouts}/{MAX_CLOSE_TIMEOUTS} esperando el último ACK")

        if last_ack is None:
            debug("No llegó el último ACK, se asume que la contraparte cerró")
        else:
            debug(f"Recibido {describe(last_ack)}, conexión cerrada")
        self._close_socket()
