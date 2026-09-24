"""
simulador_osi.py
================
Interfaz gráfica (Tkinter) del simulador de encapsulamiento y
desencapsulamiento de datos a través de las 7 capas del Modelo OSI.

Ejecución:
    python simulador_osi.py                 # abre el simulador
    python simulador_osi.py --capturas img  # demo automática que guarda capturas (requiere Pillow)

La lógica de red está en osi_core.py; este archivo solo se encarga de
mostrar el recorrido del mensaje de forma visual.
"""

from __future__ import annotations

import re
import sys
import tkinter as tk
from tkinter import messagebox, ttk

import osi_core as osi

# ---------------------------------------------------------------------------
# Apariencia
# ---------------------------------------------------------------------------

FONDO = "#F4F6F8"
PANEL = "#FFFFFF"
TEXTO = "#1F2933"
TEXTO_SUAVE = "#6B7785"
BORDE = "#D5DBE1"
PENDIENTE = "#E9EDF1"
EXITO = "#1E8E3E"
ERROR = "#C62828"
CABLE = "#34495E"

FUENTE = "Segoe UI"
MONO = "Consolas"

ANCHO_CANVAS = 1240
ALTO_CANVAS = 470

# Posiciones de las pilas de capas
PILA_A_X = (30, 330)
PILA_B_X = (910, 1210)
PILA_Y0 = 78
ALTO_CAPA = 44
SEPARACION = 6

PATRON_ENCABEZADO = re.compile(r"\[(L\d|FCS)\|[^\]]*\]")


def aclarar(color: str, factor: float = 0.75) -> str:
    """Mezcla un color #RRGGBB con blanco (factor 0 = igual, 1 = blanco)."""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    r, g, b = (int(c + (255 - c) * factor) for c in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}"


def oscurecer(color: str, factor: float = 0.3) -> str:
    """Oscurece un color #RRGGBB para que el texto sea legible sobre fondo blanco."""
    r, g, b = (int(int(color[i:i + 2], 16) * (1 - factor)) for i in (1, 3, 5))
    return f"#{r:02X}{g:02X}{b:02X}"


def color_capa(numero: int) -> str:
    return osi.obtener_capa(numero)["color"]


def y_capa(numero: int) -> int:
    """Coordenada Y superior de la caja de la capa (la 7 arriba, la 1 abajo)."""
    return PILA_Y0 + (7 - numero) * (ALTO_CAPA + SEPARACION)


# ---------------------------------------------------------------------------
# Aplicación
# ---------------------------------------------------------------------------

class SimuladorOSI(tk.Tk):
    """Ventana principal del simulador."""

    def __init__(self):
        super().__init__()
        self.title("Simulador OSI – Encapsulamiento y Desencapsulamiento (PC-A → PC-B)")
        self.configure(bg=FONDO)
        self.resizable(False, False)

        self.resultado: osi.ResultadoTransmision | None = None
        self.eventos: list[tuple] = []     # secuencia de pasos a mostrar
        self.indice = -1                   # evento mostrado actualmente
        self.automatico = False
        self.animando = False
        self.id_after = None

        self.var_mensaje = tk.StringVar(value="Hola PC-B, este es un mensaje desde PC-A")
        self.var_ruido = tk.BooleanVar(value=False)
        self.var_velocidad = tk.IntVar(value=1200)
        self.var_estado = tk.StringVar(value="Escriba un mensaje y presione «Transmitir» o «Paso a paso».")

        self._crear_estilos()
        self._crear_controles()
        self._crear_canvas()
        self._crear_paneles()
        self._crear_barra_estado()
        self.reiniciar()

    # ----------------------------------------------------------------- UI --
    def _crear_estilos(self):
        estilo = ttk.Style(self)
        estilo.theme_use("clam")
        estilo.configure("TFrame", background=FONDO)
        estilo.configure("Panel.TFrame", background=PANEL)
        estilo.configure("TLabel", background=FONDO, foreground=TEXTO, font=(FUENTE, 10))
        estilo.configure("Titulo.TLabel", font=(FUENTE, 16, "bold"))
        estilo.configure("Sub.TLabel", foreground=TEXTO_SUAVE, font=(FUENTE, 10))
        estilo.configure("Panel.TLabel", background=PANEL, font=(FUENTE, 10, "bold"))
        estilo.configure("TCheckbutton", background=FONDO, font=(FUENTE, 10))
        estilo.configure("TButton", font=(FUENTE, 10), padding=(10, 5))
        estilo.configure("Primario.TButton", font=(FUENTE, 10, "bold"), foreground="white",
                         background="#2563EB", bordercolor="#2563EB")
        estilo.map("Primario.TButton", background=[("disabled", "#9DB4E8"), ("active", "#1D4ED8")])
        estilo.configure("Estado.TLabel", background="#E3E8EE", font=(FUENTE, 10), padding=(10, 6))
        estilo.configure("Horizontal.TScale", background=FONDO)

    def _crear_controles(self):
        cabecera = ttk.Frame(self, padding=(16, 12, 16, 4))
        cabecera.pack(fill="x")
        ttk.Label(cabecera, text="Simulador de Encapsulamiento – Modelo OSI",
                  style="Titulo.TLabel").pack(side="left")
        ttk.Label(cabecera, text="Recorrido del mensaje por las 7 capas desde PC-A hasta PC-B",
                  style="Sub.TLabel").pack(side="left", padx=14, pady=(6, 0))

        barra = ttk.Frame(self, padding=(16, 6))
        barra.pack(fill="x")
        ttk.Label(barra, text="Mensaje:").pack(side="left")
        self.entrada = ttk.Entry(barra, textvariable=self.var_mensaje, width=48, font=(FUENTE, 11))
        self.entrada.pack(side="left", padx=(6, 12), ipady=3)
        self.entrada.bind("<Return>", lambda _e: self.transmitir())

        self.btn_transmitir = ttk.Button(barra, text="▶  Transmitir", style="Primario.TButton",
                                         command=self.transmitir)
        self.btn_transmitir.pack(side="left")
        self.btn_paso = ttk.Button(barra, text="⏭  Paso a paso", command=self.paso_a_paso)
        self.btn_paso.pack(side="left", padx=6)
        self.btn_reiniciar = ttk.Button(barra, text="↺  Reiniciar", command=self.reiniciar)
        self.btn_reiniciar.pack(side="left")

        ttk.Checkbutton(barra, text="Simular ruido en el cable", variable=self.var_ruido).pack(side="left", padx=14)
        ttk.Label(barra, text="Velocidad:").pack(side="left")
        ttk.Scale(barra, from_=2000, to=300, variable=self.var_velocidad, length=110).pack(side="left", padx=6)

    def _crear_canvas(self):
        marco = ttk.Frame(self, padding=(16, 4))
        marco.pack(fill="x")
        self.canvas = tk.Canvas(marco, width=ANCHO_CANVAS, height=ALTO_CANVAS, bg=PANEL,
                                highlightthickness=1, highlightbackground=BORDE)
        self.canvas.pack()

    def _crear_paneles(self):
        marco = ttk.Frame(self, padding=(16, 8, 16, 8))
        marco.pack(fill="both", expand=True)
        marco.columnconfigure(0, weight=3)
        marco.columnconfigure(1, weight=2)

        izquierda = ttk.Frame(marco, style="Panel.TFrame", padding=8)
        izquierda.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ttk.Label(izquierda, text="Detalle del paso actual", style="Panel.TLabel").pack(anchor="w")
        self.detalle = tk.Text(izquierda, height=11, wrap="char", font=(MONO, 10), relief="flat",
                               bg=PANEL, fg=TEXTO, padx=4, pady=4)
        self.detalle.pack(fill="both", expand=True)

        derecha = ttk.Frame(marco, style="Panel.TFrame", padding=8)
        derecha.grid(row=0, column=1, sticky="nsew")
        ttk.Label(derecha, text="Bitácora de la transmisión", style="Panel.TLabel").pack(anchor="w")
        self.bitacora = tk.Text(derecha, height=11, wrap="word", font=(MONO, 9), relief="flat",
                                bg=PANEL, fg=TEXTO, padx=4, pady=4)
        self.bitacora.pack(fill="both", expand=True)

        for widget in (self.detalle, self.bitacora):
            for capa in osi.CAPAS_OSI:
                widget.tag_configure(f"L{capa['numero']}", foreground=oscurecer(capa["color"]))
            widget.tag_configure("FCS", foreground=oscurecer(color_capa(2)))
            widget.tag_configure("titulo", font=(FUENTE, 11, "bold"))
            widget.tag_configure("etiqueta", foreground=TEXTO_SUAVE, font=(FUENTE, 9, "bold"))
            widget.tag_configure("exito", foreground=EXITO, font=(FUENTE, 10, "bold"))
            widget.tag_configure("error", foreground=ERROR, font=(FUENTE, 10, "bold"))
            widget.tag_configure("bits", foreground=color_capa(1))

    def _crear_barra_estado(self):
        self.estado = ttk.Label(self, textvariable=self.var_estado, style="Estado.TLabel", anchor="w")
        self.estado.pack(fill="x", side="bottom")

    # ------------------------------------------------------ dibujo canvas --
    def dibujar_escena(self, activa: tuple[str, int] | None = None, completadas_a=(), completadas_b=(),
                       capa_error: int | None = None):
        """Redibuja las dos pilas OSI, el cable y el área central."""
        c = self.canvas
        c.delete("all")
        self._dibujar_pila("PC-A", "Emisor", osi.PC_A, PILA_A_X, activa, completadas_a, None)
        self._dibujar_pila("PC-B", "Receptor", osi.PC_B, PILA_B_X, activa, completadas_b, capa_error)
        self._dibujar_cable()

        # Flechas de sentido
        xa, xb = PILA_A_X[1] + 14, PILA_B_X[0] - 14
        c.create_line(xa, y_capa(7) + 10, xa, y_capa(1) + ALTO_CAPA - 10, arrow="last",
                      width=3, fill=aclarar(CABLE, 0.55))
        c.create_line(xb, y_capa(1) + ALTO_CAPA - 10, xb, y_capa(7) + 10, arrow="last",
                      width=3, fill=aclarar(CABLE, 0.55))
        c.create_text(xa + 8, y_capa(4) + ALTO_CAPA / 2, text="Encapsulamiento", angle=90,
                      font=(FUENTE, 9, "bold"), fill=TEXTO_SUAVE)
        c.create_text(xb - 8, y_capa(4) + ALTO_CAPA / 2, text="Desencapsulamiento", angle=90,
                      font=(FUENTE, 9, "bold"), fill=TEXTO_SUAVE)

    def _dibujar_pila(self, nombre, rol, equipo, xs, activa, completadas, capa_error):
        c = self.canvas
        x0, x1 = xs
        # Ícono de computadora
        c.create_rectangle(x0 + 4, 14, x0 + 40, 38, outline=CABLE, width=2, fill="#DCE6F2")
        c.create_line(x0 + 22, 38, x0 + 22, 44, fill=CABLE, width=2)
        c.create_line(x0 + 12, 45, x0 + 32, 45, fill=CABLE, width=2)
        c.create_text(x0 + 50, 18, text=f"{nombre}  ·  {rol}", anchor="w", font=(FUENTE, 12, "bold"), fill=TEXTO)
        c.create_text(x0 + 50, 38, text=f"IP {equipo.ip}   ·   Puerto {equipo.puerto}",
                      anchor="w", font=(FUENTE, 8), fill=TEXTO_SUAVE)
        c.create_text(x0 + 50, 54, text=f"MAC {equipo.mac}", anchor="w", font=(FUENTE, 8), fill=TEXTO_SUAVE)

        for capa in osi.CAPAS_OSI:
            n = capa["numero"]
            y0 = y_capa(n)
            es_activa = activa == (nombre, n)
            if capa_error == n:
                relleno, borde, color_txt = "#FDECEA", ERROR, ERROR
            elif es_activa:
                relleno, borde, color_txt = capa["color"], capa["color"], "white"
            elif n in completadas:
                relleno, borde, color_txt = aclarar(capa["color"], 0.78), capa["color"], TEXTO
            else:
                relleno, borde, color_txt = PENDIENTE, BORDE, TEXTO_SUAVE
            c.create_rectangle(x0, y0, x1, y0 + ALTO_CAPA, fill=relleno, outline=borde,
                               width=3 if es_activa or capa_error == n else 1)
            c.create_oval(x0 + 8, y0 + 8, x0 + 36, y0 + 36, fill=capa["color"], outline="")
            c.create_text(x0 + 22, y0 + 22, text=str(n), fill="white", font=(FUENTE, 11, "bold"))
            c.create_text(x0 + 46, y0 + 22, text=capa["nombre"], anchor="w", fill=color_txt,
                          font=(FUENTE, 11, "bold" if es_activa else "normal"))
            marca = "  ✕" if capa_error == n else ("  ✓" if n in completadas and not es_activa else "")
            c.create_text(x1 - 10, y0 + 22, text=capa["pdu"] + marca, anchor="e", fill=color_txt,
                          font=(FUENTE, 9, "italic"))

    def _dibujar_cable(self):
        c = self.canvas
        ya = y_capa(1) + ALTO_CAPA
        xa = (PILA_A_X[0] + PILA_A_X[1]) / 2
        xb = (PILA_B_X[0] + PILA_B_X[1]) / 2
        yc = ALTO_CANVAS - 26
        self.ruta_cable = [(xa, ya), (xa, yc), (xb, yc), (xb, ya)]
        c.create_line(*[p for punto in self.ruta_cable for p in punto], fill=CABLE, width=5,
                      joinstyle="round", tags="cable")
        c.create_text((xa + xb) / 2, yc - 14, text="Medio físico (cable UTP)", font=(FUENTE, 9, "bold"),
                      fill=TEXTO_SUAVE)

    def dibujar_pdu(self, capas_envoltorio: list[int], titulo: str, subtitulo: str,
                    solo_bits: bool = False, datos_b64: bool = False, sin_bloques: bool = False):
        """Dibuja en el centro la PDU como bloques de colores (encabezados + datos + FCS)."""
        c = self.canvas
        x_izq, x_der = PILA_A_X[1] + 40, PILA_B_X[0] - 40
        ancho = x_der - x_izq
        y0 = 118
        c.create_text((x_izq + x_der) / 2, 82, text=titulo, font=(FUENTE, 13, "bold"), fill=TEXTO)
        c.create_text((x_izq + x_der) / 2, 102, text=subtitulo, font=(FUENTE, 9), fill=TEXTO_SUAVE)
        if sin_bloques:
            return

        if solo_bits:
            c.create_rectangle(x_izq, y0, x_der, y0 + 52, fill=aclarar(color_capa(1), 0.8),
                               outline=color_capa(1), width=2)
            muestra = (self.resultado.bits_enviados[:64] if self.resultado else "")
            c.create_text((x_izq + x_der) / 2, y0 + 26, text=osi.agrupar_bits(muestra) + " …",
                          font=(MONO, 10, "bold"), fill=color_capa(1))
            return

        bloques = []  # (texto, color, ancho)
        # Encabezados en orden exterior -> interior: L2, L3, ..., L7
        for n in sorted(c_ for c_ in capas_envoltorio if c_ >= 2):
            etiqueta = {2: "L2\nMAC", 3: "L3\nIP", 4: "L4\nTCP", 5: "L5\nSES", 6: "L6\nB64", 7: "L7\nAPP"}[n]
            bloques.append((etiqueta, color_capa(n), 52))
        datos_txt = "DATOS\n(Base64)" if datos_b64 else "DATOS\n(mensaje)"
        bloques.append((datos_txt, "#7F8C8D", 118))
        if 2 in capas_envoltorio:
            bloques.append(("FCS\nCRC32", color_capa(2), 52))

        total = sum(b[2] for b in bloques)
        x = x_izq + (ancho - total) / 2
        for texto, color, w in bloques:
            c.create_rectangle(x, y0, x + w, y0 + 52, fill=color, outline="white", width=2)
            c.create_text(x + w / 2, y0 + 26, text=texto, fill="white", font=(FUENTE, 9, "bold"),
                          justify="center")
            x += w

        # Leyenda de tamaño
        if self.resultado and self.indice >= 0:
            evento = self.eventos[self.indice]
            if evento[0] in ("enc", "des"):
                tam = len(evento[1].contenido.encode("utf-8"))
                c.create_text((x_izq + x_der) / 2, y0 + 70, text=f"Tamaño de la PDU: {tam} bytes",
                              font=(FUENTE, 9), fill=TEXTO_SUAVE)

    def dibujar_info_central(self, lineas: list[tuple[str, str]]):
        """Texto explicativo bajo la PDU (lista de (texto, color))."""
        c = self.canvas
        x = (PILA_A_X[1] + PILA_B_X[0]) / 2
        y = 222
        for texto, color in lineas:
            c.create_text(x, y, text=texto, font=(FUENTE, 10), fill=color, width=500, justify="center")
            y += 24

    # ------------------------------------------------------------ control --
    def _preparar(self) -> bool:
        """Llama a osi.transmitir() y arma la lista de eventos a mostrar."""
        mensaje = self.var_mensaje.get()
        try:
            self.resultado = osi.transmitir(mensaje, ruido=self.var_ruido.get())
        except ValueError as exc:
            messagebox.showwarning("Mensaje vacío", str(exc))
            return False
        self.eventos = [("inicio", None)]
        self.eventos += [("enc", p) for p in self.resultado.pasos_encapsulamiento]
        self.eventos.append(("medio", None))
        self.eventos += [("des", p) for p in self.resultado.pasos_desencapsulamiento]
        self.eventos.append(("fin", None) if self.resultado.exito else ("error", None))
        self.indice = -1
        self.bitacora.delete("1.0", "end")
        self.entrada.state(["disabled"])
        return True

    def transmitir(self):
        """Botón «Transmitir»: recorre automáticamente todos los pasos."""
        if self.animando:
            return
        if not self.eventos or self.indice >= len(self.eventos) - 1:
            if not self._preparar():
                return
        self.automatico = True
        self._actualizar_botones()
        self._avanzar_automatico()

    def paso_a_paso(self):
        """Botón «Paso a paso»: muestra un solo paso por clic."""
        if self.animando:
            return
        if not self.eventos or self.indice >= len(self.eventos) - 1:
            if not self._preparar():
                return
        self.automatico = False
        self.siguiente_paso()

    def _avanzar_automatico(self):
        if not self.automatico:
            return
        if self.indice >= len(self.eventos) - 1:
            self.automatico = False
            self._actualizar_botones()
            return
        self.siguiente_paso(al_terminar=lambda: self._programar(self._avanzar_automatico))

    def _programar(self, funcion):
        self.id_after = self.after(int(self.var_velocidad.get()), funcion)

    def reiniciar(self):
        """Botón «Reiniciar»: deja el simulador en su estado inicial."""
        if self.id_after:
            self.after_cancel(self.id_after)
        self.automatico = self.animando = False
        self.resultado, self.eventos, self.indice = None, [], -1
        self.entrada.state(["!disabled"])
        self.dibujar_escena()
        self.dibujar_pdu([], "Listo para transmitir", "Escriba un mensaje en PC-A")
        self.dibujar_info_central([
            ("PC-A encapsulará el mensaje bajando de la capa 7 a la capa 1,", TEXTO_SUAVE),
            ("lo enviará como bits por el cable y PC-B lo desencapsulará", TEXTO_SUAVE),
            ("subiendo de la capa 1 a la capa 7.", TEXTO_SUAVE),
        ])
        self._escribir_detalle([("Esperando mensaje…\n", "titulo"),
                                ("Presione «Transmitir» para ver todo el recorrido automáticamente\n"
                                 "o «Paso a paso» para avanzar capa por capa.", None)])
        self.bitacora.delete("1.0", "end")
        self.var_estado.set("Escriba un mensaje y presione «Transmitir» o «Paso a paso».")
        self.estado.configure(foreground=TEXTO)
        self._actualizar_botones()

    def _actualizar_botones(self):
        ocupado = self.automatico or self.animando
        for boton in (self.btn_transmitir, self.btn_paso):
            boton.state(["disabled"] if ocupado else ["!disabled"])

    # ------------------------------------------------------------- pasos --
    def siguiente_paso(self, al_terminar=None):
        """Muestra el siguiente evento de la secuencia."""
        if self.indice >= len(self.eventos) - 1:
            return
        self.indice += 1
        tipo, paso = self.eventos[self.indice]
        if tipo == "inicio":
            self._mostrar_inicio()
        elif tipo == "enc":
            self._mostrar_encapsulamiento(paso)
        elif tipo == "medio":
            self._mostrar_medio(al_terminar)
            return  # la animación llama a al_terminar
        elif tipo == "des":
            self._mostrar_desencapsulamiento(paso)
        elif tipo == "fin":
            self._mostrar_fin()
        elif tipo == "error":
            self._mostrar_error()
        self._actualizar_botones()
        if al_terminar:
            al_terminar()

    def _mostrar_inicio(self):
        msg = self.resultado.mensaje_original
        self.dibujar_escena(activa=None)
        self.dibujar_pdu([], "Mensaje original en PC-A", "El usuario escribe el mensaje en la aplicación")
        self.dibujar_info_central([(f"«{msg}»", TEXTO), ("Se establece la sesión y comienza el encapsulamiento.",
                                                          TEXTO_SUAVE)])
        self._escribir_detalle([("PC-A · Mensaje original\n", "titulo"),
                                ("Texto ingresado por el usuario:\n", "etiqueta"), (msg + "\n\n", None),
                                ("Longitud: ", "etiqueta"), (f"{len(msg)} caracteres / "
                                                             f"{len(msg.encode('utf-8'))} bytes UTF-8\n", None)])
        self._log(f"PC-A: mensaje a enviar = «{msg}»\n", None)
        self.var_estado.set("PC-A preparó el mensaje. Comienza el encapsulamiento (capa 7 → capa 1).")

    def _mostrar_encapsulamiento(self, paso: osi.PasoOSI):
        completadas = [n for n in osi.ORDEN_ENCAPSULAMIENTO if n > paso.capa]
        self.dibujar_escena(activa=("PC-A", paso.capa), completadas_a=completadas)
        if paso.capa == 1:
            self.dibujar_pdu([], f"Capa 1 · {paso.pdu}", "La trama se convierte en una secuencia de 0 y 1",
                             solo_bits=True)
        else:
            envoltorio = list(range(paso.capa, 8))
            self.dibujar_pdu(envoltorio, f"Capa {paso.capa} · {paso.nombre_capa} → PDU: {paso.pdu}",
                             "PC-A agrega información (encapsula)", datos_b64=paso.capa <= 6)
        self.dibujar_info_central([(paso.explicacion, TEXTO), (f"+ {paso.agregado}", color_capa(paso.capa))])
        self._detalle_paso(paso, "Información agregada:")
        self._log(f"✔ PC-A  C{paso.capa} {paso.nombre_capa:<15} + {paso.agregado}\n", f"L{paso.capa}")
        self.var_estado.set(f"PC-A · Encapsulamiento · Capa {paso.capa} ({paso.nombre_capa}) → {paso.pdu}")

    def _mostrar_medio(self, al_terminar):
        self.dibujar_escena(activa=None, completadas_a=osi.ORDEN_ENCAPSULAMIENTO)
        self.dibujar_pdu([], "Transmisión por el medio físico",
                         f"{len(self.resultado.bits_enviados)} bits viajan de PC-A a PC-B", solo_bits=True)
        info = [("Los bits se propagan como señales eléctricas por el cable.", TEXTO)]
        if self.resultado.bits_enviados != self.resultado.bits_recibidos:
            dif = next(i for i, (a, b) in enumerate(zip(self.resultado.bits_enviados,
                                                         self.resultado.bits_recibidos)) if a != b)
            info.append((f"⚠ Ruido: el bit n.º {dif} fue alterado durante el viaje.", ERROR))
        self.dibujar_info_central(info)
        self._escribir_detalle([("Medio físico · Transmisión\n", "titulo"),
                                ("Bits enviados por PC-A (primeros 400):\n", "etiqueta"),
                                (osi.agrupar_bits(self.resultado.bits_enviados[:400]) + " …\n\n", "bits"),
                                ("Total: ", "etiqueta"), (f"{len(self.resultado.bits_enviados)} bits", None)])
        self._log(f"⇢ Medio: {len(self.resultado.bits_enviados)} bits enviados por el cable\n", "L1")
        self.var_estado.set("Los bits viajan por el cable desde PC-A hasta PC-B…")
        self._animar_bits(al_terminar)

    def _animar_bits(self, al_terminar, cuadros: int = 40):
        """Mueve pequeños bloques (0/1) a lo largo del cable."""
        self.animando = True
        self._actualizar_botones()
        ruta = self.ruta_cable
        longitudes = [abs(ruta[i + 1][0] - ruta[i][0]) + abs(ruta[i + 1][1] - ruta[i][1]) for i in range(3)]
        total = sum(longitudes)
        bits = self.resultado.bits_enviados

        def punto(distancia):
            for i, largo in enumerate(longitudes):
                if distancia <= largo:
                    (x0, y0), (x1, y1) = ruta[i], ruta[i + 1]
                    t = distancia / largo if largo else 0
                    return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                distancia -= largo
            return ruta[-1]

        def cuadro(k):
            self.canvas.delete("bit")
            for j in range(8):
                d = (k / cuadros) * total - j * 26
                if 0 <= d <= total:
                    x, y = punto(d)
                    self.canvas.create_rectangle(x - 9, y - 9, x + 9, y + 9, fill=color_capa(1),
                                                 outline="white", tags="bit")
                    self.canvas.create_text(x, y, text=bits[(k + j) % len(bits)], fill="white",
                                            font=(MONO, 9, "bold"), tags="bit")
            if k < cuadros + 8:
                self.after(35, cuadro, k + 1)
            else:
                self.canvas.delete("bit")
                self.animando = False
                self._actualizar_botones()
                if al_terminar:
                    al_terminar()

        cuadro(0)

    def _mostrar_desencapsulamiento(self, paso: osi.PasoOSI):
        completadas = [n for n in osi.ORDEN_DESENCAPSULAMIENTO if n < paso.capa]
        self.dibujar_escena(activa=("PC-B", paso.capa), completadas_a=osi.ORDEN_ENCAPSULAMIENTO,
                            completadas_b=completadas)
        if paso.capa == 7:
            envoltorio, sub_datos = [], False
        else:
            envoltorio, sub_datos = list(range(paso.capa + 1, 8)), paso.capa < 6
        if paso.capa == 6:
            envoltorio = [7]
        self.dibujar_pdu(envoltorio, f"Capa {paso.capa} · {paso.nombre_capa} → entrega a capa "
                                     f"{paso.capa + 1 if paso.capa < 7 else 'usuario'}",
                         "PC-B verifica y retira información (desencapsula)", datos_b64=sub_datos)
        self.dibujar_info_central([(paso.explicacion, TEXTO), (f"− {paso.agregado}", color_capa(paso.capa))])
        self._detalle_paso(paso, "Información retirada / verificada:")
        self._log(f"✔ PC-B  C{paso.capa} {paso.nombre_capa:<15} − {paso.agregado}\n", f"L{paso.capa}")
        self.var_estado.set(f"PC-B · Desencapsulamiento · Capa {paso.capa} ({paso.nombre_capa})")

    def _mostrar_fin(self):
        r = self.resultado
        self.dibujar_escena(activa=None, completadas_a=osi.ORDEN_ENCAPSULAMIENTO,
                            completadas_b=osi.ORDEN_DESENCAPSULAMIENTO)
        self.dibujar_pdu([], "✔ Mensaje recuperado en PC-B", "El receptor obtuvo exactamente el mismo texto")
        self.dibujar_info_central([(f"Enviado por PC-A:   «{r.mensaje_original}»", TEXTO),
                                   (f"Recibido en PC-B:   «{r.mensaje_recibido}»", EXITO),
                                   ("Resultado: los mensajes son IDÉNTICOS ✔", EXITO)])
        self._escribir_detalle([("PC-B · Mensaje recuperado\n", "titulo"),
                                ("Mensaje original (PC-A):\n", "etiqueta"), (r.mensaje_original + "\n\n", None),
                                ("Mensaje recibido (PC-B):\n", "etiqueta"), (r.mensaje_recibido + "\n\n", "exito"),
                                ("Comparación: ", "etiqueta"),
                                ("original == recibido → True ✔ (7 capas encapsuladas y 7 desencapsuladas)", "exito")])
        self._log(f"★ PC-B recibió: «{r.mensaje_recibido}»  → ÉXITO\n", "exito")
        self.var_estado.set(f"✔ Transmisión exitosa. PC-B recibió: «{r.mensaje_recibido}»")
        self.estado.configure(foreground=EXITO)
        self.entrada.state(["!disabled"])

    def _mostrar_error(self):
        r = self.resultado
        hechas = [p.capa for p in r.pasos_desencapsulamiento]
        self.dibujar_escena(activa=None, completadas_a=osi.ORDEN_ENCAPSULAMIENTO, completadas_b=hechas,
                            capa_error=r.capa_error)
        self.dibujar_pdu([], "✕ Trama descartada en PC-B", "Un error fue detectado durante el desencapsulamiento",
                         sin_bloques=True)
        self.dibujar_info_central([(r.error, ERROR),
                                   ("El mensaje no se entrega a la aplicación. Se debe retransmitir.", TEXTO)])
        self._escribir_detalle([("PC-B · Error detectado\n", "titulo"), (r.error + "\n\n", "error"),
                                ("El control de errores de la capa de Enlace (CRC32) detectó que\n"
                                 "los bits cambiaron en el medio físico.", None)])
        self._log(f"✕ {r.error}\n", "error")
        self.var_estado.set(f"✕ Error: {r.error}")
        self.estado.configure(foreground=ERROR)
        self.entrada.state(["!disabled"])

    # -------------------------------------------------------- utilidades --
    def _detalle_paso(self, paso: osi.PasoOSI, rotulo_agregado: str):
        capa = osi.obtener_capa(paso.capa)
        partes = [(f"{paso.dispositivo} · {paso.accion} · Capa {paso.capa} – {paso.nombre_capa} ({paso.pdu})\n",
                   "titulo"),
                  ("Función de la capa: ", "etiqueta"), (capa["funcion"] + "\n", None),
                  (rotulo_agregado + " ", "etiqueta"), (paso.agregado + "\n", f"L{paso.capa}"),
                  ("PDU resultante:\n", "etiqueta")]
        if paso.accion == "Encapsulamiento" and paso.capa == 1:
            partes.append((osi.agrupar_bits(paso.contenido[:480]) + " …", "bits"))
        else:
            partes.extend(self._colorear_pdu(paso.contenido))
        self._escribir_detalle(partes)

    @staticmethod
    def _colorear_pdu(pdu: str) -> list[tuple[str, str | None]]:
        """Divide la PDU en trozos y asigna a cada encabezado el color de su capa."""
        partes, pos = [], 0
        for m in PATRON_ENCABEZADO.finditer(pdu):
            if m.start() > pos:
                partes.append((pdu[pos:m.start()], None))
            partes.append((m.group(0), m.group(1)))
            pos = m.end()
        if pos < len(pdu):
            partes.append((pdu[pos:], None))
        return partes

    def _escribir_detalle(self, partes):
        self.detalle.configure(state="normal")
        self.detalle.delete("1.0", "end")
        for texto, etiqueta in partes:
            self.detalle.insert("end", texto, etiqueta or ())
        self.detalle.configure(state="disabled")

    def _log(self, texto, etiqueta):
        self.bitacora.insert("end", texto, etiqueta or ())
        self.bitacora.see("end")


# ---------------------------------------------------------------------------
# Modo capturas: recorre la simulación y guarda imágenes de cada paso
# ---------------------------------------------------------------------------

SIN_TILDES = {7: "aplicacion", 6: "presentacion", 5: "sesion", 4: "transporte",
              3: "red", 2: "enlace", 1: "fisica"}


def generar_capturas(carpeta: str, mensaje: str = "Hola PC-B, saludos desde PC-A ¿recibes?"):
    import os
    from PIL import ImageGrab  # dependencia solo para este modo

    os.makedirs(carpeta, exist_ok=True)
    app = SimuladorOSI()
    app.attributes("-topmost", True)
    app.geometry("+10+10")
    capturas = []

    def capturar(nombre):
        app.update_idletasks()
        app.update()
        x, y = app.winfo_rootx(), app.winfo_rooty()
        w, h = app.winfo_width(), app.winfo_height()
        ruta = os.path.join(carpeta, nombre + ".png")
        ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(ruta)
        capturas.append(ruta)

    def esperar(ms):
        fin = app.tk.call("clock", "milliseconds") + ms
        while app.tk.call("clock", "milliseconds") < fin:
            app.update()

    esperar(600)
    capturar("01_inicio")
    app.var_mensaje.set(mensaje)
    app.entrada.icursor("end")
    app.entrada.focus_set()
    esperar(200)
    capturar("02_mensaje_ingresado")

    app._preparar()
    nombres = {"inicio": "03_transmision_iniciada", "fin": "19_mensaje_recuperado"}
    numero = 4
    while app.indice < len(app.eventos) - 1:
        tipo, paso = app.eventos[app.indice + 1]
        if tipo == "medio":
            app.siguiente_paso()
            esperar(700)       # captura a mitad de la animación
            capturar("11_medio_fisico")
            while app.animando:
                esperar(50)
            numero = 12
            continue
        app.siguiente_paso()
        esperar(150)
        if tipo in nombres:
            capturar(nombres[tipo])
        else:
            accion = "enc" if tipo == "enc" else "des"
            capturar(f"{numero:02d}_{accion}_capa{paso.capa}_{SIN_TILDES[paso.capa]}")
            numero += 1

    # Caso de prueba con ruido
    app.reiniciar()
    app.var_ruido.set(True)
    app.var_mensaje.set(mensaje)
    app._preparar()
    while app.indice < len(app.eventos) - 1:
        app.siguiente_paso()
        while app.animando:
            esperar(50)
    esperar(150)
    capturar("20_prueba_ruido_error")
    app.destroy()
    return capturas


def activar_alta_resolucion():
    """En Windows evita que la ventana se vea borrosa en pantallas con escalado."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass


def main():
    activar_alta_resolucion()
    if len(sys.argv) >= 3 and sys.argv[1] == "--capturas":
        for ruta in generar_capturas(sys.argv[2]):
            print("Captura guardada:", ruta)
        return
    SimuladorOSI().mainloop()


if __name__ == "__main__":
    main()
