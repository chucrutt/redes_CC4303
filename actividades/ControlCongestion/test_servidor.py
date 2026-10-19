import sys

import SocketTCP

MODE = sys.argv[1] if len(sys.argv) > 1 else "go_back_n"

address = ("localhost", int(sys.argv[2]) if len(sys.argv) > 2 else 8000)

server_socketTCP = SocketTCP.SocketTCP()
server_socketTCP.bind(address)
connection_socketTCP, new_address = server_socketTCP.accept()

# test 1
buff_size = 16
full_message = connection_socketTCP.recv(buff_size, mode=MODE)
print("Test 1 received:", full_message)
if full_message == "Mensje de len=16".encode(): print("Test 1: Passed")
else: print("Test 1: Failed")

# test 2
buff_size = 19
full_message = connection_socketTCP.recv(buff_size, mode=MODE)
print("Test 2 received:", full_message)
if full_message == "Mensaje de largo 19".encode(): print("Test 2: Passed")
else: print("Test 2: Failed")

# test 3
buff_size = 14
message_part_1 = connection_socketTCP.recv(buff_size, mode=MODE)
message_part_2 = connection_socketTCP.recv(buff_size, mode=MODE)
print("Test 3 received:", message_part_1 + message_part_2)
if (message_part_1 + message_part_2) == "Mensaje de largo 19".encode(): print("Test 3: Passed")
else: print("Test 3: Failed")

# test 4: mensaje de 2n bytes recibido con dos recv(n), con n = 21 (no múltiplo de 16)
n = 21
message_part_1 = connection_socketTCP.recv(n, mode=MODE)
message_part_2 = connection_socketTCP.recv(n, mode=MODE)
print("Test 4 received:", message_part_1, message_part_2)
expected = "Primera mitad de 21 b" "Segunda mitad de 21 b"
if len(message_part_1) == n and (message_part_1 + message_part_2) == expected.encode(): print("Test 4: Passed")
else: print("Test 4: Failed")

# cierre
connection_socketTCP.recv_close()
print("Conexión cerrada")
