import re
from pathlib import Path
from PyPDF2 import PdfReader
from difflib import SequenceMatcher


def extract_text_from_pdf(path: str) -> str:
    try:
        with open(path, "rb") as f:
            reader = PdfReader(f)
            return "\n".join((p.extract_text() or "") for p in reader.pages)
    except:
        return ""

def extract_text_from_docx(path: str) -> str:
    try:
        from docx import Document
        doc = Document(path)
        return "\n".join([p.text for p in doc.paragraphs])
    except:
        return ""

def extract_text(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(path)
    if ext == ".docx":
        return extract_text_from_docx(path)
    return ""

def compute_match(required_skills, candidate_skills):
    if not required_skills or not candidate_skills:
        return 0.0

    req = {s.lower() for s in required_skills}
    cand = {s.lower() for s in candidate_skills}

    intersection = req.intersection(cand)

    score = (len(intersection) / len(req)) * 100
    return round(score, 1)



SKILL_SYNONYMS = {
    # genéricos
    "react.js": "react",
    "react js": "react",
    "reactjs": "react",
    "nest js": "nestjs",
    "nest.js": "nestjs",
    "tsql": "sql",
    "t-sql": "sql",
    "sql server": "sql",
    "mssql": "sql",

    # .NET / C#
    "c sharp": "c#",
    "csharp": "c#",
    ".net": ".net",
    "dotnet": ".net",
    "net": ".net",

    # MAUI
    "maui": "maui",
    ".net maui": "maui",
    ".net con maui": "maui",
}

def normalize_skill(s: str) -> str:
    """
    Normaliza un nombre de skill: minúsculas, sin caracteres raros,
    aplica sinónimos y reconocimiento parcial para MAUI / .NET / C#.
    """
    if not s:
        return ""

    x = s.strip().lower()

    # quitar paréntesis y su contenido
    x = re.sub(r"\(.*?\)", "", x)

    # dejar solo letras, números, espacios, punto y #
    x = re.sub(r"[^\w\s\.#]", " ", x)

    # colapsar espacios
    x = re.sub(r"\s+", " ", x).strip()

    # sinónimos exactos
    if x in SKILL_SYNONYMS:
        return SKILL_SYNONYMS[x]

    # reconocimiento parcial
    if "maui" in x:
        return "maui"

    if ".net" in x:
        return ".net"

    if "c#" in x or "c sharp" in x:
        return "c#"

    # recortes simples: 'framework', 'developer', etc.
    for suffix in [" framework", " developer", " dev", " engineer"]:
        if x.endswith(suffix):
            x = x[: -len(suffix)]

    return x.strip()


def similarity(a: str, b: str) -> float:
    """
    Similaridad de 0 a 1 usando SequenceMatcher de la librería estándar.
    """
    return SequenceMatcher(None, a, b).ratio()


def compute_match_v2(required_skills, candidate_skills):
    """
    Calcula un match score mejorado:
      - Normaliza skills (minúsculas + sinónimos).
      - Usa similitud difusa (fuzzy) para emparejar.
      - Da un bonus pequeño por amplitud de stack.
    """
    if not required_skills:
        return 0.0

    # Normalizar listas
    req_norm = [normalize_skill(s) for s in required_skills if s]
    cand_norm = [normalize_skill(s) for s in candidate_skills or [] if s]

    # eliminar vacíos
    req_norm = [s for s in req_norm if s]
    cand_norm = [s for s in cand_norm if s]

    if not req_norm or not cand_norm:
        return 0.0

    per_skill_scores = []

    for req in req_norm:
        best = 0.0
        for cand in cand_norm:
            sim = similarity(req, cand)

            if req and cand and (req in cand or cand in req):
                sim = max(sim, 0.95)

            if sim > best:
                best = sim

        if best >= 0.90:
            weight = 1.0      # match casi exacto o contenido dentro
        elif best >= 0.75:
            weight = 0.7
        elif best >= 0.60:
            weight = 0.4
        else:
            weight = 0.0

        per_skill_scores.append(weight)

    # Score base: promedio de pesos (0–1) → 0–100
    if per_skill_scores:
        base_score = (sum(per_skill_scores) / len(per_skill_scores)) * 100.0
    else:
        base_score = 0.0

    # BONUS por amplitud de stack (máx 10 puntos extra)
    unique_stack = set(cand_norm)
    breadth_bonus = min(len(unique_stack) / 10.0, 1.0) * 10.0

    final_score = base_score * 0.9 + breadth_bonus * 0.1  # 90% skills requeridos, 10% amplitud
    return round(min(final_score, 100.0), 1)