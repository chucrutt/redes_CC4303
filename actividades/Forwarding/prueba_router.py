import socket
import sys

from router import create_packet

# Lee un archivo desde entrada estándar y envía cada línea como un paquete IP.
# Uso: python3 prueba_router.py "IP_final;puerto_final;TTL" IP_router_inicial puerto_router_inicial < archivo.txt
# El primer argumento va entre comillas porque en bash ";" separa comandos.
if len(sys.argv) != 4:
    print('Uso: python3 prueba_router.py "IP_final;puerto_final;TTL" IP_router_inicial puerto_router_inicial < archivo')
    sys.exit(1)

final_ip, final_port, ttl = sys.argv[1].split(";")
first_router_address = (sys.argv[2], int(sys.argv[3]))

sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for line in sys.stdin.read().splitlines():
    packet = create_packet({"ip": final_ip, "port": int(final_port), "ttl": int(ttl), "message": line})
    sender_socket.sendto(packet, first_router_address)
sender_socket.close()
