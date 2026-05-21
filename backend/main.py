"""
main.py — Servidor FastAPI: Trova Coach
"""

import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from analizador import AnalizadorTrova

load_dotenv()

app = FastAPI(title="Trova Coach", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent.parent / "frontend" / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

analizador = AnalizadorTrova()


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

class TextoTrova(BaseModel):
    texto: str
    rima_plural: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    index_path = Path(__file__).parent.parent / "frontend" / "index.html"
    return FileResponse(str(index_path))


@app.post("/transcribir")
async def transcribir_audio(audio: UploadFile = File(...)):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY no configurada.")

    suffix = Path(audio.filename).suffix if audio.filename else ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await audio.read())
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
    if not body.texto.strip():
        raise HTTPException(status_code=400, detail="Texto vacío.")

    try:
        r = analizador.analizar(body.texto, acepta_plural=body.rima_plural)
        return {
            "tipo": r.tipo,
            "num_versos": r.num_versos,
            "versos": [
                {
                    "numero": v.numero,
                    "texto": v.texto,
                    "silabas": v.silabas,
                    "ultima_palabra": v.ultima_palabra,
                    "jergas": v.jergas_encontradas,
                }
                for v in r.versos
            ],
            "esquema_rima": r.esquema_rima,
            "tipo_rima": r.tipo_rima,
            "silabas_por_verso": r.silabas_por_verso,
            "metrica_regular": r.metrica_regular,
            "silaba_predominante": r.silaba_predominante,
            "jergas_totales": r.jergas_totales,
            "uso_jerga": r.uso_jerga,
            "puntuacion": r.puntuacion,
            "observaciones": r.observaciones,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en análisis: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
