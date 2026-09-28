# Sculptor’s Hoard

[English](README.md)

**Convierte texturas pintadas de personajes en relieve 3D editable.** Es un espacio de trabajo local para preparar mapas de altura con Blender Figure Tools. Interpreta qué representa cada superficie del modelo antes de decidir cómo desplazarla: un párpado, una pupila, una hebilla y una sombra pintada no deben recibir el mismo tratamiento.

## Qué hace

- **Preparación semántica:** observa la figura completa y asocia partes visibles con regiones UV y posiciones 3D. Conserva evidencias por pieza para que el artista pueda revisar lo que ha interpretado.
- **Posado desde imagen de referencia, experimental:** propone una pose de rig ACNH a partir de una tarjeta de personaje u otra imagen y guarda una copia independiente de Blender. [Uso y límites](docs/REFERENCE_POSE.md).
- **Comprobación en 3D real:** Blender ejecuta los nodos instalados de Figure Tools; la revisión compara el resultado con el original y un control de altura uniforme, incluidas vistas cercanas de la cara.
- **Mapas grandes:** salida PNG RGBA a resolución nativa con alturas de 16 bits, procesamiento por filas con memoria acotada, padding UV y caché por contenido.
- **Edición útil:** ajustes en lenguaje natural, alturas vinculadas, fusión y división de grupos, contraste de relieve, guardado automático, versiones, deshacer y rehacer.
- **Producción local:** cola persistente de figuras, recuperación por fase y selección y observación de modelos locales.
- **Evidencia reproducible:** conserva entradas y respuestas de modelos, máscaras, planes, mapas, parámetros de render, mediciones de geometría y escenas Blender.

## Arranque

El entorno de producción comprobado es **Windows, Python 3.12/3.13, Node.js, Blender 5.0 con Figure Tools y Ollama**. Figure Tools es una dependencia externa; este repositorio no incluye su código ni sus recursos.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
npm ci
npm run build
.venv\Scripts\python start.py
```

También puedes abrir **Abrir Sculptors Hoard.vbs** tras instalarlo. La ventana de escritorio arranca su servicio local; al cerrarla, los trabajos ya en cola pueden continuar. Si Blender está en otra ruta, configura `SCULPTORS_HOARD_BLENDER`. El archivo `.blend` es la fuente principal de mallas visibles, pose, materiales e imágenes aplicadas. Los recursos privados y datos de trabajo generados no se publican en Git.

En **Equipo y lotes**, elige un modelo de visión instalado, escanea escenas `.blend`, prepara figuras, revisa el resultado y exporta mapas nativos, una escena editable o STL. El complemento `blender/relief_bridge.py` comunica Blender con la aplicación.

## Pruebas y límites

```powershell
python -m pytest -q
npm run build
```

Las pruebas deterministas cubren máscaras, salida nativa, padding UV, continuidad, comandos, conflictos de revisión, historial y recuperación de colas. Las pruebas con Blender y visión reales se documentan aparte en [evaluación](docs/EVALUATION.md). Los modelos de visión aún se equivocan en detalles semánticos; sus propuestas y la geometría resultante requieren revisión. Una malla cerrada por sí sola no demuestra que una figura esté lista para imprimir.

Código bajo [licencia MIT](LICENSE); modelos, complementos y recursos externos conservan sus licencias.
