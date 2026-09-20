#!/usr/bin/env python3
"""
Genera la plantilla de caligrafía como PDF vectorial.

Escribe el PDF a mano, sin librerías: son unos pocos objetos y un flujo de
líneas y texto, y así el script corre en cualquier Python sin instalar nada.
Las letras guía usan Helvetica, la única familia que un PDF puede mostrar sin
incrustar el archivo de fuente; son marcas de referencia minúsculas en la
esquina de cada celda, no contenido del documento.

Uso:
    python crear_plantilla.py --salida plantilla.pdf
    python crear_plantilla.py --juego griego --papel a4 --salida griega.pdf
    python crear_plantilla.py --juego "ΑΒΓΔΕΖ" --rejilla 4x6 --color rojo
"""
import argparse
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from geometria import (Plantilla, COLORES, JUEGOS, resuelve_juego)

MM_A_PT = 72 / 25.4

# WinAnsi asigna estos códigos a caracteres que no están en Latin-1.
WINANSI_EXTRA = {
    0x20AC: 0x80, 0x201A: 0x82, 0x0192: 0x83, 0x201E: 0x84, 0x2026: 0x85,
    0x2020: 0x86, 0x2021: 0x87, 0x02C6: 0x88, 0x2030: 0x89, 0x0160: 0x8A,
    0x2039: 0x8B, 0x0152: 0x8C, 0x017D: 0x8E, 0x2018: 0x91, 0x2019: 0x92,
    0x201C: 0x93, 0x201D: 0x94, 0x2022: 0x95, 0x2013: 0x96, 0x2014: 0x97,
    0x02DC: 0x98, 0x2122: 0x99, 0x0161: 0x9A, 0x203A: 0x9B, 0x0153: 0x9C,
    0x017E: 0x9E, 0x0178: 0x9F,
}


def byte_winansi(cp):
    if 32 <= cp <= 126 or 0xA0 <= cp <= 0xFF:
        return cp
    return WINANSI_EXTRA.get(cp)


def etiqueta_imprimible(ch):
    """Devuelve el carácter si Helvetica/WinAnsi puede mostrarlo, o un sustituto.

    Un juego griego o cirílico no cabe en WinAnsi. En vez de dejar la celda sin
    referencia —lo que obligaría a adivinar qué toca escribir en cada una— se
    imprime el nombre corto del carácter, que sigue identificándolo sin
    ambigüedad.
    """
    if byte_winansi(ord(ch)) is not None:
        return ch
    try:
        nombre = unicodedata.name(ch)
    except ValueError:
        return "U+%04X" % ord(ch)
    for prefijo in ("GREEK SMALL LETTER ", "GREEK CAPITAL LETTER ",
                    "CYRILLIC SMALL LETTER ", "CYRILLIC CAPITAL LETTER "):
        if nombre.startswith(prefijo):
            corto = nombre[len(prefijo):].title()
            return corto.lower() if "SMALL" in prefijo else corto
    return "U+%04X" % ord(ch)


def cadena_pdf(texto):
    salida = ["("]
    for ch in texto:
        b = byte_winansi(ord(ch))
        if b is None:
            salida.append("?")
        elif b in (40, 41, 92):
            salida.append("\\" + chr(b))
        elif b < 32 or b > 126:
            salida.append("\\%03o" % b)
        else:
            salida.append(chr(b))
    return "".join(salida) + ")"


def num(v):
    return f"{round(v, 3):g}"


def rgb_pdf(hexcolor):
    n = int(hexcolor[1:], 16)
    return " ".join(num(c / 255) for c in ((n >> 16) & 255, (n >> 8) & 255, n & 255))


def flujo_pagina(p, caracteres, pagina, total):
    """Flujo de contenido de una página, en puntos y con el origen abajo."""
    linea_color, guia_color = COLORES[p.color]
    X = lambda mm: num(mm * MM_A_PT)
    Y = lambda mm: num((p.alto - mm) * MM_A_PT)
    W = lambda mm: num(mm * MM_A_PT)
    o = ["q"]

    def linea(x1, y1, x2, y2, grosor, color):
        o.append(f"q {rgb_pdf(color)} RG {W(grosor)} w [] 0 d "
                 f"{X(x1)} {Y(y1)} m {X(x2)} {Y(y2)} l S Q")

    cw, ch = p.celda_ancho, p.celda_alto
    for i in range(p.por_pagina):
        col, fila = i % p.columnas, i // p.columnas
        x = p.rejilla_x + col * cw
        y = p.rejilla_y + fila * ch
        o.append(f"q {rgb_pdf(guia_color)} RG {W(0.12)} w [] 0 d "
                 f"{X(x)} {Y(y + ch)} {W(cw)} {W(ch)} re S Q")
        if i >= len(caracteres):
            continue
        ch_actual = caracteres[i]
        gx1, gx2 = x + 1, x + cw - 1
        # Continuos y de grosor distinto: el lector los reconoce porque cruzan la
        # celda entera, y los distingue del trazo por ser mucho más finos.
        for dy, grosor in p.renglones:
            linea(gx1, y + dy, gx2, y + dy, grosor, linea_color)
        etiqueta = etiqueta_imprimible(ch_actual)
        tam = 2.6 if len(etiqueta) <= 2 else 1.9
        o.append(f"BT {rgb_pdf(guia_color)} rg /F1 {num(tam * MM_A_PT)} Tf "
                 f"{X(x + cw - 1.2 - 0.55 * tam * len(etiqueta))} {Y(y + p.y_guia)} Td "
                 f"{cadena_pdf(etiqueta)} Tj ET")

    # Las marcas van al final para quedar por encima de cualquier trazo de pauta.
    for mx, my in p.marcas:
        o.append(f"0 0 0 rg {X(mx - 3)} {Y(my + 3)} {W(6)} {W(6)} re f")
    pie = (f"Pagina {pagina} de {total} - imprimir en {p.papel} al 100%, "
           f"sin ajustar a la pagina")
    o.append(f"BT 0 0 0 rg /F1 {num(3 * MM_A_PT)} Tf "
             f"{X(p.marcas[0][0])} {Y(p.alto - 6)} Td {cadena_pdf(pie)} Tj ET")
    o.append("Q")
    return "\n".join(o)


def construir_pdf(p, caracteres):
    paginas = p.paginas(caracteres)
    total = len(paginas)
    wpt, hpt = num(p.ancho * MM_A_PT), num(p.alto * MM_A_PT)

    objetos = [None] * (2 + total * 2 + 1)
    ids_pagina = [3 + i * 2 for i in range(total)]
    id_fuente = 3 + total * 2

    objetos[0] = "<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{i} 0 R" for i in ids_pagina)
    objetos[1] = f"<< /Type /Pages /Count {total} /Kids [{kids}] >>"
    for i, chars in enumerate(paginas):
        cuerpo = flujo_pagina(p, chars, i + 1, total)
        objetos[ids_pagina[i] - 1] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {wpt} {hpt}] "
            f"/Resources << /Font << /F1 {id_fuente} 0 R >> >> "
            f"/Contents {ids_pagina[i] + 1} 0 R >>")
        objetos[ids_pagina[i]] = (
            f"<< /Length {len(cuerpo.encode('latin-1', 'replace'))} >>\n"
            f"stream\n{cuerpo}\nendstream")
    objetos[id_fuente - 1] = ("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                              "/Encoding /WinAnsiEncoding >>")

    salida = "%PDF-1.4\n%\xE2\xE3\xCF\xD3\n"
    offsets = []
    for i, obj in enumerate(objetos):
        offsets.append(len(salida.encode("latin-1", "replace")))
        salida += f"{i + 1} 0 obj\n{obj}\nendobj\n"
    xref = len(salida.encode("latin-1", "replace"))
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n"
    for off in offsets:
        salida += f"{off:010d} 00000 n \n"
    salida += (f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
               f"startxref\n{xref}\n%%EOF\n")
    return salida.encode("latin-1", "replace"), total


def main():
    ap = argparse.ArgumentParser(description="Genera una plantilla de caligrafía en PDF")
    ap.add_argument("--juego", default="espanol",
                    help=f"nombre predefinido ({', '.join(JUEGOS)}) o los caracteres literales")
    ap.add_argument("--papel", default="carta", help="carta, a4 u oficio")
    ap.add_argument("--rejilla", default="6x8", help="columnas x filas, p. ej. 6x8")
    ap.add_argument("--color", default="negro",
                    help="negro (impresora monocroma), rojo o cian (solo en color)")
    ap.add_argument("--salida", default="plantilla.pdf")
    args = ap.parse_args()

    try:
        cols, filas = (int(v) for v in args.rejilla.lower().split("x"))
    except ValueError:
        ap.error("--rejilla debe tener la forma COLUMNASxFILAS, por ejemplo 6x8")

    p = Plantilla(papel=args.papel, columnas=cols, filas=filas, color=args.color)
    caracteres = resuelve_juego(args.juego)
    if not caracteres:
        ap.error("el juego de caracteres quedó vacío")

    datos, total = construir_pdf(p, caracteres)
    destino = Path(args.salida)
    destino.write_bytes(datos)

    sobran = total * p.por_pagina - len(caracteres)
    print(p.resumen())
    print(f"{len(caracteres)} caracteres en {total} página(s), {sobran} celdas libres")
    print(f"escrito: {destino}  ({len(datos) / 1024:.1f} kB)")
    if p.color != "negro":
        print("AVISO: esta pauta necesita impresión en color; en blanco y negro "
              "saldría gris y se confundiría con la tinta.")


if __name__ == "__main__":
    main()
