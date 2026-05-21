# 🎤 Jurado Virtual de Trova

Aplicación web para análisis técnico automático de trovas en tiempo real.
Soporta **trova sencilla (4 versos)** y **trova dobleteada (8 versos)**.

## Características

- 🎙 **Grabación de audio** desde el micrófono del navegador
- 📝 **Transcripción automática** via Whisper API (OpenAI)
- ✏️ **Editor de correcciones** para el jurado presencial
- 📐 **Análisis técnico**:
  - Conteo de versos y tipo de trova
  - Esquema de rima (ABAB, ABBA, ABABABAB, etc.)
  - Tipo de rima (consonante / asonante / mixta)
  - Conteo de sílabas por verso
  - Regularidad métrica
  - Detección de jergas y regionalismos
- ⚖️ **Deliberación narrativa** con Claude (streaming en tiempo real)
- 🏆 **Puntajes** por categoría con barras animadas

## Instalación

### 1. Clonar / descargar el proyecto

```bash
cd trova-jurado
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv
source venv/bin/activate        # Linux/Mac
# o: venv\Scripts\activate      # Windows

pip install -r requirements.txt
```

### 3. Configurar claves de API

```bash
cp .env.example .env
# Edita .env y añade tus claves:
#   OPENAI_API_KEY=sk-...
#   ANTHROPIC_API_KEY=sk-ant-...
```

### 4. Ejecutar el servidor

```bash
cd backend
python main.py
```

Luego abre en el navegador: **http://localhost:8000**

## Estructura del proyecto

```
trova-jurado/
├── backend/
│   ├── main.py          # Servidor FastAPI (endpoints)
│   └── analizador.py    # Motor de análisis técnico
├── frontend/
│   └── index.html       # Interfaz web completa
├── requirements.txt
├── .env.example
└── README.md
```

## Flujo de uso

1. **Jurado presencial** hace click en "Iniciar grabación"
2. El trovador interpreta su trova
3. Al detener, **Whisper** transcribe automáticamente
4. El jurado puede **corregir errores** de transcripción
5. Click en **"Analizar trova"** → análisis técnico instantáneo
6. Click en **"Deliberar"** → el jurado virtual elabora su veredicto

## Próximas fases

- [ ] Historial de trovas por sesión
- [ ] Comparativa entre trovadores
- [ ] Modo pantalla pública (proyector)
- [ ] Exportar resultados como PDF
- [ ] Soporte para décimas y otras formas

## Notas técnicas

- El análisis de sílabas es heurístico (español iberoamericano).
  Para máxima precisión con el acento colombiano se puede ajustar
  la lista de terminaciones agudas en `analizador.py`.
- Las jergas están en `JERGAS` en `analizador.py` — se puede ampliar
  fácilmente con vocabulario regional específico.
- La puntuación técnica es sobre 85; la IA complementa con una
  evaluación subjetiva de contenido hasta 100.
