"""
Geometría de la plantilla: el contrato entre el PDF que se imprime y el lector
que interpreta la hoja escaneada.

Ambos scripts importan de aquí. Si cambias un valor, la plantilla y el lector
siguen cuadrando; si copias los números a mano en otro sitio, dejan de cuadrar
en cuanto uno de los dos cambie. Por eso todo vive en este módulo.

Sistema de coordenadas: milímetros desde la esquina superior izquierda del papel,
que es como se piensa una hoja. El generador de PDF hace la única conversión a
puntos y da la vuelta al eje Y (el PDF mide desde abajo).
"""
from dataclasses import dataclass, field

# Formatos de papel en mm (ancho, alto)
PAPELES = {
    "carta": (215.9, 279.4),
    "a4": (210.0, 297.0),
    "oficio": (215.9, 330.2),
}

# Métricas de la fuente resultante. La altura de ascendente de la plantilla
# equivale a ASCENDER unidades: es lo que fija la escala mm -> unidades de fuente.
UPM = 1000
ASCENDER = 800
DESCENDER = -200

# Resolución de trabajo del lienzo enderezado, en píxeles por mm. Con 8 px/mm una
# celda ronda los 240x244 px: suficiente para que el trazo tenga cuerpo y barato
# de procesar. Subirlo afina el contorno y encarece el trazado en proporción
# cuadrática.
PX_POR_MM = 8

# Proporciones de la pauta dentro de la celda, como fracción de su altura.
# Calibradas sobre la celda de 30,5 mm de la versión validada; al expresarlas como
# fracción, una rejilla más holgada o más apretada conserva las proporciones de la
# escritura en vez de deformarlas.
F_ASCENDENTE = 6.00 / 30.5    # renglón superior: altura de mayúsculas y de b, d, l
F_EQUIS      = 12.75 / 30.5   # altura de la x: cuerpo de las minúsculas redondas
F_BASE       = 24.00 / 30.5   # línea base: sobre ella se apoya la letra
F_DESCENDENTE= 28.50 / 30.5   # hasta dónde bajan las colas de g, j, p, q, y

# Grosores de impresión en mm. Finos a propósito: el lector separa la letra del
# renglón comparando grosores, así que cuanto más fina la línea frente al trazo
# del bolígrafo, más limpio el borrado. La base es la más gruesa porque es la
# referencia que la persona necesita ver al escribir.
W_ASCENDENTE  = 0.18
W_EQUIS       = 0.12
W_BASE        = 0.40
W_DESCENDENTE = 0.12
W_CELDA       = 0.12

# Márgenes de lectura dentro de cada celda, en mm.
PAD_LATERAL = 2.0   # absorbe el error de registro sin comerse el trazo
MARGEN_GUIA = 1.6   # separación entre la letra guía impresa y el área que se lee

MARCA_LADO = 6.0    # lado de los cuadrados negros de registro
MARCA_MARGEN = 12.7 # media pulgada: dentro del área imprimible de cualquier impresora
SEPARACION_REJILLA = 5.0  # aleja la rejilla de las marcas para que no invadan celdas

# Colores de pauta. El negro se borra por geometría y funciona en impresora
# monocroma. Rojo y cian tienen el canal rojo alto, así que además desaparecen al
# leer solo ese canal, pero exigen impresión en color: en escala de grises salen
# como gris o trama de puntos y se leerían como tinta.
COLORES = {
    "negro": ("#000000", "#555555"),
    "rojo":  ("#FF4D4D", "#FFB0B0"),
    "cian":  ("#9DDCEC", "#C3E9F4"),
}

JUEGOS = {
    "basico": ("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
               "abcdefghijklmnopqrstuvwxyz"
               "0123456789.,:;!?'\"-()"),
    "espanol": ("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                "abcdefghijklmnopqrstuvwxyz"
                "0123456789.,:;!?'\"-()"
                "áéíóúüñÁÉÍÓÚÑ¿¡"),
    "extendido": ("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                  "abcdefghijklmnopqrstuvwxyz"
                  "0123456789.,:;!?'\"-()"
                  "áéíóúüñÁÉÍÓÚÑ¿¡"
                  "@#%&*+=/\\<>[]{}_|~$€°"),
    "griego": "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩαβγδεζηθικλμνξοπρστυφχψω",
    "matematico": "0123456789+-±×÷=≠≈<>≤≥()[]{}∑∏∫∂∇√∞πθλμσωΔΩ°%·",
}


@dataclass
class Plantilla:
    """Geometría completa de una plantilla, derivada de unos pocos parámetros."""
    papel: str = "carta"
    columnas: int = 6
    filas: int = 8
    color: str = "negro"

    ancho: float = field(init=False)
    alto: float = field(init=False)

    def __post_init__(self):
        if self.papel not in PAPELES:
            raise ValueError(f"papel desconocido: {self.papel!r}; usa {list(PAPELES)}")
        if self.color not in COLORES:
            raise ValueError(f"color desconocido: {self.color!r}; usa {list(COLORES)}")
        if not (1 <= self.columnas <= 12 and 1 <= self.filas <= 14):
            raise ValueError("la rejilla debe estar entre 1x1 y 12x14 celdas")
        self.ancho, self.alto = PAPELES[self.papel]

    # --- marcas de registro: definen el rectángulo de referencia -------------
    @property
    def marcas(self):
        """Centros de las cuatro marcas, en orden SI, SD, II, ID."""
        m = MARCA_MARGEN
        return [(m, m), (self.ancho - m, m),
                (m, self.alto - m), (self.ancho - m, self.alto - m)]

    @property
    def ref_ancho(self):
        return self.ancho - 2 * MARCA_MARGEN

    @property
    def ref_alto(self):
        return self.alto - 2 * MARCA_MARGEN

    # --- rejilla de celdas, metida dentro del rectángulo de referencia -------
    @property
    def rejilla_x(self):
        return MARCA_MARGEN + SEPARACION_REJILLA

    @property
    def rejilla_y(self):
        return MARCA_MARGEN + SEPARACION_REJILLA

    @property
    def celda_ancho(self):
        return (self.ref_ancho - 2 * SEPARACION_REJILLA) / self.columnas

    @property
    def celda_alto(self):
        return (self.ref_alto - 2 * SEPARACION_REJILLA) / self.filas

    @property
    def por_pagina(self):
        return self.columnas * self.filas

    # --- pauta dentro de una celda, en mm desde su borde superior ------------
    @property
    def y_ascendente(self):
        return self.celda_alto * F_ASCENDENTE

    @property
    def y_equis(self):
        return self.celda_alto * F_EQUIS

    @property
    def y_base(self):
        return self.celda_alto * F_BASE

    @property
    def y_descendente(self):
        return self.celda_alto * F_DESCENDENTE

    @property
    def renglones(self):
        """Los cuatro renglones, para dibujarlos y para volver a borrarlos."""
        return [(self.y_ascendente, W_ASCENDENTE),
                (self.y_equis, W_EQUIS),
                (self.y_base, W_BASE),
                (self.y_descendente, W_DESCENDENTE)]

    @property
    def y_guia(self):
        """Línea base de la letra modelo impresa en la esquina de la celda."""
        return max(2.6, self.y_ascendente - 2.5)

    @property
    def pad_superior(self):
        """El área de lectura empieza bajo la letra guía para no capturarla."""
        return max(PAD_LATERAL, self.y_ascendente - MARGEN_GUIA)

    # --- escalas -------------------------------------------------------------
    @property
    def unidades_por_mm(self):
        """Cuántas unidades de fuente mide un milímetro del papel."""
        return ASCENDER / (self.y_base - self.y_ascendente)

    @property
    def unidades_por_px(self):
        return self.unidades_por_mm / PX_POR_MM

    # --- lienzo enderezado ---------------------------------------------------
    @property
    def lienzo(self):
        """Tamaño en px del rectángulo de marcas una vez enderezado."""
        return (round(self.ref_ancho * PX_POR_MM), round(self.ref_alto * PX_POR_MM))

    @property
    def desplazamiento_px(self):
        """Origen de la rejilla dentro de ese lienzo."""
        return SEPARACION_REJILLA * PX_POR_MM

    def recorte_celda(self, col, fila):
        """Ventana (x0, x1, y0, y1) en px que se lee para un glifo.

        Deja fuera la letra guía por arriba y el borde de celda por los lados,
        y llega un poco más abajo del renglón de descendentes para no cortar las
        colas de g, j, p, q, y.
        """
        s, off = PX_POR_MM, self.desplazamiento_px
        cw, ch = self.celda_ancho * s, self.celda_alto * s
        x0 = round(off + col * cw + PAD_LATERAL * s)
        x1 = round(off + (col + 1) * cw - PAD_LATERAL * s)
        y0 = round(off + fila * ch + self.pad_superior * s)
        y1 = round(off + fila * ch + self.y_descendente * s + 2)
        return x0, x1, y0, y1

    def paginas(self, caracteres):
        """Reparte los caracteres en páginas de por_pagina celdas."""
        n = self.por_pagina
        return [caracteres[i:i + n] for i in range(0, len(caracteres), n)] or [[]]

    def resumen(self):
        return (f"{self.papel} {self.ancho:g}x{self.alto:g} mm · "
                f"rejilla {self.columnas}x{self.filas} = {self.por_pagina} celdas de "
                f"{self.celda_ancho:.2f}x{self.celda_alto:.2f} mm · pauta {self.color} · "
                f"{self.unidades_por_mm:.1f} unidades/mm")


def normaliza_caracteres(texto):
    """Quita espacios y repetidos conservando el orden en que aparecen."""
    vistos, salida = set(), []
    for ch in texto:
        if ch.isspace() or ch in vistos:
            continue
        vistos.add(ch)
        salida.append(ch)
    return salida


def resuelve_juego(nombre_o_texto):
    """Acepta el nombre de un juego predefinido o una cadena de caracteres."""
    clave = nombre_o_texto.strip().lower()
    if clave in JUEGOS:
        return normaliza_caracteres(JUEGOS[clave])
    return normaliza_caracteres(nombre_o_texto)
