"""
main.py — Servidor FastAPI: Jurado Virtual de Trova
"""

import os
import json
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from analizador import AnalizadorTrova

load_dotenv()

app = FastAPI(title="Jurado Virtual de Trova", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir archivos estáticos del frontend
STATIC_DIR = Path(__file__).parent.parent / "frontend" / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

analizador = AnalizadorTrova()


# ---------------------------------------------------------------------------
# Modelos Pydantic
# ---------------------------------------------------------------------------

class TextoTrova(BaseModel):
    texto: str


class DeliberacionRequest(BaseModel):
    texto: str
    analisis: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    """Sirve el frontend principal."""
    index_path = Path(__file__).parent.parent / "frontend" / "index.html"
    return FileResponse(str(index_path))


@app.post("/transcribir")
async def transcribir_audio(audio: UploadFile = File(...)):
    """
    Recibe un archivo de audio y retorna la transcripción usando Whisper API.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY no configurada.")

    # Guardar audio temporalmente
    suffix = Path(audio.filename).suffix if audio.filename else ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        contenido = await audio.read()
        tmp.write(contenido)
        tmp_path = tmp.name

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        with open(tmp_path, "rb") as f:
            respuesta = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="es",
                response_format="text",
            )

        transcripcion = respuesta if isinstance(respuesta, str) else respuesta.text
        return {"transcripcion": transcripcion.strip()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en transcripción: {str(e)}")
    finally:
        os.unlink(tmp_path)


@app.post("/analizar")
async def analizar_trova(body: TextoTrova):
    """
    Analiza técnicamente un texto de trova (versos, rima, métrica, jerga).
    """
    if not body.texto.strip():
        raise HTTPException(status_code=400, detail="Texto vacío.")

    try:
        resultado = analizador.analizar(body.texto)

        return {
            "tipo": resultado.tipo,
            "num_versos": resultado.num_versos,
            "versos": [
                {
                    "numero": v.numero,
                    "texto": v.texto,
                    "silabas": v.silabas,
                    "ultima_palabra": v.ultima_palabra,
                    "jergas": v.jergas_encontradas,
                }
                for v in resultado.versos
            ],
            "esquema_rima": resultado.esquema_rima,
            "tipo_rima": resultado.tipo_rima,
            "silabas_por_verso": resultado.silabas_por_verso,
            "metrica_regular": resultado.metrica_regular,
            "silaba_predominante": resultado.silaba_predominante,
            "jergas_totales": resultado.jergas_totales,
            "uso_jerga": resultado.uso_jerga,
            "puntuacion": resultado.puntuacion,
            "observaciones": resultado.observaciones,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en análisis: {str(e)}")


@app.post("/deliberar")
async def deliberar(body: DeliberacionRequest):
    """
    Genera la deliberación del jurado virtual usando Claude (streaming).
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY no configurada.")

    analisis = body.analisis
    texto = body.texto

    prompt = f"""Eres un jurado experto en trova colombiana y latinoamericana. 
Acabas de escuchar la siguiente trova:

---
{texto}
---

ANÁLISIS TÉCNICO AUTOMÁTICO:
- Tipo: {analisis.get('tipo', 'desconocido')}
- Versos: {analisis.get('num_versos', 0)}
- Esquema de rima: {analisis.get('esquema_rima', '?')}
- Tipo de rima: {analisis.get('tipo_rima', '?')}
- Métrica: {'Regular' if analisis.get('metrica_regular') else 'Irregular'} ({analisis.get('silaba_predominante', '?')} sílabas predominantes)
- Jergas detectadas: {', '.join(analisis.get('jergas_totales', [])) or 'ninguna'}
- Puntaje técnico preliminar: {analisis.get('puntuacion', {}).get('total', 0)} / 85

Como jurado, emite tu deliberación pública considerando:
1. 🎯 ESTRUCTURA: ¿Cumple con la forma de trova {analisis.get('tipo', '')}?
2. 🎵 RIMA: Calidad e ingenio de la rima
3. 📏 MÉTRICA: Regularidad del ritmo
4. 💬 CONTENIDO: Creatividad, mensaje, ingenio del trovador
5. 🏆 VEREDICTO FINAL con puntaje sobre 100

Habla con pasión y autoridad, como lo haría un jurado en un festival de trova. 
Sé específico, menciona versos concretos. Máximo 200 palabras."""

    async def stream_deliberacion():
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield f"data: {json.dumps({'chunk': text})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream_deliberacion(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
