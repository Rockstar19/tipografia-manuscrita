#!/usr/bin/env python3
"""
Convierte las hojas escritas a mano en un archivo .ttf instalable.

El recorrido es: localizar las cuatro marcas de registro, enderezar la hoja con
una homografía, binarizar, borrar los renglones impresos, recortar cada celda,
vectorizar el trazo y escribir la fuente.

Uso:
    python hoja_a_fuente.py --imagen hoja1.jpg --nombre "Mi Letra"
    python hoja_a_fuente.py --imagen p1.jpg p2.jpg --nombre "Mi Letra" --juego espanol
    python hoja_a_fuente.py --imagen hoja.png --nombre X --diagnostico dx/
"""
import argparse
import sys
import unicodedata
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from geometria import (Plantilla, PX_POR_MM, UPM, ASCENDER, DESCENDER,
                       JUEGOS, resuelve_juego)

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen


# --------------------------------------------------------------------------
# 1. Marcas de registro
# --------------------------------------------------------------------------
def detecta_marcas(img):
    """Localiza los cuatro cuadrados negros, uno por cuadrante.

    Se busca por cuadrante en vez de globalmente porque así la tinta de la
    escritura, que vive en el centro, nunca compite con las marcas, y porque el
    resultado sale ya ordenado: SI, SD, II, ID.
    """
    alto, ancho = img.shape[:2]
    escala = min(1.0, 1100 / max(alto, ancho))
    peq = cv2.resize(img, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    gris = cv2.cvtColor(peq, cv2.COLOR_BGR2GRAY)
    h, w = gris.shape
    bw, bh = int(w * 0.28), int(h * 0.28)

    centros = []
    for qx, qy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        x0 = w - bw if qx else 0
        y0 = h - bh if qy else 0
        region = gris[y0:y0 + bh, x0:x0 + bw]
        umbral = max(40, min(170, int(region.mean()) - 50))
        _, binaria = cv2.threshold(region, umbral, 255, cv2.THRESH_BINARY_INV)
        n, _, stats, cents = cv2.connectedComponentsWithStats(binaria, 8)
        mejor, mejor_area = None, 0
        for i in range(1, n):
            x, y, cw, chh, area = stats[i]
            if area < 20:
                continue
            proporcion = cw / max(chh, 1)
            relleno = area / max(cw * chh, 1)
            # Una marca es un cuadrado macizo: descarta letras y manchas.
            if not (0.5 <= proporcion <= 2.0 and relleno >= 0.6):
                continue
            if area > mejor_area:
                mejor_area, mejor = area, cents[i]
        if mejor is None:
            raise SystemExit(
                "No se encontraron las cuatro marcas de registro. Comprueba que "
                "la hoja entera esté dentro de la foto, con sus cuatro esquinas "
                "visibles y sin sombras fuertes."
            )
        centros.append(((mejor[0] + x0) / escala, (mejor[1] + y0) / escala))
    return np.array(centros, dtype=np.float32)


# --------------------------------------------------------------------------
# 2. Enderezado y binarizado
# --------------------------------------------------------------------------
def endereza(img, marcas, p):
    ancho_px, alto_px = p.lienzo
    destino = np.array([[0, 0], [ancho_px, 0], [0, alto_px], [ancho_px, alto_px]],
                       dtype=np.float32)
    matriz = cv2.getPerspectiveTransform(marcas, destino)
    return cv2.warpPerspective(img, matriz, (ancho_px, alto_px),
                               flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))


def binariza(lienzo, umbral=None):
    """Devuelve la máscara de tinta leyendo el canal rojo.

    El canal rojo se elige porque deja casi blancas las pautas rojas y cianes
    —que así desaparecen solas— y en cambio oscurece la tinta azul de bolígrafo,
    que es con la que se escribe casi siempre. Con pauta negra no separa nada,
    de eso se encarga el borrado por geometría del paso siguiente.
    """
    rojo = lienzo[:, :, 2]
    if umbral is None:
        valor, mascara = cv2.threshold(rojo, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        return mascara.astype(np.uint8), int(valor)
    _, mascara = cv2.threshold(rojo, umbral, 1, cv2.THRESH_BINARY_INV)
    return mascara.astype(np.uint8), umbral


# --------------------------------------------------------------------------
# 3. Borrado de los renglones impresos
# --------------------------------------------------------------------------
def borra_renglones(mascara, p):
    """Quita los renglones sin romper la letra que los cruza o se apoya en ellos.

    Dos criterios encadenados. Primero se confirma que en la banda esperada hay
    de verdad un renglón: una fila cubierta casi de extremo a extremo, algo que
    un trazo de letra no hace. Después se borra columna a columna, pero solo
    donde la mancha es fina: el renglón impreso mide décimas de milímetro y el
    bolígrafo bastante más, así que el grosor distingue lo uno de lo otro sin
    tener que adivinar si el trazo cruza, se apoya o pasa de largo.
    """
    s = PX_POR_MM
    off = int(p.desplazamiento_px)
    cw, ch = p.celda_ancho * s, p.celda_alto * s
    banda = max(3, round(1.1 * s))
    grosor_max = max(3, round(0.95 * s))
    alto, ancho = mascara.shape

    for fila in range(p.filas):
        for dy, _ in p.renglones:
            cy = round(off + fila * ch + dy * s)
            for col in range(p.columnas):
                x0 = round(off + col * cw + 1.2 * s)
                x1 = round(off + (col + 1) * cw - 1.2 * s)
                if x1 - x0 < 12 or cy - banda < 0 or cy + banda >= alto:
                    continue
                sub = mascara[cy - banda:cy + banda + 1, x0:x1]
                cobertura = sub.mean(axis=1)
                pico = int(np.argmax(cobertura))
                if cobertura[pico] <= 0.55:
                    continue                      # aquí no hay renglón
                # El renglón es el bloque contiguo de filas muy cubiertas alrededor
                # del pico. Recoger en cambio todas las filas de la banda que pasen
                # un umbral bajo acaba incluyendo filas de la propia letra cuando
                # esta pasa cerca, y entonces el bloque se vuelve grueso y el
                # criterio de grosor lo protege entero, renglón incluido.
                ini = fin = pico
                while ini - 1 >= 0 and cobertura[ini - 1] >= 0.40:
                    ini -= 1
                while fin + 1 < cobertura.size and cobertura[fin + 1] >= 0.40:
                    fin += 1
                y_ini = cy - banda + ini
                y_fin = cy - banda + fin

                columna_tinta = mascara[y_ini:y_fin + 1, x0:x1].any(axis=0)
                for dx in np.nonzero(columna_tinta)[0]:
                    x = x0 + int(dx)
                    arriba = y_ini
                    while arriba - 1 >= 0 and mascara[arriba - 1, x]:
                        arriba -= 1
                    abajo = y_fin
                    while abajo + 1 < alto and mascara[abajo + 1, x]:
                        abajo += 1
                    if abajo - arriba + 1 > grosor_max:
                        continue                  # hay letra: se deja intacta
                    mascara[y_ini:y_fin + 1, x] = 0
    return mascara


# --------------------------------------------------------------------------
# 4. Vectorizado de una celda
# --------------------------------------------------------------------------
def limpia(recorte, mancha_minima, suavizar=True):
    m = recorte.copy()
    if suavizar:
        m = cv2.medianBlur(m * 255, 3) // 255
    if mancha_minima > 0:
        n, etiquetas, stats, _ = cv2.connectedComponentsWithStats(m, 8)
        conservar = np.zeros(n, dtype=np.uint8)
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] >= mancha_minima:
                conservar[i] = 1
        m = conservar[etiquetas]
    return m.astype(np.uint8)


def area_firmada(puntos):
    x, y = puntos[:, 0], puntos[:, 1]
    return float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)) / 2.0


def a_curvas(poligono, grados_esquina=58, largo_recto=9.0):
    """Convierte un polígono en puntos on-curve y off-curve para TrueType.

    Un vértice se marca como esquina cuando el giro es brusco o cuando une dos
    segmentos largos —un tramo recto de verdad—; el resto se deja como punto de
    control para que la curva siga el trazo sin acusar la rejilla de píxeles.
    """
    n = len(poligono)
    if n < 3:
        return None
    umbral = np.cos(np.radians(grados_esquina))
    previo = np.roll(poligono, 1, axis=0)
    siguiente = np.roll(poligono, -1, axis=0)
    a = poligono - previo
    b = siguiente - poligono
    la = np.linalg.norm(a, axis=1)
    lb = np.linalg.norm(b, axis=1)
    coseno = np.sum(a * b, axis=1) / np.maximum(la * lb, 1e-9)
    esquina = (coseno < umbral) | ((la > largo_recto) & (lb > largo_recto))

    puntos = [(float(pt[0]), float(pt[1]), bool(e)) for pt, e in zip(poligono, esquina)]
    # Entre dos puntos de control seguidos hace falta un punto on-curve; TrueType
    # lo da por implícito en el punto medio, pero escribirlo evita ambigüedades.
    completos = []
    for i, pt in enumerate(puntos):
        completos.append(pt)
        sig = puntos[(i + 1) % len(puntos)]
        if not pt[2] and not sig[2]:
            completos.append(((pt[0] + sig[0]) / 2, (pt[1] + sig[1]) / 2, True))
    if not any(p[2] for p in completos):
        return None
    while not completos[0][2]:
        completos.append(completos.pop(0))
    return completos


def extrae_glifo(mascara, p, col, fila, mancha_minima, suavizar, aire):
    """Devuelve los contornos de una celda en unidades de fuente, o None."""
    x0, x1, y0, y1 = p.recorte_celda(col, fila)
    if y1 > mascara.shape[0] or x1 > mascara.shape[1]:
        return None
    recorte = limpia(mascara[y0:y1, x0:x1], mancha_minima, suavizar)
    if int(recorte.sum()) < 25:
        return None

    contornos, jerarquia = cv2.findContours(recorte, cv2.RETR_CCOMP,
                                            cv2.CHAIN_APPROX_NONE)
    if not contornos:
        return None

    base_local = p.y_base * PX_POR_MM - (y0 - p.desplazamiento_px - fila * p.celda_alto * PX_POR_MM)
    upx = p.unidades_por_px

    figuras, min_x, max_x = [], 1e9, -1e9
    for i, contorno in enumerate(contornos):
        if len(contorno) < 8:
            continue
        aprox = cv2.approxPolyDP(contorno, 1.1, True).reshape(-1, 2)
        if len(aprox) < 3:
            continue
        # a unidades de fuente: X desde el borde del trazo, Y contra la línea base
        pts = np.column_stack([aprox[:, 0].astype(float),
                               (base_local - aprox[:, 1].astype(float))]) * upx
        es_hueco = jerarquia[0][i][3] != -1
        # TrueType espera el contorno exterior en sentido horario (área negativa
        # con el eje Y hacia arriba) y los huecos al revés.
        area = area_firmada(pts)
        if (not es_hueco and area > 0) or (es_hueco and area < 0):
            pts = pts[::-1]
        curva = a_curvas(pts)
        if curva is None:
            continue
        min_x = min(min_x, pts[:, 0].min())
        max_x = max(max_x, pts[:, 0].max())
        figuras.append(curva)

    if not figuras:
        return None

    desplaza = aire - min_x
    figuras = [[(x + desplaza, y, on) for x, y, on in fig] for fig in figuras]
    avance = int(round(max_x - min_x + 2 * aire))
    return {"contornos": figuras, "avance": max(avance, int(2 * aire) + 10)}


# --------------------------------------------------------------------------
# 5. Construcción de la fuente
# --------------------------------------------------------------------------
def sin_acentos(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def nombre_archivo(familia):
    limpio = "".join(c if (c.isalnum() or c in "-_ ") else ""
                     for c in sin_acentos(familia)).strip()
    limpio = "-".join(limpio.split())
    return limpio or "Manuscrita"


def nombre_postscript(familia, estilo):
    # La especificación prohíbe acentos, espacios y ()[]{}<>/% aquí.
    crudo = sin_acentos(f"{familia}-{estilo}")
    limpio = "".join(c for c in crudo if c.isalnum() or c == "-")
    while "--" in limpio:
        limpio = limpio.replace("--", "-")
    return (limpio.strip("-") or "Manuscrita-Regular")[:63]


def construye_fuente(glifos, familia, estilo, ancho_espacio):
    orden = [".notdef", "space"]
    cmap = {32: "space"}
    dibujos = {}
    metricas = {".notdef": (round(UPM * 0.4), 0), "space": (ancho_espacio, 0)}

    lapiz = TTGlyphPen(None)
    dibujos[".notdef"] = lapiz.glyph()
    lapiz = TTGlyphPen(None)
    dibujos["space"] = lapiz.glyph()

    for ch, datos in glifos.items():
        nombre = "uni%04X" % ord(ch)
        if nombre in dibujos:
            continue
        lapiz = TTGlyphPen(None)
        for contorno in datos["contornos"]:
            inicio = next(i for i, pt in enumerate(contorno) if pt[2])
            rotado = contorno[inicio:] + contorno[:inicio]
            lapiz.moveTo((round(rotado[0][0]), round(rotado[0][1])))
            i = 1
            total = len(rotado)
            while i <= total:
                actual = rotado[i % total]
                if actual[2]:
                    lapiz.lineTo((round(actual[0]), round(actual[1])))
                    i += 1
                else:
                    siguiente = rotado[(i + 1) % total]
                    lapiz.qCurveTo((round(actual[0]), round(actual[1])),
                                   (round(siguiente[0]), round(siguiente[1])))
                    i += 2
            lapiz.closePath()
        dibujos[nombre] = lapiz.glyph()
        metricas[nombre] = (datos["avance"], 0)
        cmap[ord(ch)] = nombre
        orden.append(nombre)

    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(orden)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(dibujos)
    fb.setupHorizontalMetrics(metricas)
    fb.setupHorizontalHeader(ascent=ASCENDER, descent=DESCENDER)
    fb.setupNameTable({
        "familyName": familia,
        "styleName": estilo,
        "uniqueFontIdentifier": f"{familia} {estilo}; hecha a mano",
        "fullName": f"{familia} {estilo}" if estilo.lower() != "regular" else familia,
        "psName": nombre_postscript(familia, estilo),
        "version": "Version 1.000",
    })
    fb.setupOS2(sTypoAscender=ASCENDER, sTypoDescender=DESCENDER,
                usWinAscent=ASCENDER, usWinDescent=abs(DESCENDER))
    fb.setupPost(isFixedPitch=0)
    return fb


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Convierte hojas escritas a mano en un .ttf")
    ap.add_argument("--imagen", nargs="+", required=True,
                    help="foto o escaneo de cada hoja, en el orden de las páginas")
    ap.add_argument("--nombre", default="Manuscrita", help="nombre de la tipografía")
    ap.add_argument("--estilo", default="Regular")
    ap.add_argument("--juego", default="espanol",
                    help="el mismo juego con el que se generó la plantilla")
    ap.add_argument("--papel", default="carta")
    ap.add_argument("--rejilla", default="6x8")
    ap.add_argument("--color", default="negro")
    ap.add_argument("--umbral", type=int, default=None,
                    help="umbral de tinta 0-255; por defecto se calcula con Otsu")
    ap.add_argument("--mancha-minima", type=int, default=15,
                    help="área en px por debajo de la cual una mancha se descarta")
    ap.add_argument("--aire", type=int, default=45,
                    help="espacio lateral de cada glifo, en unidades de fuente")
    ap.add_argument("--espacio", type=int, default=260,
                    help="ancho del carácter espacio, en unidades de fuente")
    ap.add_argument("--salida", default=None)
    ap.add_argument("--diagnostico", default=None,
                    help="carpeta donde guardar imágenes del proceso")
    args = ap.parse_args()

    try:
        cols, filas = (int(v) for v in args.rejilla.lower().split("x"))
    except ValueError:
        ap.error("--rejilla debe tener la forma COLUMNASxFILAS")

    p = Plantilla(papel=args.papel, columnas=cols, filas=filas, color=args.color)
    caracteres = resuelve_juego(args.juego)
    paginas = p.paginas(caracteres)
    print(p.resumen())

    if len(args.imagen) > len(paginas):
        ap.error(f"diste {len(args.imagen)} imágenes pero el juego solo ocupa "
                 f"{len(paginas)} página(s)")

    dx = Path(args.diagnostico) if args.diagnostico else None
    if dx:
        dx.mkdir(parents=True, exist_ok=True)

    glifos = {}
    for indice, ruta in enumerate(args.imagen):
        img = cv2.imread(str(ruta), cv2.IMREAD_COLOR)
        if img is None:
            raise SystemExit(f"no pude abrir la imagen: {ruta}")
        marcas = detecta_marcas(img)
        lienzo = endereza(img, marcas, p)
        mascara, umbral = binariza(lienzo, args.umbral)
        borra_renglones(mascara, p)

        if dx:
            cv2.imwrite(str(dx / f"pagina{indice + 1}-enderezada.png"), lienzo)
            cv2.imwrite(str(dx / f"pagina{indice + 1}-tinta.png"),
                        (1 - mascara) * 255)

        de_esta = paginas[indice]
        leidos = 0
        for i, ch in enumerate(de_esta):
            datos = extrae_glifo(mascara, p, i % p.columnas, i // p.columnas,
                                 args.mancha_minima, True, args.aire)
            if datos:
                glifos[ch] = datos
                leidos += 1
        print(f"página {indice + 1}: {leidos} de {len(de_esta)} celdas con letra "
              f"(umbral {umbral})")

    if not glifos:
        raise SystemExit(
            "No se leyó ninguna letra. Lo más habitual es que el trazo sea "
            "demasiado fino o claro: repite con bolígrafo de 0,7 mm o más, o "
            "prueba a subir --umbral."
        )

    fb = construye_fuente(glifos, args.nombre.strip() or "Manuscrita",
                          args.estilo.strip() or "Regular", args.espacio)
    destino = Path(args.salida) if args.salida else Path(
        nombre_archivo(args.nombre) + ".ttf")
    fb.save(str(destino))
    faltan = [c for c in caracteres[:sum(len(x) for x in paginas[:len(args.imagen)])]
              if c not in glifos]
    print(f"escrito: {destino}  ({destino.stat().st_size / 1024:.1f} kB, "
          f"{len(glifos)} glifos)")
    if faltan:
        print("celdas vacías o ilegibles: " + " ".join(faltan))


if __name__ == "__main__":
    main()
