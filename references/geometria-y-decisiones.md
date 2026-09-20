# Geometría de la plantilla y por qué está así

Este documento explica de dónde salen las medidas y las decisiones de diseño, para
que quien tenga que cambiarlas sepa qué se rompe al tocarlas. Para el uso normal no
hace falta: basta con SKILL.md.

Todas las constantes viven en `scripts/geometria.py`. Los dos scripts importan de
ahí, así que cambiar un valor en ese módulo mantiene plantilla y lector
sincronizados. Copiar los números a otro sitio es la forma más rápida de que dejen
de cuadrar.

## Índice

1. [El rectángulo de referencia](#el-rectángulo-de-referencia)
2. [La rejilla y la celda](#la-rejilla-y-la-celda)
3. [La pauta dentro de la celda](#la-pauta-dentro-de-la-celda)
4. [Escala: de milímetros a unidades de fuente](#escala-de-milímetros-a-unidades-de-fuente)
5. [Colores de pauta y tipos de impresora](#colores-de-pauta-y-tipos-de-impresora)
6. [Por qué las líneas son finas](#por-qué-las-líneas-son-finas)
7. [El área de lectura y la letra guía](#el-área-de-lectura-y-la-letra-guía)
8. [Limitaciones conocidas](#limitaciones-conocidas)
9. [Adaptar a otro alfabeto o a otra caligrafía](#adaptar-a-otro-alfabeto-o-a-otra-caligrafía)

## El rectángulo de referencia

Las cuatro marcas negras se centran a **12,7 mm** (media pulgada) de cada borde.
Esa distancia no es estética: es el margen que cualquier impresora doméstica puede
imprimir sin recortar. Más cerca del borde y algunas impresoras se comerían una
marca, con lo que la hoja dejaría de poder enderezarse.

Los centros de esas marcas definen el rectángulo que el lector lleva a las esquinas
del lienzo. Todo lo demás se mide desde ahí, no desde el borde del papel, porque el
papel puede estar cortado con holgura y la foto nunca lo captura exacto.

Cada marca es un cuadrado macizo de 6 mm. Macizo y cuadrado a propósito: el
detector descarta manchas comprobando que la proporción ancho/alto ronde 1 y que el
relleno supere el 60 %, y así no confunde una marca con una letra o una sombra.

## La rejilla y la celda

La rejilla se mete **5 mm hacia dentro** del rectángulo de referencia
(`SEPARACION_REJILLA`). Sin esa separación, la mitad de cada marca caería dentro de
las celdas de las esquinas y se leería como tinta del glifo: cuatro letras saldrían
con un cuadrado negro pegado. Fue un defecto real del primer diseño.

Con Carta y rejilla 6×8 la celda mide 30,08 × 30,50 mm y caben 48 caracteres por
hoja, así que el juego español completo ocupa dos páginas.

## La pauta dentro de la celda

Los cuatro renglones se expresan como **fracción de la altura de la celda**, no en
milímetros fijos:

| Renglón | Fracción | En una celda de 30,5 mm |
|---|---|---|
| Ascendente (altura de mayúsculas y de b, d, l) | 0,197 | 6,00 mm |
| Altura de la x (cuerpo de las redondas) | 0,418 | 12,75 mm |
| Línea base | 0,787 | 24,00 mm |
| Descendente (colas de g, j, p, q, y) | 0,934 | 28,50 mm |

Al ser fracciones, una rejilla más holgada o más apretada conserva las proporciones
de la escritura en lugar de deformarlas. Si fueran milímetros fijos, una celda
grande dejaría la pauta apelotonada arriba y una pequeña no tendría sitio.

## Escala: de milímetros a unidades de fuente

La distancia entre el renglón de ascendente y la línea base **es** la altura de
ascendente de la fuente, fijada en 800 unidades sobre un em de 1000. De ahí sale
todo lo demás:

```
unidades_por_mm = 800 / (y_base − y_ascendente)
```

Con la celda estándar salen 44,4 unidades por milímetro. Esto es lo que hace que
las proporciones salgan bien solas: quien escribe tocando las guías produce, sin
saberlo, una fuente con métricas correctas. No hay que normalizar tamaños después,
que es donde otras herramientas deforman la letra.

El descendente queda en −200 unidades, el reparto habitual 800/200 de un em de 1000.

El lienzo enderezado trabaja a **8 píxeles por milímetro** (`PX_POR_MM`). Con eso
una celda ronda los 240 × 244 px: suficiente para que el trazo tenga cuerpo y
barato de procesar. Subirlo afina el contorno y encarece el trazado de forma
cuadrática.

## Colores de pauta y tipos de impresora

| Color | Canal rojo | Impresora monocroma | Cómo se borra |
|---|---|---|---|
| Negro | 0 | **sí** | por geometría |
| Rojo `#FF4D4D` | 255 | no | desaparece en el canal rojo, y además por geometría |
| Cian `#9DDCEC` | 157 | no | igual que el rojo, con menos margen |

El binarizado lee **solo el canal rojo**. Un color con canal rojo alto queda ahí tan
blanco como el papel y desaparece sin más; la tinta azul de bolígrafo, en cambio,
tiene canal rojo bajo (≈35) y se oscurece. Ese es el truco clásico de las plantillas
de caligrafía a color.

Con una impresora en blanco y negro ese truco no sirve: el rojo sale como gris medio
o como trama de puntos negros, y se leería como tinta. Por eso **el negro es el
valor por defecto**, y por eso el borrado por geometría existe: es lo que permite
que el sistema funcione con la impresora que casi todo el mundo tiene.

El rojo sigue siendo la mejor opción si hay impresora en color, porque su canal rojo
de 255 lo borra incluso antes de llegar al paso geométrico.

## Por qué las líneas son finas

El lector distingue el renglón del trazo por el **grosor**. El renglón impreso mide
décimas de milímetro; el bolígrafo, 0,7 mm o más. Cuanto mayor sea esa diferencia,
más limpio el borrado.

| Renglón | Grosor |
|---|---|
| Base | 0,40 mm |
| Ascendente | 0,18 mm |
| Altura de x y descendente | 0,12 mm |
| Borde de celda | 0,12 mm |

La base es la más gruesa porque es la referencia que la persona necesita ver
mientras escribe; aun así se mantiene muy por debajo del trazo de un bolígrafo.

Las líneas son **continuas**, no punteadas. El lector reconoce un renglón porque
cruza la celda de lado a lado, algo que ningún trazo de letra hace; una línea
punteada no daría esa firma y no se detectaría.

El umbral de grosor está en `0,95 × PX_POR_MM` píxeles. Si alguien escribe con un
trazo de 0,5 mm, la suma de trazo y línea puede quedar por debajo y el punto de
apoyo se borraría. De ahí la insistencia en el bolígrafo grueso.

## El área de lectura y la letra guía

Cada celda lleva impresa en su esquina la letra que toca escribir. Con pauta de
color daba igual dónde estuviera, porque desaparecía; con pauta negra se leería como
parte del glifo. Por eso la letra guía se coloca **por encima del renglón de
ascendente** y el área de lectura empieza por debajo de ella:

```
pad_superior = y_ascendente − 1,6 mm
```

Como la zona de escritura arranca en el renglón de ascendente, recortar ahí no pierde
nada del trazo. A los lados y abajo el margen es de 2 mm, suficiente para absorber
el error de registro sin comerse la letra.

El recorte llega dos píxeles más abajo del renglón de descendente para no cortar las
colas de g, j, p, q, y.

En alfabetos que Helvetica no puede mostrar —griego, cirílico— la letra guía se
imprime como nombre corto («Alpha», «Beta»), porque el PDF usa las fuentes base y
ninguna de ellas cubre esos alfabetos. Sigue identificando la celda sin ambigüedad.

## Limitaciones conocidas

**Trazos horizontales sobre la línea base.** Una letra cuya base sea un trazo
horizontal ancho apoyado justo en el renglón (la Δ griega, o una L muy plana) funde
su trazo con la línea. El criterio de grosor conserva entonces la columna entera, y
puede quedar un resto de renglón sobresaliendo a los lados de la letra. Se prefiere
este fallo al contrario: cortar la base de la letra sería peor que dejar un resto.
Si molesta, escribir esa letra un pelo por encima de la línea lo evita.

**Trazo fino.** Ya cubierto arriba: por debajo de 0,5 mm el sistema no puede separar
la letra del renglón con fiabilidad.

**Una sola variante por carácter.** Cada celda produce un glifo. No hay alternancia
de formas ni ligaduras, así que un texto largo se nota repetitivo comparado con la
escritura real.

**Sin kerning.** El espaciado sale del ancho de cada glifo más el aire lateral.
Pares como «Av» o «To» quedan más sueltos de lo que los ajustaría un tipógrafo.

## Adaptar a otro alfabeto o a otra caligrafía

- **Alfabeto nuevo**: basta con pasar los caracteres a `--juego`. Si se va a usar a
  menudo, añadirlo al diccionario `JUEGOS` de `geometria.py`.
- **Letra muy grande o muy adornada**: bajar el número de celdas (`--rejilla 4x6`)
  para que cada una sea más amplia. Las proporciones se mantienen solas.
- **Caligrafía con ascendentes y descendentes muy largos**: ajustar `F_ASCENDENTE` y
  `F_DESCENDENTE` en `geometria.py`. Hay que tocar los dos scripts a la vez, y por
  eso las constantes están en un módulo compartido: cambiarlas ahí basta.
- **Escritura de derecha a izquierda o vertical**: el sistema asume celdas
  independientes y una línea base horizontal. Serviría para capturar los glifos,
  pero la fuente resultante necesitaría metadatos de dirección que estos scripts no
  escriben.
