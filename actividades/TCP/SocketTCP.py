import random
import socket
import sys
import time

SEQ_DIGITS = 10
HEADER_SIZE = len("0|0|0|" + "0" * SEQ_DIGITS + "|")
MAX_DATA_SIZE = 16
UDP_BUFFER_SIZE = HEADER_SIZE + MAX_DATA_SIZE

TIMEOUT = 1.5
MAX_CLOSE_TIMEOUTS = 3
LAST_ACK_REPETITIONS = 3

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
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
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

    def _send_segment(self, segment, address=None):
        """Envía un segmento por UDP."""
        if address is None:
            address = self.destination_address
        self.udp_socket.sendto(self.create_segment(segment), address)

    def _recv_segment(self):
        """Recibe un segmento; primero entrega los que quedaron pendientes.

        Retorna (None, address) si el segmento no se puede interpretar.
        Lanza socket.timeout si se cumple el timeout del socket.
        """
        if self.pending_segments:
            return self.pending_segments.pop(0)
        raw_segment, address = self.udp_socket.recvfrom(UDP_BUFFER_SIZE)
        try:
            return self.parse_segment(raw_segment), address
        except ValueError:
            return None, address

    def _send_ack(self, seq):
        self._send_segment(self._segment(ack=True, seq=seq))

    def _handle_unexpected(self, segment):
        """Responde segmentos fuera de lugar que indican que se perdió un ACK."""
        if segment["syn"] and segment["ack"] and self.handshake_ack_seq is not None:
            # La contraparte no recibió el último ACK del handshake.
            debug(f"Recibido {describe(segment)} repetido, reenviando ACK del handshake")
            self._send_ack(self.handshake_ack_seq)
        elif not (segment["syn"] or segment["ack"] or segment["fin"]) and self.expected_seq is not None:
            # Datos ya recibidos: se perdió nuestro ACK, así que se repite.
            debug(f"Recibido {describe(segment)} duplicado, reenviando ACK seq={self.expected_seq}")
            self._send_ack(self.expected_seq)
        else:
            debug(f"Ignorando {describe(segment)}")

    def bind(self, address):
        self.udp_socket.bind(address)
        self.local_address = address

    def connect(self, address):
        """Lado del cliente del 3-way handshake."""
        initial_seq = random.randint(0, 100)
        syn = self._segment(syn=True, seq=initial_seq)
        self.udp_socket.settimeout(TIMEOUT)

        while True:
            debug(f"Enviando {describe(syn)} a {address}")
            self._send_segment(syn, address)
            try:
                # Se ignora todo lo que no sea el SYN+ACK esperado.
                while True:
                    syn_ack, server_address = self._recv_segment()
                    if syn_ack is not None and syn_ack["syn"] and syn_ack["ack"] and syn_ack["seq"] == initial_seq + 1:
                        break
                break
            except socket.timeout:
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
        self.udp_socket.settimeout(None)
        while True:
            syn, client_address = self._recv_segment()
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
        connection.udp_socket.settimeout(TIMEOUT)

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
                break
            except socket.timeout:
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

    def _send_reliable(self, data):
        """Envía un segmento de datos con Stop & Wait."""
        segment = self._segment(seq=self.seq, data=data)
        expected_ack = self.seq + len(data)
        self.udp_socket.settimeout(TIMEOUT)

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
                break
            except socket.timeout:
                debug(f"Timeout esperando ACK seq={expected_ack}, retransmitiendo")
        self.seq = expected_ack

    def send(self, message):
        """Envía el largo del mensaje y luego el mensaje en trozos de 16 bytes."""
        self._send_reliable(str(len(message)).encode())
        for start in range(0, len(message), MAX_DATA_SIZE):
            self._send_reliable(message[start:start + MAX_DATA_SIZE])

    def _recv_reliable(self):
        """Recibe el siguiente segmento de datos en orden y lo confirma."""
        self.udp_socket.settimeout(None)
        while True:
            segment, _ = self._recv_segment()
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

    def recv(self, buff_size):
        """Retorna a lo más buff_size bytes del mensaje que envía la contraparte."""
        if self.message_pending == 0:
            # Comienza un mensaje nuevo: su primer segmento trae el largo.
            self.message_pending = int(self._recv_reliable().decode())

        target = min(self.message_pending, buff_size)
        while len(self.recv_buffer) < target:
            self.recv_buffer += self._recv_reliable()

        # Lo que sobra queda guardado para la siguiente llamada a recv.
        data = self.recv_buffer[:target]
        self.recv_buffer = self.recv_buffer[target:]
        self.message_pending -= target
        return data

    def close(self):
        """Cierre de conexión desde el lado que lo inicia (Host A)."""
        fin = self._segment(fin=True, seq=self.seq)
        fin_ack = None
        timeouts = 0
        self.udp_socket.settimeout(TIMEOUT)

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
            except socket.timeout:
                timeouts += 1
                debug(f"Timeout {timeouts}/{MAX_CLOSE_TIMEOUTS} esperando FIN+ACK")

        if fin_ack is None:
            debug("No llegó FIN+ACK, se asume que la contraparte cerró")
            self.udp_socket.close()
            return

        last_ack = self._segment(ack=True, seq=self.seq + 2)
        debug(f"Recibido {describe(fin_ack)}, enviando {describe(last_ack)} {LAST_ACK_REPETITIONS} veces")
        for repetition in range(LAST_ACK_REPETITIONS):
            if repetition > 0:
                time.sleep(TIMEOUT)
            self._send_segment(last_ack)
        debug("Conexión cerrada")
        self.udp_socket.close()

    def recv_close(self):
        """Cierre de conexión desde el lado que recibe el FIN (Host B)."""
        self.udp_socket.settimeout(None)
        while True:
            fin, _ = self._recv_segment()
            if fin is None:
                continue
            if fin["fin"] and not fin["ack"]:
                break
            self._handle_unexpected(fin)

        debug(f"Recibido {describe(fin)}")
        fin_ack = self._segment(fin=True, ack=True, seq=fin["seq"] + 1)
        last_ack = None
        timeouts = 0
        self.udp_socket.settimeout(TIMEOUT)

        while last_ack is None and timeouts < MAX_CLOSE_TIMEOUTS:
            debug(f"Enviando {describe(fin_ack)}")
            self._send_segment(fin_ack)
            try:
                while True:
                    segment, _ = self._recv_segment()
                    if segment is not None and segment["ack"] and not segment["fin"] and segment["seq"] == fin["seq"] + 2:
                        last_ack = segment
                        break
            except socket.timeout:
                timeouts += 1
                debug(f"Timeout {timeouts}/{MAX_CLOSE_TIMEOUTS} esperando el último ACK")

        if last_ack is None:
            debug("No llegó el último ACK, se asume que la contraparte cerró")
        else:
            debug(f"Recibido {describe(last_ack)}, conexión cerrada")
        self.udp_socket.close()
