## Paso 1: IP de la máquina virtual

Durante el desarrollo se utilizará temporalmente la dirección `127.0.0.1` como `IP_VM`.

## Paso 2: Recepción de mensajes DNS

El resolver se implementó en [resolver.py](resolver.py). El socket utiliza `AF_INET` para trabajar con direcciones IPv4 y `SOCK_DGRAM` para utilizar UDP, que es el tipo de socket apropiado para recibir consultas DNS en esta actividad.

El socket queda asociado a `(127.0.0.1, 8000)` y recibe mensajes continuamente mediante `recvfrom()` en un loop. Se utiliza un buffer de `65535` bytes y el mensaje se imprime directamente como `bytes`, sin aplicar `decode()`.

## Test: mensaje DNS sin procesar

Se ejecutó el resolver y, desde otra terminal, se realizó la consulta:

```bash
dig -p8000 @127.0.0.1 example.com
```

El resolver recibió e imprimió el mensaje sin procesarlo:

```text
b'\xc3\xab\x01 \x00\x01\x00\x00\x00\x00\x00\x01\x07example\x03com\x00\x00\x01\x00\x01\x00\x00)\x04\xd0\x00\x00\x00\x00\x00\x0c\x00\n\x00\x08\xe9\x1br\x8fW\xd6\xe6\xa1'
```

Como el resolver todavía no envía una respuesta, `dig` mostró tres mensajes `communications error ... timed out` correspondientes a sus reintentos y terminó indicando `no servers could be reached`. Este resultado es el esperado en este paso: el resolver puede recibir consultas DNS, pero aún no puede responderlas.

## Paso 3: Parseo de mensajes DNS

En [resolver.py](resolver.py) se implementó la función `parse_dns_message(message)`. La función interpreta el header mediante `struct`, obtiene el `QNAME` y los conteos `ANCOUNT`, `NSCOUNT` y `ARCOUNT`, y transforma las secciones `Answer`, `Authority` y `Additional` en listas de diccionarios.

Los nombres DNS se leen considerando etiquetas normales y punteros de compresión. Los registros `A`, `AAAA`, `NS`, `CNAME`, `PTR` y `MX` se convierten a una representación legible; para otros tipos se conserva el contenido de `RDATA` en hexadecimal. El resolver ahora imprime la estructura resultante en vez del mensaje crudo.

### Pruebas del parser

Se probó una consulta DNS para `example.com`. El resultado fue `qname = example.com.`, con `ANCOUNT = 0`, `NSCOUNT = 0`, `ARCOUNT = 0` y las tres secciones vacías.

También se probó una respuesta DNS sintética con un nombre comprimido y un registro `A`. El parser obtuvo:

```text
qname: example.com.
ancount: 1
answer: name=example.com., type=A, class=1, ttl=60, data=1.2.3.4
```

Esto confirma que la función puede leer tanto consultas como respuestas que contienen registros y compresión de nombres.

### Test de parte 3 con `dig`

Se ejecutó el resolver y se realizó nuevamente la consulta:

```bash
dig -p8000 @127.0.0.1 example.com
```

En cada reintento, `parse_dns_message` produjo una estructura equivalente a:

```text
{
	'qname': 'example.com.',
	'ancount': 0,
	'nscount': 0,
	'arcount': 1,
	'answer': [],
	'authority': [],
	'additional': [
		{
			'name': '.',
			'type': 41,
			'class': 1232,
			'ttl': 0,
			'data': '000a000876a593ddef621c96'
		}
	]
}
```

La consulta fue recibida y transformada correctamente. El registro de tipo 41 corresponde a la información `OPT` que `dig` agregó en la sección `Additional`; como todavía no se implementa el envío de respuestas, `dig` terminó mostrando `communications error ... timed out`, lo cual es esperado en esta parte.

## Paso 4: Resolver iterativo

Se implementó la función `resolver(mensaje_consulta: bytes, ip_addr=root_ip) -> bytes`. La resolución comienza enviando la consulta al servidor raíz `198.41.0.4` mediante UDP en el puerto 53.

- Si `Answer` contiene un registro `A`, se retorna el mensaje DNS completo recibido.
- Si `Authority` contiene un registro `NS`, se busca el primer registro `A` de `Additional` y se reenvía la consulta original a esa dirección.
- Si no hay una dirección en `Additional`, se crea una consulta `A` para el nombre del NS y se usa recursivamente `resolver` para obtener su dirección IP.
- Ante respuestas no soportadas, mensajes inválidos o errores de red, la función retorna `b""`.

El programa principal entrega cada mensaje recibido a `resolver` y envía al cliente la respuesta retornada cuando no está vacía.

Una limitación del caso d es que respuestas como `CNAME`, `AAAA`, `NXDOMAIN`, `SERVFAIL` o respuestas truncadas no se resuelven: se ignoran y el cliente no recibe respuesta. Además, esta implementación sigue solo el primer NS o la primera dirección `A`, por lo que no intenta alternativas si ese servidor no responde.

### Test del resolver

Se ejecutó el resolver y se consultó `example.com` con:

```bash
dig +time=2 +tries=1 -p8000 @127.0.0.1 example.com
```

La consulta fue resuelta correctamente. `dig` recibió `status: NOERROR` desde `127.0.0.1:8000` y obtuvo dos respuestas `A`:

```text
example.com.  300  IN  A  104.20.23.154
example.com.  300  IN  A  172.66.147.243
```

También se mostró la advertencia `recursion requested but not available`, porque el resolver no ofrece recursión mediante el bit `RA`; la resolución iterativa fue realizada por el código del paso 4.

Finalmente se probó con mensajes sintéticos una delegación sin glue `A`. El resolver consultó recursivamente la dirección del NS y luego reenvió la consulta original al servidor obtenido, completando la resolución correctamente.

### Comparación con Cloudflare

Se consultó la IP de `www.uchile.cl` directamente a Cloudflare:

```bash
dig @1.1.1.1 www.uchile.cl
```

El resultado fue:

```text
status: NOERROR
www.uchile.cl.  268  IN  A  200.89.76.36
Query time: 18 msec
```

Luego se repitió la consulta al resolver propio:

```bash
dig +time=5 +tries=1 -p8000 @127.0.0.1 www.uchile.cl
```

El resultado fue:

```text
status: NOERROR
www.uchile.cl.  300  IN  A  200.89.76.36
Query time: 156 msec
```

Ambos resolvers entregaron la misma dirección IPv4. Cloudflare respondió más rápido porque es un resolver recursivo con información posiblemente almacenada en caché, mientras que nuestro resolver recorrió la jerarquía DNS desde el servidor raíz. La respuesta propia incluyó las flags `qr aa rd` y la advertencia `recursion requested but not available`, ya que nuestro programa no implementa el bit `RA`. También se observó una diferencia en el TTL reportado: `268` segundos para Cloudflare y `300` segundos para la respuesta autoritativa obtenida por nuestro resolver.

## Paso 5: Modo debug

Se agregó la constante `DEBUG = True`. Antes de cada consulta interna, el resolver imprime el dominio consultado, el nombre del Name Server y su dirección IP.

### Test de parte 5

Se repitió la consulta:

```bash
dig +time=5 +tries=1 -p8000 @127.0.0.1 www.uchile.cl
```

El resolver mostró la siguiente cadena de consultas:

```text
(debug) Consultando 'www.uchile.cl.' a '.' con dirección IP '198.41.0.4'
(debug) Consultando 'www.uchile.cl.' a 'cl2-tld.d-zone.ca.' con dirección IP '185.159.198.56'
(debug) Consultando 'www.uchile.cl.' a 'ns1.uchile.cl.' con dirección IP '200.89.70.3'
```

La consulta terminó correctamente con `status: NOERROR` y la respuesta `www.uchile.cl. 300 IN A 200.89.76.36`. Esto confirma que el modo debug informa los saltos internos realizados por el resolver.

## Paso 6: Caché

Se agregó un caché en memoria. `query_history` conserva las últimas 20 consultas y `dns_cache` conserva la IP del primer registro `A` para los tres dominios más frecuentes de esa ventana. Antes de resolver una consulta nueva se actualiza la ventana y se busca el dominio en `dns_cache`.

En caso de encontrarlo, se construye una respuesta DNS completa con la IP almacenada y se muestra un mensaje `(debug) Caché hit`. Si no se encuentra, se ejecuta la resolución iterativa normal y, cuando se obtiene una respuesta `A`, se guarda su IP. En ese caso se muestra `(debug) Caché miss`.

### Test de parte 6

Se ejecutó dos veces consecutivas:

```bash
dig +time=5 +tries=1 -p8000 @127.0.0.1 www.uchile.cl
```

En la primera consulta se observó:

```text
(debug) Caché miss para 'www.uchile.cl.'
Query time: 156 msec
www.uchile.cl.  300  IN  A  200.89.76.36
```

En la segunda consulta se observó:

```text
(debug) Caché hit para 'www.uchile.cl.': usando IP '200.89.76.36'
Query time: 0 msec
www.uchile.cl.  300  IN  A  200.89.76.36
```

La segunda consulta no generó nuevos mensajes de consulta a los Name Servers y utilizó la IP almacenada en el caché.

## Pruebas de funcionalidad

Con el resolver recién iniciado se consultó `eol.uchile.cl`:

```bash
dig +time=5 +tries=1 -p8000 @127.0.0.1 eol.uchile.cl
```

La respuesta contenía 12 registros en `Answer`: un registro `CNAME` (`eol.uchile.cl -> oeol-c.uchile.cl`) y **11 respuestas IPv4** de la forma `146.83.63.X`:

```text
146.83.63.68  146.83.63.69  146.83.63.73  146.83.63.74
146.83.63.77  146.83.63.40  146.83.63.31  146.83.63.65
146.83.63.64  146.83.63.72  146.83.63.71
```

Al repetir la consulta, el resolver mostró:

```text
(debug) Caché hit para 'eol.uchile.cl.': usando IP '146.83.63.68'
```

La segunda respuesta entregó `146.83.63.68` sin volver a consultar los Name Servers.

También se probaron los otros dominios solicitados:

```text
www.uchile.cl.       200.89.76.36
cc4303.bachmann.cl.  104.248.65.245
```

Ambas consultas terminaron con `status: NOERROR` y las direcciones IP esperadas.

## Experimentos finales

### `www.webofscience.com`

Al consultar el dominio con el resolver propio:

```bash
dig +time=5 +tries=1 -p8000 @127.0.0.1 www.webofscience.com
```

`dig` terminó con `communications error ... timed out` y no recibió una respuesta. En el modo debug se observó que el resolver llegó a consultar servidores AWS, pero repitió la resolución de `ns-1010.awsdns-62.net.` y no alcanzó una respuesta final.

La consulta de referencia a Cloudflare sí respondió:

```text
www.webofscience.com.                 CNAME  www-us.webofscience.com.
www-us.webofscience.com.               CNAME  www-us.webofscience.com.cdn.cloudflare.net.
www-us.webofscience.com.cdn.cloudflare.net.  A  104.18.24.24
www-us.webofscience.com.cdn.cloudflare.net.  A  104.18.25.24
```

El timeout observado ocurre principalmente porque, al resolver nombres de Name Servers, el resolver puede volver a visitar la misma delegación: no mantiene un conjunto de consultas visitadas ni un límite de profundidad. Además, el resolver solo considera registros `A` en `Answer` y no sigue explícitamente una cadena de `CNAME`, por lo que tampoco garantiza resolver respuestas que entreguen únicamente alias.

Para corregirlo, se debería seguir cada `CNAME` hasta encontrar registros `A`, aceptar todas las respuestas `A` obtenidas y mantener un conjunto de pares `(dominio, servidor)` visitados. También se debería limitar la profundidad de la recursión y probar otros NS cuando uno no responda.

### `www.cc4303.bachmann.cl`

La consulta al resolver propio:

```bash
dig +time=5 +tries=1 -p8000 @127.0.0.1 www.cc4303.bachmann.cl
```

terminó en timeout. El debug mostró que el resolver llegó a `ns1.digitalocean.com`, pero recibió una respuesta negativa con un registro `SOA` y ningún registro `A`. Como el paso 4 indica ignorar respuestas distintas de una delegación o una respuesta `A`, el programa retornó `b""` y no respondió a `dig`.

En cambio, Cloudflare respondió:

```text
status: NXDOMAIN
AUTHORITY SECTION:
bachmann.cl.  1800  IN  SOA  ns1.digitalocean.com. hostmaster.bachmann.cl. ...
```

Esto significa que `www.cc4303.bachmann.cl` no existe. El resolver debería copiar y reenviar al cliente el mensaje DNS negativo, conservando el `RCODE NXDOMAIN` y la sección `Authority`, en vez de ignorarlo y provocar un timeout.

### Repetición de consultas y Name Servers

Se realizaron tres resoluciones independientes de `www.uchile.cl`, reiniciando el proceso entre consultas para evitar que el caché ocultara los saltos. En las tres ejecuciones se observó la misma secuencia:

```text
(debug) Consultando 'www.uchile.cl.' a '.' con dirección IP '198.41.0.4'
(debug) Consultando 'www.uchile.cl.' a 'cl2-tld.d-zone.ca.' con dirección IP '185.159.198.56'
(debug) Consultando 'www.uchile.cl.' a 'ns1.uchile.cl.' con dirección IP '200.89.70.3'
```

En este experimento sí fueron siempre los mismos Name Servers. Esto ocurre porque el código selecciona determinísticamente el primer registro `NS` de `Authority` y la primera dirección `A` de `Additional`; además, los servidores respondieron con el mismo orden durante las pruebas. En una red real podrían cambiar por balanceo, disponibilidad, caché o cambios en el orden de los registros. Si las consultas se repiten dentro del mismo proceso y el dominio entra al caché, ya no se realizan nuevos saltos: se muestra `Caché hit` y se utiliza la IP almacenada.
