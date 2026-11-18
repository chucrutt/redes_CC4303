import socket
import sys

from router import create_packet

# Envía un paquete IP a la dirección (IP_envío, puerto_envío).
# Uso: python3 enviar.py "IP_router_final;puerto_router_final;TTL" "mensaje" IP_envío puerto_envío
# Ejemplo: python3 enviar.py "127.0.0.1;8885;10" "hola R5" 127.0.0.1 8881
if len(sys.argv) != 5:
    print('Uso: python3 enviar.py "IP_final;puerto_final;TTL" "mensaje" IP_envío puerto_envío')
    sys.exit(1)

final_ip, final_port, ttl = sys.argv[1].split(";")
message = sys.argv[2]
send_address = (sys.argv[3], int(sys.argv[4]))

packet = create_packet({"ip": final_ip, "port": int(final_port), "ttl": int(ttl), "message": message})
sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sender_socket.sendto(packet, send_address)
sender_socket.close()
