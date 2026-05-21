"""
analizador.py — Análisis técnico de trovas
Soporta: trova sencilla (4 versos) y trova dobleteada (8 versos)
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Jergas y regionalismos del español colombiano / latinoamericano
# ---------------------------------------------------------------------------
JERGAS = {
    # Saludos / despedidas
    "quiubo", "quiubas", "parce", "parcero", "parcera", "llave", "llavecita",
    "mano", "manito", "brother", "bro", "chino", "china",
    # Expresiones
    "chimba", "bacano", "bacana", "chévere", "berraco", "berraca",
    "gonorrea", "hp", "hijueputa", "verga", "vaina", "marica", "mariquita",
    "güevón", "güeva", "gonorria", "mondá", "mondongo",
    "jueputa", "juepucha", "juemadre", "malparido", "malparida",
    "pirobo", "piroba", "saporro", "saporra",
    # Verbos / acciones
    "vacilando", "vacilar", "camello", "camellar", "mamar", "mamando",
    "embolatarse", "embolatar", "enguayabar", "enguayabado",
    # Lugares / cosas
    "camello", "billete", "plata", "pesos", "tombos", "tombo",
    "finca", "potrero", "verraquera", "arrecho", "arrecha",
    # Trova específica
    "cantador", "repentista", "trovador", "contrapunteo",
    # Interjecciones
    "uy", "ay", "ombe", "hombe", "jue", "hijole", "órale", "chale",
    "achis", "achi", "eche", "echa",
}

# ---------------------------------------------------------------------------
# Utilidades fonéticas
# ---------------------------------------------------------------------------

def quitar_tildes(texto: str) -> str:
    """Elimina diacríticos para comparación fonética."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )


def ultima_vocal_tonica(palabra: str) -> str:
    """
    Retorna la cadena desde la última vocal tónica hasta el final.
    Heurística: en español la penúltima sílaba es tónica por defecto
    (palabras llanas), salvo terminaciones que sugieren agudas u esdrújulas.
    """
    palabra = quitar_tildes(palabra.lower())
    vocales = "aeiou"

    # Detectar palabras agudas por terminación
    agudas_terminaciones = ('ad', 'ed', 'id', 'od', 'ud',
                            'al', 'el', 'il', 'ol', 'ul',
                            'an', 'en', 'in', 'on', 'un',
                            'ar', 'er', 'ir', 'or', 'ur',
                            'az', 'ez', 'iz', 'oz', 'uz')

    indices_vocales = [i for i, c in enumerate(palabra) if c in vocales]
    if not indices_vocales:
        return palabra

    if palabra.endswith(agudas_terminaciones):
        # Última vocal
        idx = indices_vocales[-1]
    else:
        # Penúltima vocal (llanas)
        idx = indices_vocales[-2] if len(indices_vocales) >= 2 else indices_vocales[-1]

    return palabra[idx:]


def rima_consonante(p1: str, p2: str) -> bool:
    """Rima consonante: coinciden vocal tónica + todo lo que sigue."""
    return ultima_vocal_tonica(p1) == ultima_vocal_tonica(p2)


def rima_asonante(p1: str, p2: str) -> bool:
    """Rima asonante: solo coinciden las vocales desde la tónica."""
    def solo_vocales(s: str) -> str:
        return ''.join(c for c in s if c in "aeiou")

    v1 = solo_vocales(ultima_vocal_tonica(p1))
    v2 = solo_vocales(ultima_vocal_tonica(p2))
    return v1 == v2 and not rima_consonante(p1, p2)


# ---------------------------------------------------------------------------
# Conteo de sílabas (simplificado para evaluación de trova)
# ---------------------------------------------------------------------------

DIPTONGOS = {
    'ai', 'au', 'ei', 'eu', 'oi', 'ou',
    'ia', 'ie', 'io', 'iu', 'ua', 'ue', 'ui', 'uo',
}


def contar_silabas(palabra: str) -> int:
    """Cuenta sílabas de una palabra española (heurístico)."""
    palabra = quitar_tildes(palabra.lower())
    palabra = re.sub(r'[^a-záéíóúüñ]', '', palabra)
    if not palabra:
        return 0

    vocales = "aeiouáéíóúü"
    silabas = 0
    i = 0
    while i < len(palabra):
        if palabra[i] in vocales:
            silabas += 1
            # Verificar diptongo
            if i + 1 < len(palabra) and palabra[i:i+2] in DIPTONGOS:
                i += 2
            else:
                i += 1
        else:
            i += 1

    return max(1, silabas)


def silabas_verso(verso: str) -> int:
    """Cuenta sílabas métricas de un verso completo."""
    palabras = re.findall(r"[a-záéíóúüñA-ZÁÉÍÓÚÜÑ']+", verso)
    total = sum(contar_silabas(p) for p in palabras)

    # Licencias métricas básicas
    # Sinalefa: vocal final + vocal inicial de siguiente palabra (ya aproximado)
    # Verso agudo: +1; verso esdrújulo: -1
    if palabras:
        ultima = palabras[-1].lower()
        if ultima.endswith(('ar', 'er', 'ir', 'or', 'ur',
                            'al', 'el', 'il', 'ol', 'ul',
                            'an', 'en', 'in', 'on', 'un')):
            total += 1
        elif len(ultima) > 2 and quitar_tildes(ultima)[-3] in "aeiou":
            total -= 1  # esdrújula aproximada

    return total


# ---------------------------------------------------------------------------
# Dataclasses de resultado
# ---------------------------------------------------------------------------

@dataclass
class AnalisisVerso:
    numero: int
    texto: str
    silabas: int
    ultima_palabra: str
    jergas_encontradas: list[str] = field(default_factory=list)


@dataclass
class AnalisisTrova:
    tipo: str                          # "sencilla" | "dobleteada" | "irregular"
    num_versos: int
    versos: list[AnalisisVerso]
    esquema_rima: str                  # ej. "ABAB", "ABBA", "ABABABAB"
    tipo_rima: str                     # "consonante" | "asonante" | "mixta" | "sin rima"
    silabas_por_verso: list[int]
    metrica_regular: bool
    silaba_predominante: Optional[int]
    jergas_totales: list[str]
    uso_jerga: bool
    puntuacion: dict                   # puntajes por categoría
    observaciones: list[str]


# ---------------------------------------------------------------------------
# Analizador principal
# ---------------------------------------------------------------------------

class AnalizadorTrova:

    METRICAS_VALIDAS = {6, 7, 8, 10, 11, 12}  # sílabas aceptadas en trova

    def analizar(self, texto: str) -> AnalisisTrova:
        versos_raw = self._extraer_versos(texto)
        num_versos = len(versos_raw)

        # Analizar cada verso
        versos = []
        for i, v in enumerate(versos_raw):
            palabras = re.findall(r"[a-záéíóúüñA-ZÁÉÍÓÚÜÑ']+", v)
            ultima = palabras[-1] if palabras else ""
            jergas = self._detectar_jergas(v)
            silabas = silabas_verso(v)
            versos.append(AnalisisVerso(
                numero=i + 1,
                texto=v,
                silabas=silabas,
                ultima_palabra=ultima,
                jergas_encontradas=jergas,
            ))

        # Tipo de trova
        tipo = self._clasificar_tipo(num_versos)

        # Análisis de rima
        esquema, tipo_rima = self._analizar_rima(versos)

        # Métrica
        silabas_lista = [v.silabas for v in versos]
        metrica_regular, silaba_predominante = self._analizar_metrica(silabas_lista)

        # Jergas
        todas_jergas = []
        for v in versos:
            todas_jergas.extend(v.jergas_encontradas)
        todas_jergas = list(set(todas_jergas))

        # Puntuación
        puntuacion = self._calcular_puntuacion(
            tipo, tipo_rima, metrica_regular, silabas_lista, num_versos
        )

        # Observaciones
        observaciones = self._generar_observaciones(
            tipo, tipo_rima, metrica_regular, silabas_lista,
            num_versos, todas_jergas, silaba_predominante
        )

        return AnalisisTrova(
            tipo=tipo,
            num_versos=num_versos,
            versos=versos,
            esquema_rima=esquema,
            tipo_rima=tipo_rima,
            silabas_por_verso=silabas_lista,
            metrica_regular=metrica_regular,
            silaba_predominante=silaba_predominante,
            jergas_totales=todas_jergas,
            uso_jerga=len(todas_jergas) > 0,
            puntuacion=puntuacion,
            observaciones=observaciones,
        )

    # ------------------------------------------------------------------
    # Métodos internos
    # ------------------------------------------------------------------

    def _extraer_versos(self, texto: str) -> list[str]:
        """Divide el texto en versos (por salto de línea o puntuación)."""
        lineas = [l.strip() for l in texto.strip().splitlines()]
        lineas = [l for l in lineas if l]
        if len(lineas) >= 4:
            return lineas

        # Si viene como bloque, intentar dividir por puntuación fuerte
        partes = re.split(r'[,;\.]\s*', texto)
        partes = [p.strip() for p in partes if p.strip()]
        return partes if len(partes) >= 4 else [texto]

    def _clasificar_tipo(self, num_versos: int) -> str:
        if num_versos == 4:
            return "sencilla"
        elif num_versos == 8:
            return "dobleteada"
        elif num_versos < 4:
            return "incompleta"
        else:
            return "irregular"

    def _analizar_rima(self, versos: list[AnalisisVerso]) -> tuple[str, str]:
        """Determina esquema y tipo de rima."""
        if len(versos) < 2:
            return ("?", "sin rima")

        ultimas = [v.ultima_palabra for v in versos]
        n = len(ultimas)
        letras = {}
        esquema = []
        contador = 0

        def letra_para(idx: int) -> str:
            nonlocal contador
            p = ultimas[idx]
            for j, letra in letras.items():
                if rima_consonante(p, ultimas[j]):
                    return letra
            nueva = chr(ord('A') + contador)
            letras[idx] = nueva
            contador += 1
            return nueva

        for i in range(n):
            esquema.append(letra_para(i))

        esquema_str = ''.join(esquema)

        # Detectar tipo de rima predominante
        pares_riman_consonante = 0
        pares_riman_asonante = 0
        pares_totales = 0

        for i in range(n):
            for j in range(i + 1, n):
                if esquema[i] == esquema[j]:
                    pares_totales += 1
                    if rima_consonante(ultimas[i], ultimas[j]):
                        pares_riman_consonante += 1
                    elif rima_asonante(ultimas[i], ultimas[j]):
                        pares_riman_asonante += 1

        if pares_totales == 0:
            tipo = "sin rima"
        elif pares_riman_consonante == pares_totales:
            tipo = "consonante"
        elif pares_riman_asonante == pares_totales:
            tipo = "asonante"
        elif pares_riman_consonante > 0 and pares_riman_asonante > 0:
            tipo = "mixta"
        else:
            tipo = "libre"

        return (esquema_str, tipo)

    def _analizar_metrica(self, silabas: list[int]) -> tuple[bool, Optional[int]]:
        if not silabas:
            return (False, None)
        # Métrica regular: todos los versos tienen ±1 sílaba del predominante
        from collections import Counter
        conteo = Counter(silabas)
        predominante = conteo.most_common(1)[0][0]
        regular = all(abs(s - predominante) <= 1 for s in silabas)
        return (regular, predominante)

    def _detectar_jergas(self, texto: str) -> list[str]:
        palabras = re.findall(r"[a-záéíóúüñA-ZÁÉÍÓÚÜÑ']+", texto.lower())
        return [p for p in palabras if quitar_tildes(p) in JERGAS or p in JERGAS]

    def _calcular_puntuacion(
        self, tipo: str, tipo_rima: str, metrica_regular: bool,
        silabas: list[int], num_versos: int
    ) -> dict:
        puntaje = {}

        # 1. Estructura (máx 25)
        if tipo in ("sencilla", "dobleteada"):
            puntaje["estructura"] = 25
        elif tipo == "irregular":
            puntaje["estructura"] = 10
        else:
            puntaje["estructura"] = 5

        # 2. Rima (máx 35)
        rima_pts = {"consonante": 35, "asonante": 20, "mixta": 12, "libre": 5, "sin rima": 0}
        puntaje["rima"] = rima_pts.get(tipo_rima, 0)

        # 3. Métrica (máx 25)
        if metrica_regular:
            puntaje["metrica"] = 25
            if silabas:
                pred = silabas[0]
                if pred in {8, 10}:  # métricas más valoradas en trova
                    puntaje["metrica"] = 25
                elif pred in {7, 11}:
                    puntaje["metrica"] = 20
                else:
                    puntaje["metrica"] = 15
        else:
            # Parcial: cuántos versos tienen la sílaba predominante
            from collections import Counter
            if silabas:
                pred = Counter(silabas).most_common(1)[0][0]
                coinciden = sum(1 for s in silabas if abs(s - pred) <= 1)
                puntaje["metrica"] = round((coinciden / len(silabas)) * 20)
            else:
                puntaje["metrica"] = 0

        # 4. Contenido (base, será enriquecido por IA — máx 15)
        puntaje["contenido"] = 10  # placeholder

        puntaje["total"] = sum(puntaje.values())
        return puntaje

    def _generar_observaciones(
        self, tipo, tipo_rima, metrica_regular, silabas,
        num_versos, jergas, silaba_predominante
    ) -> list[str]:
        obs = []

        if tipo == "sencilla":
            obs.append("✅ Trova sencilla de 4 versos correctamente estructurada.")
        elif tipo == "dobleteada":
            obs.append("✅ Trova dobleteada de 8 versos correctamente estructurada.")
        elif tipo == "incompleta":
            obs.append(f"⚠️ Trova incompleta: solo se detectaron {num_versos} versos.")
        else:
            obs.append(f"⚠️ Estructura irregular: {num_versos} versos detectados.")

        if tipo_rima == "consonante":
            obs.append("✅ Rima consonante perfecta — el nivel más exigente.")
        elif tipo_rima == "asonante":
            obs.append("🔶 Rima asonante — válida pero menos rigurosa que la consonante.")
        elif tipo_rima == "mixta":
            obs.append("⚠️ Rima mixta — algunos versos riman en consonante y otros en asonante.")
        elif tipo_rima == "libre":
            obs.append("❌ Sin esquema de rima identificable.")

        if metrica_regular:
            obs.append(f"✅ Métrica regular: {silaba_predominante} sílabas por verso.")
        else:
            if silabas:
                irregulares = [i+1 for i, s in enumerate(silabas)
                               if silaba_predominante and abs(s - silaba_predominante) > 1]
                if irregulares:
                    obs.append(
                        f"⚠️ Métrica irregular en verso(s) {', '.join(map(str, irregulares))}."
                    )

        if jergas:
            obs.append(f"🗣️ Jerga / coloquialismos detectados: {', '.join(jergas)}.")

        return obs
