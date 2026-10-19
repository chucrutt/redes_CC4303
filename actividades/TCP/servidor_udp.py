import socket
import sys

import SocketTCP

ADDRESS = ("localhost", 8000)
USE_HEADERS = len(sys.argv) > 1 and sys.argv[1] == "--headers"
BUFFER_SIZE = SocketTCP.HEADER_SIZE + 16 if USE_HEADERS else 16

server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind(ADDRESS)

while True:
    message, _ = server_socket.recvfrom(BUFFER_SIZE)
    if USE_HEADERS:
        message = SocketTCP.SocketTCP.parse_segment(message)["data"]
    print(message.decode(errors="replace"), end="", flush=True)
