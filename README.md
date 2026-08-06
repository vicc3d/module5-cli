# Module 5 — terminal

Versión nativa de terminal del juego de pentominós Module 5 (hay también una
versión web en Three.js). Mismos pentominós, mismos 20 niveles, la misma
cuenta de 2339 soluciones únicas y **códigos de desafío intercambiables con la
versión web**.

Sin X11, sin entorno gráfico, sin compilar y sin instalar nada: es Python 3 con
pura biblioteca estándar. Funciona en Linux y macOS por SSH, en tmux o en una
consola pelada.

![Demo de Module 5 en la terminal: menú, colocar piezas con rotar/voltear, y zoom del tablero](demo.gif)

## Jugar

```bash
./module5
```

Y nada más. El lanzador busca un Python 3 (≥ 3.8) y arranca.

Si preferís no usar el lanzador:

```bash
python3 -m m5
```

### Un solo archivo

Para llevarlo a otra máquina alcanza con copiar **un** archivo. Se genera con
`zipapp`, que también es de la biblioteca estándar:

```bash
./build.sh
```

Eso produce `m5.pyz` (~42 KB), ejecutable y autocontenido:

```bash
./m5.pyz
```

Copialo a cualquier Linux o macOS con Python 3 y corre tal cual — nada de
`pip install`, nada de compilar. Si `m5.pyz` está junto al lanzador, `./module5`
lo usa automáticamente.

## Controles

Todo se juega con el teclado. El mouse funciona si la terminal lo soporta, pero
nunca es necesario.

| Acción | Teclas |
| --- | --- |
| Mover la pieza / el cursor | `←↑↓→` o `WASD` |
| Elegir pieza | `1`-`9`, `0`, `-`, `=` (F I L N P T U V W X Y Z) o `TAB` |
| Rotar / Voltear | `R` / `F` |
| Colocar | `Enter` o `Espacio` |
| Retirar una pieza puesta | `Backspace` sobre ella, o su misma tecla |
| Reiniciar el tablero | `X` |
| Zoom del tablero | `+` / `_` (Shift-`=` / Shift-`-`) o la rueda del mouse |
| Ayuda | `?` |
| Volver / cancelar | `Esc` |
| Salir | `Ctrl-C`, o `q` desde el menú |

Con el mouse: clic coloca o retira, clic derecho cancela la selección, y en el
editor se puede arrastrar para pintar.

## Modos

**01 — Clásico.** Llenar el tablero 6×10 con las 12 piezas. El puntaje es el
tiempo. Cada solución se registra en forma canónica (invariante a rotaciones de
180° y espejos del tablero) y no se puede repetir: hay **2339 soluciones
únicas** (9356 contando simetrías) por descubrir. Es exactamente la misma
canonicalización que la versión web, así que la cuenta significa lo mismo en
las dos.

**02 — Formas.** 20 niveles de dificultad creciente (de 1 a 12 piezas). La
silueta objetivo se ve en el panel lateral, comprimida con medios bloques. Cada
nivel desbloquea el siguiente.

**Mis desafíos.** Se pinta una silueta propia en una grilla de 6×10 (múltiplos
de 5, hasta 60 celdas) y un solver de cobertura exacta verifica que tenga
solución antes de dejar guardarla. Cada desafío se exporta como un código de
texto:

```
M5.eyJuIjoiQ3J1eiBQcnVlYmEiLCJyIjozLCJjIjozLCJiIjoiZVFBPSJ9
```

Ese formato es **byte por byte el mismo** que el de la versión web: un desafío
creado en la terminal se importa en el navegador y al revés. El código se
re-verifica al importar. Sin pistas durante el juego, como en el puzzle físico.

### Tamaño del tablero

El tablero **se escala al espacio disponible**: elige la celda más grande que
entre en la terminal (de 2×1 hasta 8×4 caracteres) y se re-escala solo al
cambiar el tamaño de la ventana, sin reiniciar la partida. Un tablero de 60
celdas se queda en celdas medianas —estirarlo más separa tanto las letras que
las piezas dejan de leerse como una sola figura— mientras que las siluetas
chicas de los primeros niveles se agrandan más para no quedar perdidas en el
medio de la pantalla.

Ese automático se puede pisar con **`+` y `_`** (en teclado US, Shift-`=` y
Shift-`-`; sin Shift esas teclas ya eligen las piezas Y y Z) o con la **rueda
del mouse**, como el pellizco de la vista ASCII en la web. El zoom manual llega
más lejos que el automático, pero siempre se recorta a lo que entre en pantalla,
así que acercarse de más nunca desborda el tablero. Vale también en el editor de
desafíos, se recuerda entre sesiones, y si al alejarte volvés justo a la escala
que el juego elegiría solo, vuelve al modo automático y se sigue adaptando al
redimensionar.

## Configuración

En `CONFIGURACIÓN`: idioma (español / inglés, detectado de `LANG`), tema, mouse,
5 slots de partidas guardadas y borrado del progreso.

### Temas

| Tema | |
| --- | --- |
| `neon` | Neón sobre negro (por defecto): cada pieza es una baldosa de color |
| `ascii` | Fósforo verde, texto puro — el equivalente del tema ASCII de la web |
| `blueprint` | Plano técnico en azul |
| `mono` | Sin color, para terminales sobrias |

El juego detecta lo que la terminal soporta y se adapta: color de 24 bits si hay
`COLORTERM=truecolor`, 256 colores, 16 colores, o sin color. Respeta `NO_COLOR`.

Los caracteres también se adaptan. Las flechas y el punto medio tienen ancho
"ambiguo" y algunas terminales los pintan al doble de ancho, lo que correría los
bordes de las cajas; en consolas donde eso es probable (`TERM=linux`, `dumb`) el
juego usa un juego de glifos ASCII. Se puede forzar con `--ascii`.

## Opciones

```
--lang {es,en}                  idioma
--theme {neon,ascii,blueprint,mono}
--ascii                         solo caracteres ASCII
--no-mouse                      no activar el mouse
--no-color                      sin color
--save-dir DIR                  dónde guardar el progreso
```

## Dónde se guarda el progreso

- Linux: `$XDG_DATA_HOME/module5/save.json` (o `~/.local/share/module5/`)
- macOS: `~/Library/Application Support/module5/save.json`

Un solo JSON, escrito de forma atómica (archivo temporal + `rename`) para que no
quede corrupto si el proceso muere a mitad de camino. `MODULE5_HOME` o
`--save-dir` lo mueven a otro lado.

## Pruebas

```bash
python3 tests/test_smoke.py    # lógica y dibujo, sin terminal
python3 tests/test_pty.py      # integración en una pty real
```

`test_smoke.py` juega partidas completas (resuelve el tablero con el solver y
coloca pieza por pieza por el camino real del juego), comprueba que los 20
niveles sean resolubles, que las soluciones repetidas y las simétricas se
rechacen, que los códigos coincidan con los de la versión web, y que ninguna
pantalla explote en 9 tamaños × 4 temas × 4 modos de color × 2 juegos de glifos,
más 4000 eventos de entrada aleatorios.

`test_pty.py` levanta el juego en una pseudo-terminal real y verifica el modo
raw, la pantalla alternativa, el mouse, `SIGWINCH` y que al salir la terminal
quede como estaba.

## Estructura

| | |
| --- | --- |
| `m5/pieces.py` | los 12 pentominós, orientaciones, paleta y teclas |
| `m5/levels.py` | los 20 niveles + el tablero clásico |
| `m5/solver.py` | cobertura exacta con máscaras de bits, poda por regiones y cancelación |
| `m5/term.py` | modo raw, pantalla alternativa, render diferencial, teclado y mouse |
| `m5/glyphs.py` | los dos juegos de glifos (Unicode / ASCII) |
| `m5/theme.py` | los cuatro temas |
| `m5/ui.py` | marcos, tablero, bandeja, siluetas, campo de texto |
| `m5/game.py` | estado de la partida, fantasma, reloj, solución canónica |
| `m5/screens.py` | menú, niveles, juego, editor, configuración, modales |
| `m5/app.py` | pila de pantallas, bucle principal, finalización |
| `m5/store.py` | persistencia y códigos de desafío |

### Notas de implementación

**No usa `curses`.** Se necesitaba color de 24 bits para la paleta neón, y un
buffer propio permite volcar solo las celdas que cambiaron: un frame en reposo
manda **cero bytes**, lo que importa sobre SSH y deja el uso de CPU en nada.
Además, cada frame va envuelto en el "synchronized output" (DEC 2026), así que
no se ve el barrido al repintar.

**El solver corre en el hilo principal.** Con el GIL, un hilo no ayudaría: el
solver le devuelve el control al render cada tantos nodos mediante un callback,
que gira el spinner y permite cancelar con `Esc`. Verificar el 6×10 completo
—el peor caso— toma ~1,4 s.

**Al salir, la terminal queda como estaba** incluso si el juego revienta o lo
suspenden con `Ctrl-Z`: el `Terminal` es un context manager y engancha
`SIGTSTP`/`SIGCONT` para restaurar y rehacer el modo raw.

## Créditos

**Concepto y desarrollo** — [Victor Crespo](https://3dvic.com)

## Licencia

MIT — ver [LICENSE](LICENSE).
