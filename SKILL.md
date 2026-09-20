---
name: tipografia-manuscrita
description: Convierte letra escrita a mano en una fuente .ttf instalable, de principio a fin. Genera la plantilla de caligrafía en PDF (papel Carta, A4 u oficio; rejilla y juego de caracteres a medida) y después lee la foto de la hoja escrita y construye el archivo .ttf. Úsala siempre que se hable de crear una tipografía o fuente propia, digitalizar la caligrafía de alguien, convertir letra manuscrita en fuente, hacer una plantilla de caligrafía o pauta para escribir, vectorizar letras escaneadas, o generar un .ttf/.otf personalizado — incluso si no se nombra la palabra "plantilla" y solo se pide "una fuente con mi letra" o "pasar esta hoja escrita a tipografía". También cubre juegos no latinos (griego, símbolos técnicos y matemáticos) para notación de ingeniería o tesis.
---

# Tipografía a partir de letra manuscrita

Este skill cierra el ciclo completo: imprimir una hoja pautada, escribirla a mano,
fotografiarla y obtener un `.ttf` que se instala como cualquier otra fuente.

Todo ocurre con dos scripts que comparten un único módulo de geometría. Esa
geometría es el contrato entre ambos: la plantilla dibuja los renglones en unas
posiciones concretas y el lector los busca exactamente ahí para borrarlos. Por eso
**los mismos parámetros de papel, rejilla y juego de caracteres deben pasarse a los
dos scripts**; si no coinciden, el lector busca la pauta donde no está y los glifos
salen sucios o vacíos.

## Flujo de trabajo

### 1. Generar la plantilla

```bash
python scripts/crear_plantilla.py --salida plantilla.pdf
python scripts/crear_plantilla.py --juego griego --papel a4 --rejilla 5x7 --salida griega.pdf
python scripts/crear_plantilla.py --juego "ΔΩμσ∑∫≈" --rejilla 4x5 --salida simbolos.pdf
```

| Opción | Por defecto | Para qué |
|---|---|---|
| `--juego` | `espanol` | `basico`, `espanol`, `extendido`, `griego`, `matematico`, o los caracteres literales |
| `--papel` | `carta` | `carta`, `a4`, `oficio` |
| `--rejilla` | `6x8` | columnas × filas; celdas más grandes ayudan si la letra es grande o muy adornada |
| `--color` | `negro` | `negro` para impresora monocroma; `rojo` o `cian` solo si se imprime en color |
| `--salida` | `plantilla.pdf` | |

Entrega el PDF a la persona y dile lo que de verdad condiciona el resultado:

- Imprimir **al 100%**, nunca «ajustar a la página». Si la escala cambia, la
  rejilla deja de caer donde el lector la espera.
- Escribir con bolígrafo o rotulador de **0,7 mm o más**. El lector separa la letra
  del renglón comparando grosores, así que un trazo fino o a lápiz se confunde con
  la línea impresa y desaparece con ella.
- Apoyar cada letra en la línea base gruesa, y no invadir los cuatro cuadrados
  negros de las esquinas: son las marcas que permiten enderezar la foto.
- Si una letra sale mal, imprimir otra hoja en vez de tacharla.

### 2. Leer la hoja y construir la fuente

```bash
python scripts/hoja_a_fuente.py --imagen hoja1.jpg --nombre "Mi Letra"
python scripts/hoja_a_fuente.py --imagen p1.jpg p2.jpg --nombre "Mi Letra" --estilo Regular
python scripts/hoja_a_fuente.py --imagen g.jpg --juego griego --papel a4 --rejilla 5x7 --nombre "Griega"
```

Las imágenes se pasan **en el orden de las páginas**. Vale una foto de móvil: el
script localiza las marcas de registro, corrige la perspectiva y el giro, y trabaja
sobre la hoja ya enderezada.

| Opción | Por defecto | Para qué |
|---|---|---|
| `--nombre` | `Manuscrita` | el nombre que aparecerá en Word y en el menú de fuentes |
| `--estilo` | `Regular` | |
| `--juego`, `--papel`, `--rejilla`, `--color` | como la plantilla | **deben coincidir con los que se usaron al generarla** |
| `--umbral` | automático (Otsu) | súbelo si el trazo sale roto o pálido |
| `--mancha-minima` | `15` | súbelo si quedan motas sueltas en los glifos |
| `--aire` | `45` | espacio lateral de cada glifo, en unidades de fuente |
| `--espacio` | `260` | ancho del carácter espacio |
| `--diagnostico` | — | carpeta donde guardar la hoja enderezada y la máscara de tinta |

### 3. Comprobar antes de entregar

Un `.ttf` que no se puede instalar no sirve de nada, y el fallo no se ve hasta que
alguien lo prueba. Vale la pena renderizar una muestra y mirarla:

```python
from PIL import Image, ImageDraw, ImageFont
f = ImageFont.truetype("Mi-Letra.ttf", 56)
im = Image.new("RGB", (1100, 260), "white")
d = ImageDraw.Draw(im)
d.text((20, 20), "El veloz murciélago hindú comía feliz", font=f, fill="black")
d.text((20, 110), "¿Qué año? 1929. ABCDEFG", font=f, fill="black")
im.save("muestra.png")
```

Mira la imagen y comprueba tres cosas: que no queden trozos de renglón pegados bajo
las letras, que las tildes y la ñ estén presentes, y que todas se apoyen en la misma
línea base. Si algo falla, el apartado de problemas de abajo dice qué ajustar.

Para instalar en Windows: clic derecho sobre el `.ttf` → «Instalar para todos los
usuarios». Si Word estaba abierto, cerrarlo y volver a abrirlo.

## Qué hace el lector por dentro

Conviene conocerlo para diagnosticar, porque casi todos los problemas vienen de una
de estas etapas:

1. **Marcas de registro.** Busca un cuadrado negro macizo en cada cuadrante. Busca
   por cuadrante y no en toda la hoja, así la tinta del centro nunca compite con las
   marcas y el resultado sale ya ordenado.
2. **Enderezado.** Una homografía lleva esas cuatro marcas a las esquinas de un
   lienzo de medidas conocidas, corrigiendo giro y perspectiva de golpe.
3. **Binarizado.** Umbral de Otsu sobre el **canal rojo**. Ese canal deja casi
   blancas las pautas rojas y cianes, y en cambio oscurece la tinta azul de
   bolígrafo, que es la habitual.
4. **Borrado de renglones.** Con pauta negra el color no separa nada, así que el
   renglón se quita por geometría: se sabe dónde cae, se confirma que hay una marca
   que cruza la celda de lado a lado, y se borra columna a columna solo donde la
   mancha es fina. Donde es gruesa hay letra —cruzando el renglón o apoyada en él— y
   se conserva entera.
5. **Vectorizado.** Contornos con jerarquía (para que los huecos de la a, la o o la
   e queden huecos), simplificación Douglas-Peucker y conversión a curvas
   cuadráticas, marcando como esquina solo los giros bruscos y los tramos rectos
   largos.
6. **Fuente.** Se escribe un TrueType real, con contornos en la tabla `glyf`. La
   altura de ascendente de la plantilla equivale a 800 unidades sobre la línea base:
   de ahí sale la escala, y por eso las proporciones salen bien sin ajustes.

## Cuando algo sale mal

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| «No se encontraron las cuatro marcas» | falta una esquina en la foto, o hay sombra fuerte | repetir la foto con la hoja entera dentro del encuadre y luz pareja |
| Ninguna celda con letra | trazo demasiado fino o claro | rehacer con bolígrafo más grueso, o subir `--umbral` |
| Trozos de renglón bajo las letras | la escala de impresión no fue del 100%, o los parámetros no coinciden con la plantilla | reimprimir al 100%; verificar `--papel`, `--rejilla` y `--juego` |
| Letras rotas o con huecos | umbral demasiado bajo | subir `--umbral` (p. ej. `--umbral 170`) |
| Motas sueltas dentro de los glifos | ruido del papel o del sensor | subir `--mancha-minima` (p. ej. `40`) |
| Letras pegadas al escribir | demasiado juntas en el renglón | subir `--aire` a 60–80 |
| Glifos desplazados de la línea base | se escribió flotando o cruzando la base | rehacer esas celdas apoyando la letra en la línea gruesa |

Cuando el resultado no cuadre, `--diagnostico dx/` guarda la hoja ya enderezada y la
máscara de tinta tras borrar los renglones. Esa segunda imagen es la que de verdad
lee el programa: si ahí se ven restos de pauta o la letra aparece rota, el problema
está antes del vectorizado y ninguna opción de la fuente lo va a arreglar.

## Detalles que rara vez hacen falta

`references/geometria-y-decisiones.md` explica de dónde salen las medidas de la
plantilla, por qué la pauta es negra y fina en lugar de gruesa o de color, cómo se
comporta cada color con distintas impresoras, y qué tocar para adaptar el sistema a
otro alfabeto o a una caligrafía muy distinta de la habitual. Léelo si hay que
cambiar la geometría, no para el uso normal.

## Dependencias

`opencv-python-headless`, `numpy`, `fontTools` y `Pillow`. Si falta alguna:

```bash
pip install opencv-python-headless numpy fonttools pillow
```

El generador de plantillas no necesita ninguna: escribe el PDF a mano y corre con
Python solo.
