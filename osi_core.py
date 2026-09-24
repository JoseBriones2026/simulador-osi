"""
osi_core.py
===========
Lógica del simulador de encapsulamiento / desencapsulamiento del Modelo OSI.

Este módulo NO tiene interfaz gráfica: solo contiene las funciones que
transforman el mensaje capa por capa. La interfaz (simulador_osi.py) y las
pruebas (tests/) lo importan.

Recorrido en PC-A (encapsulamiento):
    7 Aplicación -> 6 Presentación -> 5 Sesión -> 4 Transporte
    -> 3 Red -> 2 Enlace de Datos -> 1 Física

Recorrido en PC-B (desencapsulamiento):
    1 Física -> 2 Enlace de Datos -> 3 Red -> 4 Transporte
    -> 5 Sesión -> 6 Presentación -> 7 Aplicación
"""

from __future__ import annotations

import base64
import binascii
import random
import re
import zlib
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Representación de las 7 capas
# ---------------------------------------------------------------------------

CAPAS_OSI = [
    {"numero": 7, "nombre": "Aplicación", "pdu": "Datos", "color": "#E74C3C",
     "funcion": "Interfaz con el usuario; identifica el servicio (chat)."},
    {"numero": 6, "nombre": "Presentación", "pdu": "Datos", "color": "#E67E22",
     "funcion": "Formato y codificación de los datos (UTF-8 + Base64)."},
    {"numero": 5, "nombre": "Sesión", "pdu": "Datos", "color": "#F1C40F",
     "funcion": "Establece, mantiene y cierra el diálogo entre equipos."},
    {"numero": 4, "nombre": "Transporte", "pdu": "Segmento", "color": "#2ECC71",
     "funcion": "Puertos, número de secuencia y checksum (TCP)."},
    {"numero": 3, "nombre": "Red", "pdu": "Paquete", "color": "#1ABC9C",
     "funcion": "Direccionamiento lógico IP y TTL."},
    {"numero": 2, "nombre": "Enlace de Datos", "pdu": "Trama", "color": "#3498DB",
     "funcion": "Direccionamiento físico MAC y control de errores (FCS/CRC32)."},
    {"numero": 1, "nombre": "Física", "pdu": "Bits", "color": "#9B59B6",
     "funcion": "Convierte la trama en bits (0 y 1) que viajan por el medio."},
]

ORDEN_ENCAPSULAMIENTO = [7, 6, 5, 4, 3, 2, 1]
ORDEN_DESENCAPSULAMIENTO = [1, 2, 3, 4, 5, 6, 7]


def obtener_capa(numero: int) -> dict:
    """Devuelve el diccionario descriptivo de la capa `numero` (1..7)."""
    for capa in CAPAS_OSI:
        if capa["numero"] == numero:
            return capa
    raise ValueError(f"Capa OSI inexistente: {numero}")


# ---------------------------------------------------------------------------
# Estructuras de datos
# ---------------------------------------------------------------------------

@dataclass
class Dispositivo:
    """Equipo final de la red (PC-A o PC-B)."""
    nombre: str
    ip: str
    mac: str
    puerto: int


PC_A = Dispositivo("PC-A", "192.168.1.10", "AA:AA:AA:00:00:0A", 49152)
PC_B = Dispositivo("PC-B", "192.168.1.20", "BB:BB:BB:00:00:0B", 8080)


@dataclass
class PasoOSI:
    """Un paso del recorrido: lo que ocurrió en una capa de un dispositivo."""
    capa: int
    nombre_capa: str
    pdu: str
    accion: str            # "Encapsulamiento" o "Desencapsulamiento"
    dispositivo: str       # "PC-A" o "PC-B"
    agregado: str          # encabezado/tráiler agregado o retirado
    contenido: str         # PDU resultante después del paso
    explicacion: str


@dataclass
class ResultadoTransmision:
    """Resultado completo que devuelve transmitir()."""
    mensaje_original: str
    pasos_encapsulamiento: list[PasoOSI] = field(default_factory=list)
    bits_enviados: str = ""
    bits_recibidos: str = ""
    pasos_desencapsulamiento: list[PasoOSI] = field(default_factory=list)
    mensaje_recibido: str | None = None
    exito: bool = False
    error: str | None = None
    capa_error: int | None = None

    @property
    def todos_los_pasos(self) -> list[PasoOSI]:
        return self.pasos_encapsulamiento + self.pasos_desencapsulamiento


class ErrorOSI(Exception):
    """Error detectado por una capa al desencapsular (trama dañada, IP ajena...)."""

    def __init__(self, capa: int, mensaje: str):
        super().__init__(f"Capa {capa} ({obtener_capa(capa)['nombre']}): {mensaje}")
        self.capa = capa


# ---------------------------------------------------------------------------
# Utilidades de encabezados
# ---------------------------------------------------------------------------

def crear_encabezado(etiqueta: str, campos: dict) -> str:
    """Construye un encabezado legible, p. ej. [L3|src=192.168.1.10;dst=...]."""
    texto = ";".join(f"{clave}={valor}" for clave, valor in campos.items())
    return f"[{etiqueta}|{texto}]"


def extraer_encabezado(pdu: str, etiqueta: str, capa: int) -> tuple[dict, str]:
    """Separa el encabezado `etiqueta` del inicio de la PDU.

    Devuelve (campos del encabezado, carga útil restante).
    Lanza ErrorOSI si el encabezado esperado no está.
    """
    patron = re.compile(r"^\[" + re.escape(etiqueta) + r"\|([^\]]*)\]")
    coincidencia = patron.match(pdu)
    if not coincidencia:
        raise ErrorOSI(capa, f"no se encontró el encabezado {etiqueta}")
    campos = {}
    for par in coincidencia.group(1).split(";"):
        if "=" in par:
            clave, valor = par.split("=", 1)
            campos[clave] = valor
    return campos, pdu[coincidencia.end():]


# ---------------------------------------------------------------------------
# Base64 (capa de Presentación)
# ---------------------------------------------------------------------------

def codificar_base64(texto: str) -> str:
    """Texto -> bytes UTF-8 -> Base64 (solo caracteres A-Z a-z 0-9 + / =)."""
    return base64.b64encode(texto.encode("utf-8")).decode("ascii")


def decodificar_base64(texto_b64: str) -> str:
    """Base64 -> bytes -> texto UTF-8 (operación inversa de codificar_base64)."""
    return base64.b64decode(texto_b64.encode("ascii"), validate=True).decode("utf-8")


# ---------------------------------------------------------------------------
# Control de errores
# ---------------------------------------------------------------------------

def calcular_checksum(datos: str) -> str:
    """Checksum simple de Transporte: suma de bytes módulo 65536 en hexadecimal."""
    return f"{sum(datos.encode('utf-8')) % 65536:04X}"


def calcular_crc32(datos: str) -> str:
    """FCS de la capa de Enlace: CRC32 de la trama en hexadecimal."""
    return f"{zlib.crc32(datos.encode('utf-8')) & 0xFFFFFFFF:08X}"


# ---------------------------------------------------------------------------
# Conversión bits <-> bytes (capa Física)
# ---------------------------------------------------------------------------

def texto_a_bits(texto: str) -> str:
    """Convierte cada byte UTF-8 del texto en 8 bits ('0'/'1')."""
    return "".join(f"{byte:08b}" for byte in texto.encode("utf-8"))


def bits_a_texto(bits: str) -> str:
    """Agrupa los bits de 8 en 8 y reconstruye el texto UTF-8."""
    if len(bits) % 8 != 0 or set(bits) - {"0", "1"}:
        raise ErrorOSI(1, "la secuencia de bits recibida no es válida")
    datos = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
    # errors="replace": si hubo ruido, el texto se reconstruye igual y
    # será la capa de Enlace (CRC32) la que detecte el daño.
    return datos.decode("utf-8", errors="replace")


def agrupar_bits(bits: str, grupo: int = 8) -> str:
    """Formatea los bits en grupos de 8 para mostrarlos en pantalla."""
    return " ".join(bits[i:i + grupo] for i in range(0, len(bits), grupo))


def aplicar_ruido(bits: str, posicion: int | None = None) -> tuple[str, int]:
    """Simula interferencia en el cable invirtiendo un bit.

    Devuelve (bits alterados, posición invertida).
    """
    if posicion is None:
        posicion = random.randrange(len(bits) // 4, len(bits) * 3 // 4)
    invertido = "1" if bits[posicion] == "0" else "0"
    return bits[:posicion] + invertido + bits[posicion + 1:], posicion


# ---------------------------------------------------------------------------
# Sesión
# ---------------------------------------------------------------------------

def establecer_sesion() -> str:
    """Simula el establecimiento de la sesión entre PC-A y PC-B (ID compartido)."""
    return f"S-{random.randint(1000, 9999)}"


# ---------------------------------------------------------------------------
# ENCAPSULAMIENTO (PC-A): cada función recibe la PDU de la capa superior
# y devuelve (pdu_nueva, texto_agregado)
# ---------------------------------------------------------------------------

def encapsular_aplicacion(mensaje: str, origen: Dispositivo, destino: Dispositivo) -> tuple[str, str]:
    """Capa 7: identifica el servicio y los usuarios de la comunicación."""
    encabezado = crear_encabezado("L7", {"app": "CHAT", "de": origen.nombre, "para": destino.nombre})
    return encabezado + mensaje, encabezado


def encapsular_presentacion(datos: str) -> tuple[str, str]:
    """Capa 6: traduce los datos a un formato común (UTF-8) y los codifica en Base64."""
    codificado = codificar_base64(datos)
    encabezado = crear_encabezado("L6", {"charset": "UTF-8", "cod": "BASE64"})
    return encabezado + codificado, encabezado


def encapsular_sesion(datos: str, id_sesion: str) -> tuple[str, str]:
    """Capa 5: marca los datos con el identificador de la sesión activa."""
    encabezado = crear_encabezado("L5", {"sesion": id_sesion, "estado": "ACTIVA"})
    return encabezado + datos, encabezado


def encapsular_transporte(datos: str, origen: Dispositivo, destino: Dispositivo, secuencia: int = 1) -> tuple[str, str]:
    """Capa 4: crea el SEGMENTO con puertos, secuencia, longitud y checksum."""
    encabezado = crear_encabezado("L4", {
        "proto": "TCP", "sport": origen.puerto, "dport": destino.puerto,
        "seq": secuencia, "len": len(datos), "chk": calcular_checksum(datos),
    })
    return encabezado + datos, encabezado


def encapsular_red(segmento: str, origen: Dispositivo, destino: Dispositivo, ttl: int = 64) -> tuple[str, str]:
    """Capa 3: crea el PAQUETE con IP de origen, IP de destino y TTL."""
    encabezado = crear_encabezado("L3", {"src": origen.ip, "dst": destino.ip, "ttl": ttl, "proto": "TCP"})
    return encabezado + segmento, encabezado


def encapsular_enlace(paquete: str, origen: Dispositivo, destino: Dispositivo) -> tuple[str, str]:
    """Capa 2: crea la TRAMA con MAC origen/destino (encabezado) y FCS (tráiler)."""
    encabezado = crear_encabezado("L2", {"dst": destino.mac, "src": origen.mac, "tipo": "0x0800"})
    cuerpo = encabezado + paquete
    trailer = crear_encabezado("FCS", {"crc32": calcular_crc32(cuerpo)})
    return cuerpo + trailer, f"{encabezado}  ...  {trailer}"


def encapsular_fisica(trama: str) -> tuple[str, str]:
    """Capa 1: convierte la trama completa en una secuencia de BITS."""
    bits = texto_a_bits(trama)
    return bits, f"{len(bits)} bits ({len(bits) // 8} bytes)"


# ---------------------------------------------------------------------------
# DESENCAPSULAMIENTO (PC-B): proceso inverso, cada capa verifica y retira
# su propio encabezado. Devuelven (pdu_para_capa_superior, texto_retirado)
# ---------------------------------------------------------------------------

def desencapsular_fisica(bits: str) -> tuple[str, str]:
    """Capa 1: reconstruye la trama a partir de los bits recibidos."""
    trama = bits_a_texto(bits)
    return trama, f"{len(bits)} bits -> {len(bits) // 8} bytes"


def desencapsular_enlace(trama: str, receptor: Dispositivo) -> tuple[str, str]:
    """Capa 2: verifica el FCS (CRC32) y la MAC destino; retira encabezado y tráiler."""
    posicion = trama.rfind("[FCS|")
    if posicion == -1:
        raise ErrorOSI(2, "trama sin FCS (tráiler dañado)")
    cuerpo, trailer = trama[:posicion], trama[posicion:]
    fcs, _ = extraer_encabezado(trailer, "FCS", 2)
    crc_calculado = calcular_crc32(cuerpo)
    if fcs.get("crc32") != crc_calculado:
        raise ErrorOSI(2, f"FCS incorrecto (recibido {fcs.get('crc32')}, calculado {crc_calculado}). "
                          "La trama se descarta.")
    campos, paquete = extraer_encabezado(cuerpo, "L2", 2)
    if campos.get("dst") != receptor.mac:
        raise ErrorOSI(2, f"la MAC destino {campos.get('dst')} no corresponde a {receptor.nombre}")
    encabezado = crear_encabezado("L2", campos)
    return paquete, f"{encabezado}  ...  {trailer}"


def desencapsular_red(paquete: str, receptor: Dispositivo) -> tuple[str, str]:
    """Capa 3: verifica que la IP destino sea la del receptor y retira el encabezado."""
    campos, segmento = extraer_encabezado(paquete, "L3", 3)
    if campos.get("dst") != receptor.ip:
        raise ErrorOSI(3, f"la IP destino {campos.get('dst')} no corresponde a {receptor.nombre}")
    return segmento, crear_encabezado("L3", campos)


def desencapsular_transporte(segmento: str, receptor: Dispositivo) -> tuple[str, str]:
    """Capa 4: valida puerto, longitud y checksum; entrega los datos a Sesión."""
    campos, datos = extraer_encabezado(segmento, "L4", 4)
    if int(campos.get("dport", -1)) != receptor.puerto:
        raise ErrorOSI(4, f"puerto destino {campos.get('dport')} no está abierto en {receptor.nombre}")
    if int(campos.get("len", -1)) != len(datos):
        raise ErrorOSI(4, "la longitud del segmento no coincide")
    if campos.get("chk") != calcular_checksum(datos):
        raise ErrorOSI(4, "checksum incorrecto")
    return datos, crear_encabezado("L4", campos)


def desencapsular_sesion(datos: str, id_sesion: str) -> tuple[str, str]:
    """Capa 5: comprueba que los datos pertenezcan a la sesión establecida."""
    campos, resto = extraer_encabezado(datos, "L5", 5)
    if campos.get("sesion") != id_sesion:
        raise ErrorOSI(5, f"sesión desconocida {campos.get('sesion')}")
    return resto, crear_encabezado("L5", campos)


def desencapsular_presentacion(datos: str) -> tuple[str, str]:
    """Capa 6: decodifica Base64 y restaura el texto UTF-8."""
    campos, codificado = extraer_encabezado(datos, "L6", 6)
    try:
        decodificado = decodificar_base64(codificado)
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise ErrorOSI(6, f"no se pudo decodificar Base64: {exc}") from exc
    return decodificado, crear_encabezado("L6", campos)


def desencapsular_aplicacion(datos: str) -> tuple[str, str]:
    """Capa 7: retira el encabezado de la aplicación y entrega el mensaje al usuario."""
    campos, mensaje = extraer_encabezado(datos, "L7", 7)
    return mensaje, crear_encabezado("L7", campos)


# ---------------------------------------------------------------------------
# Procesos completos
# ---------------------------------------------------------------------------

EXPLICACION_ENC = {
    7: "Se agrega el encabezado de Aplicación: servicio CHAT, emisor y receptor.",
    6: "Los datos se convierten a bytes UTF-8 y se codifican en Base64.",
    5: "Se agrega el ID de la sesión establecida entre PC-A y PC-B.",
    4: "Se forma el SEGMENTO: puertos TCP, secuencia, longitud y checksum.",
    3: "Se forma el PAQUETE: IP origen, IP destino y TTL.",
    2: "Se forma la TRAMA: MAC destino/origen al inicio y FCS (CRC32) al final.",
    1: "La trama se convierte en BITS que viajan por el medio físico.",
}

EXPLICACION_DES = {
    1: "Los bits recibidos se agrupan en bytes y se reconstruye la trama.",
    2: "Se verifica el FCS (CRC32) y la MAC destino; se retiran encabezado y tráiler.",
    3: "Se verifica la IP destino y se retira el encabezado de Red.",
    4: "Se valida puerto, longitud y checksum; se retira el encabezado TCP.",
    5: "Se comprueba el ID de sesión y se retira el encabezado de Sesión.",
    6: "Se decodifica Base64 y se recupera el texto en UTF-8.",
    7: "Se retira el encabezado de Aplicación y se entrega el mensaje original.",
}


def _crear_paso(capa: int, accion: str, dispositivo: str, agregado: str, contenido: str) -> PasoOSI:
    info = obtener_capa(capa)
    explicacion = (EXPLICACION_ENC if accion == "Encapsulamiento" else EXPLICACION_DES)[capa]
    return PasoOSI(capa, info["nombre"], info["pdu"], accion, dispositivo, agregado, contenido, explicacion)


def encapsular(mensaje: str, origen: Dispositivo, destino: Dispositivo, id_sesion: str) -> tuple[list[PasoOSI], str]:
    """Ejecuta el encapsulamiento 7 -> 1 en el emisor.

    Devuelve (lista de pasos, bits listos para transmitir).
    """
    operaciones = {
        7: lambda pdu: encapsular_aplicacion(pdu, origen, destino),
        6: encapsular_presentacion,
        5: lambda pdu: encapsular_sesion(pdu, id_sesion),
        4: lambda pdu: encapsular_transporte(pdu, origen, destino),
        3: lambda pdu: encapsular_red(pdu, origen, destino),
        2: lambda pdu: encapsular_enlace(pdu, origen, destino),
        1: encapsular_fisica,
    }
    pasos, pdu = [], mensaje
    for capa in ORDEN_ENCAPSULAMIENTO:
        pdu, agregado = operaciones[capa](pdu)
        pasos.append(_crear_paso(capa, "Encapsulamiento", origen.nombre, agregado, pdu))
    return pasos, pdu


def desencapsular(bits: str, receptor: Dispositivo, id_sesion: str) -> tuple[list[PasoOSI], str]:
    """Ejecuta el desencapsulamiento 1 -> 7 en el receptor.

    Devuelve (lista de pasos, mensaje recuperado). Si una capa detecta un
    problema lanza ErrorOSI; los pasos completados quedan en `exc.pasos`.
    """
    operaciones = {
        1: desencapsular_fisica,
        2: lambda pdu: desencapsular_enlace(pdu, receptor),
        3: lambda pdu: desencapsular_red(pdu, receptor),
        4: lambda pdu: desencapsular_transporte(pdu, receptor),
        5: lambda pdu: desencapsular_sesion(pdu, id_sesion),
        6: desencapsular_presentacion,
        7: desencapsular_aplicacion,
    }
    pasos, pdu = [], bits
    for capa in ORDEN_DESENCAPSULAMIENTO:
        try:
            pdu, retirado = operaciones[capa](pdu)
        except ErrorOSI as exc:
            exc.pasos = pasos
            raise
        pasos.append(_crear_paso(capa, "Desencapsulamiento", receptor.nombre, retirado, pdu))
    return pasos, pdu


def transmitir(mensaje: str, origen: Dispositivo = PC_A, destino: Dispositivo = PC_B,
               ruido: bool = False) -> ResultadoTransmision:
    """Función principal: envía `mensaje` de `origen` a `destino` pasando por las 7 capas.

    1. Establece la sesión.
    2. Encapsula en el emisor (7 -> 1).
    3. Transmite los bits por el medio (opcionalmente con ruido).
    4. Desencapsula en el receptor (1 -> 7).
    5. Compara el mensaje recuperado con el original.
    """
    if not mensaje or not mensaje.strip():
        raise ValueError("El mensaje no puede estar vacío")

    resultado = ResultadoTransmision(mensaje_original=mensaje)
    id_sesion = establecer_sesion()

    resultado.pasos_encapsulamiento, resultado.bits_enviados = encapsular(mensaje, origen, destino, id_sesion)

    resultado.bits_recibidos = resultado.bits_enviados
    if ruido:
        resultado.bits_recibidos, _ = aplicar_ruido(resultado.bits_enviados)

    try:
        resultado.pasos_desencapsulamiento, resultado.mensaje_recibido = desencapsular(
            resultado.bits_recibidos, destino, id_sesion)
        resultado.exito = resultado.mensaje_recibido == mensaje
    except ErrorOSI as exc:
        resultado.pasos_desencapsulamiento = getattr(exc, "pasos", [])
        resultado.error = str(exc)
        resultado.capa_error = exc.capa
    return resultado


# ---------------------------------------------------------------------------
# Modo consola (python osi_core.py "mensaje")
# ---------------------------------------------------------------------------

def imprimir_resultado(resultado: ResultadoTransmision) -> None:
    """Muestra el recorrido completo en la terminal."""
    print(f"\nMensaje original en {PC_A.nombre}: {resultado.mensaje_original!r}\n")
    for paso in resultado.todos_los_pasos:
        contenido = paso.contenido if paso.capa != 1 or paso.accion != "Encapsulamiento" \
            else agrupar_bits(paso.contenido)[:95] + " ..."
        print(f"[{paso.dispositivo}] {paso.accion:<18} Capa {paso.capa} {paso.nombre_capa:<16} ({paso.pdu})")
        signo = "+" if paso.accion == "Encapsulamiento" else "-"
        print(f"    {signo} {paso.agregado}")
        print(f"    = {contenido}\n")
    if resultado.exito:
        print(f"Mensaje recuperado en {PC_B.nombre}: {resultado.mensaje_recibido!r}  -> OK, idéntico al original")
    else:
        print(f"ERROR: {resultado.error}")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    texto = " ".join(sys.argv[1:]) or "Hola PC-B"
    imprimir_resultado(transmitir(texto))
