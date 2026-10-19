#!/bin/bash
# Compara Go-Back-N con y sin control de congestión.
# Antes de ejecutar: sudo tc qdisc add dev lo root netem loss 20.0%
# y en SocketTCP.py: TIMEOUT = 0.5 y DEBUG = False.
# Uso: bash experimento.sh <archivo> [repeticiones]
archivo=$1
repeticiones=${2:-5}
puerto=9500

for modo in con sin; do
    echo "Go-Back-N $modo control de congestión ($archivo)"
    for i in $(seq 1 "$repeticiones"); do
        puerto=$((puerto + 2))
        python3 servidor.py localhost $puerto go_back_n > recibido.txt 2> servidor.log &
        sleep 0.3
        if [ $modo = con ]; then
            python3 cliente.py localhost $puerto go_back_n < "$archivo" 2> cliente.log
        else
            python3 cliente.py localhost $puerto go_back_n --sin-cc < "$archivo" 2> cliente.log
        fi
        wait
        if cmp -s "$archivo" recibido.txt; then integro=si; else integro=no; fi
        echo "$i: $(grep STATS cliente.log) | $(grep STATS servidor.log) | íntegro=$integro"
    done
    echo
done
rm -f recibido.txt servidor.log cliente.log
