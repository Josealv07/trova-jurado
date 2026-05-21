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


def _formas_rima(palabra: str, acepta_plural: bool) -> list:
    """
    Devuelve las formas a usar en la comparación de rima.
    Si acepta_plural, también incluye la forma sin la 's' final
    (montañas → montaña) para aceptar rima entre singular y plural.
    """
    formas = [palabra]
    if acepta_plural and len(palabra) > 2 and palabra.endswith('s'):
        formas.append(palabra[:-1])
    return formas


def rima_consonante(p1: str, p2: str, acepta_plural: bool = False) -> bool:
    """Rima consonante: coinciden vocal tónica + todo lo que sigue."""
    f1 = _formas_rima(p1, acepta_plural)
    f2 = _formas_rima(p2, acepta_plural)
    return any(ultima_vocal_tonica(a) == ultima_vocal_tonica(b) for a in f1 for b in f2)


def rima_asonante(p1: str, p2: str, acepta_plural: bool = False) -> bool:
    """Rima asonante: solo coinciden las vocales desde la tónica."""
    if rima_consonante(p1, p2, acepta_plural):
        return False

    def solo_vocales(s: str) -> str:
        return ''.join(c for c in s if c in "aeiou")

    f1 = _formas_rima(p1, acepta_plural)
    f2 = _formas_rima(p2, acepta_plural)
    return any(
        solo_vocales(ultima_vocal_tonica(a)) == solo_vocales(ultima_vocal_tonica(b))
        for a in f1 for b in f2
    )


# ---------------------------------------------------------------------------
# Conteo de sílabas con reglas métricas completas
# ---------------------------------------------------------------------------

DIPTONGOS = {
    'ai', 'au', 'ei', 'eu', 'oi', 'ou',
    'ia', 'ie', 'io', 'iu', 'ua', 'ue', 'ui', 'uo',
}

_VOCALES      = frozenset("aeiou")
_VOCALES_EXT  = frozenset("aeiouáéíóúü")
_VOCALES_TILD = frozenset("áéíóú")
_SEMIVOCALES  = frozenset("iuü")

# Monosílabos átonos: no provocan el +1 de la ley del acento final.
# Todo monosílabo que NO esté aquí se trata como tónico → aguda → +1.
_MONOSILABAS_ATONAS = frozenset({
    # artículos
    'el', 'la', 'los', 'las', 'un', 'una',
    # preposiciones
    'a', 'de', 'en', 'con', 'sin', 'por', 'pro',
    # conjunciones
    'y', 'e', 'o', 'u', 'ni', 'mas',
    # pronombres clíticos
    'me', 'te', 'se', 'le', 'lo', 'nos', 'os',
    # posesivos átonos (sin tilde)
    'mi', 'tu', 'su',
    # partículas subordinantes átonas
    'que', 'si',
})


def contar_silabas(palabra: str) -> int:
    """
    Cuenta sílabas gramaticales de una sola palabra.
    Respeta hiatos: 'í' y 'ú' con tilde rompen el diptongo (mí-a, grú-a).
    """
    p_orig = re.sub(r'[^a-záéíóúüñ]', '', palabra.lower())
    p_norm = quitar_tildes(p_orig)
    if not p_norm:
        return 0

    # Posiciones donde la í/ú tónica rompe un posible diptongo
    hiato = frozenset(i for i, c in enumerate(p_orig) if c in ('í', 'ú'))

    silabas = 0
    i = 0
    while i < len(p_norm):
        if p_norm[i] in _VOCALES:
            silabas += 1
            if (i + 1 < len(p_norm)
                    and p_norm[i:i+2] in DIPTONGOS
                    and i not in hiato
                    and (i + 1) not in hiato):
                i += 2          # diptongo cuenta como 1 sílaba
            else:
                i += 1
        else:
            i += 1

    return max(1, silabas)


def tipo_acentuacion(palabra: str) -> str:
    """
    Devuelve 'aguda', 'llana' o 'esdrujula' según la posición del acento.
    Usa tildes explícitas; si no hay, aplica la regla ortográfica española.
    """
    p = re.sub(r"[^a-záéíóúüñA-ZÁÉÍÓÚÜÑ]", "", palabra).lower()
    if not p:
        return 'llana'

    # Buscar tilde explícita (la última en la palabra)
    pos_tilde = -1
    for i, c in enumerate(p):
        if c in _VOCALES_TILD:
            pos_tilde = i

    if pos_tilde >= 0:
        # Avanzar sobre semivocales del diptongo que acompañan a la vocal tónica
        i = pos_tilde + 1
        while i < len(p) and p[i] in _SEMIVOCALES:
            i += 1

        # Contar núcleos vocálicos restantes (= sílabas después de la tónica)
        nucleos = 0
        while i < len(p):
            if p[i] in _VOCALES_EXT:
                nucleos += 1
                i += 1
                while i < len(p) and p[i] in _SEMIVOCALES:
                    i += 1
            else:
                i += 1

        if nucleos == 0:
            return 'aguda'
        elif nucleos == 1:
            return 'llana'
        else:
            return 'esdrujula'
    else:
        p_norm = quitar_tildes(p)
        # Monosílabo tónico: su única sílaba es la tónica y es la última del verso
        # → se comporta como aguda (+1), salvo que sea una palabra átona conocida.
        if contar_silabas(p) == 1 and p_norm not in _MONOSILABAS_ATONAS:
            return 'aguda'
        # Regla ortográfica general: llana → termina en vocal, n o s
        return 'llana' if p_norm[-1] in "aeiounsü" else 'aguda'


def contar_sinalefas(palabras: list) -> int:
    """
    Cuenta sinalefas posibles entre palabras consecutivas.
    Reglas:
    - Palabra A termina en vocal (incluyendo 'y' final, que es vocálica: rey, hoy, soy).
    - Palabra B empieza con vocal, h+vocal, o es la conjunción 'y' (sola).
    """
    _VOCALES_FINAL = _VOCALES | frozenset('y')   # 'y' al final es vocálica
    count = 0
    for i in range(len(palabras) - 1):
        p1 = quitar_tildes(palabras[i].lower())
        p2 = quitar_tildes(palabras[i + 1].lower())
        if not p1 or not p2:
            continue
        if p1[-1] in _VOCALES_FINAL:
            if p2 == 'y':                                          # conjunción sola
                count += 1
            elif p2[0] == 'h' and len(p2) > 1 and p2[1] in _VOCALES:
                count += 1
            elif p2[0] in _VOCALES:
                count += 1
    return count


def silabas_verso(verso: str, objetivo: int = 8) -> int:
    """
    Cuenta sílabas métricas con sinalefa facultativa:
    prueba el verso CON y SIN sinalefa y devuelve el valor más cercano
    al objetivo (por defecto 8). En empate prefiere CON sinalefa (regla clásica).
    La ley del acento final se aplica en ambos casos.
    """
    palabras = re.findall(r"[a-záéíóúüñA-ZÁÉÍÓÚÜÑ']+", verso)
    if not palabras:
        return 0

    raw       = sum(contar_silabas(p) for p in palabras)
    sinalefas = contar_sinalefas(palabras)

    acento = tipo_acentuacion(palabras[-1])
    ajuste = 1 if acento == 'aguda' else (-1 if acento == 'esdrujula' else 0)

    # Probar cada cantidad posible de sinalefas (0 … total).
    # La sinalefa es facultativa: el trovador aplica las que necesita para cuadrar el verso.
    candidatos = [raw - n + ajuste for n in range(sinalefas + 1)]
    return min(candidatos, key=lambda x: abs(x - objetivo))


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

    def analizar(self, texto: str, acepta_plural: bool = False) -> AnalisisTrova:
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
        esquema, tipo_rima = self._analizar_rima(versos, acepta_plural)

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
        """
        Divide el texto en versos.
        Prioridad: saltos de línea → división por sílabas (con puntuación como pista).
        La puntuación sola NO se usa como único criterio: es inconsistente porque no
        todos los versos terminan en coma.
        """
        lineas = [l.strip() for l in texto.strip().splitlines()]
        lineas = [l for l in lineas if l]
        if len(lineas) >= 4:
            return lineas

        return self._dividir_por_silabas(texto.strip(), objetivo=8)

    @staticmethod
    def _alfa(palabra: str) -> str:
        return re.sub(r"[^a-záéíóúüñA-ZÁÉÍÓÚÜÑ']", "", palabra.lower())

    def _dividir_por_silabas(self, texto: str, objetivo: int = 8) -> list[str]:
        """
        Divide un bloque continuo en versos de ~objetivo sílabas.
        Usa silabas_verso (con sinalefa facultativa) para decidir el corte.
        """
        _PUNT = frozenset(',.;:!?')
        palabras = texto.split()
        if not palabras:
            return [texto]

        versos: list = []
        verso_actual: list = []

        for palabra in palabras:
            verso_actual.append(palabra)
            sil = silabas_verso(' '.join(verso_actual), objetivo)

            # Retroceder: nos pasamos demasiado con >= 2 palabras ya acumuladas
            if len(verso_actual) > 1 and sil > objetivo + 2:
                verso_actual.pop()
                versos.append(' '.join(verso_actual))
                verso_actual = [palabra]
                sil = silabas_verso(palabra, objetivo)

            tiene_punct = bool(palabra) and palabra[-1] in _PUNT
            en_rango    = objetivo - 2 <= sil <= objetivo + 2

            if sil >= objetivo or (tiene_punct and en_rango):
                versos.append(' '.join(verso_actual))
                verso_actual = []

        if verso_actual:
            versos.append(' '.join(verso_actual))

        return versos if len(versos) >= 2 else [texto]

    def _clasificar_tipo(self, num_versos: int) -> str:
        if num_versos == 4:
            return "sencilla"
        elif num_versos == 8:
            return "dobleteada"
        elif num_versos < 4:
            return "incompleta"
        else:
            return "irregular"

    def _analizar_rima(self, versos: list[AnalisisVerso], acepta_plural: bool = False) -> tuple[str, str]:
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
                if rima_consonante(p, ultimas[j], acepta_plural):
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
                    if rima_consonante(ultimas[i], ultimas[j], acepta_plural):
                        pares_riman_consonante += 1
                    elif rima_asonante(ultimas[i], ultimas[j], acepta_plural):
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
        """
        Puntaje sobre 100:
          Estructura  30 pts  — forma correcta de trova
          Rima        40 pts  — calidad de la rima
          Métrica     30 pts  — regularidad del ritmo
        """
        from collections import Counter
        puntaje = {}

        # 1. Estructura (máx 30)
        if tipo in ("sencilla", "dobleteada"):
            puntaje["estructura"] = 30
        elif tipo == "irregular":
            puntaje["estructura"] = 12
        else:
            puntaje["estructura"] = 5

        # 2. Rima (máx 40)
        rima_pts = {"consonante": 40, "asonante": 26, "mixta": 14, "libre": 5, "sin rima": 0}
        puntaje["rima"] = rima_pts.get(tipo_rima, 0)

        # 3. Métrica (máx 30)
        if metrica_regular:
            pred = silabas[0] if silabas else 0
            if pred in {8, 10}:
                puntaje["metrica"] = 30
            elif pred in {7, 11}:
                puntaje["metrica"] = 24
            else:
                puntaje["metrica"] = 18
        else:
            if silabas:
                pred = Counter(silabas).most_common(1)[0][0]
                coinciden = sum(1 for s in silabas if abs(s - pred) <= 1)
                puntaje["metrica"] = round((coinciden / len(silabas)) * 24)
            else:
                puntaje["metrica"] = 0

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
