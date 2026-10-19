import socket
import sys

import SocketTCP

ADDRESS = ("localhost", 8000)
CHUNK_SIZE = 16
USE_HEADERS = len(sys.argv) > 1 and sys.argv[1] == "--headers"

file_path = input("Ruta del archivo: ")
with open(file_path, "rb") as file:
    content = file.read()

client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
seq = 0
for start in range(0, len(content), CHUNK_SIZE):
    chunk = content[start:start + CHUNK_SIZE]
    if USE_HEADERS:
        segment = SocketTCP.SocketTCP.create_segment({"seq": seq, "data": chunk})
        seq += len(chunk)
        chunk = segment
    client_socket.sendto(chunk, ADDRESS)
client_socket.close()
