import json
import os
import re

from agents import Agent, ModelSettings, Runner
from agents.tool import function_tool
from dotenv import load_dotenv
from upstash_vector import Index

load_dotenv()


# Prépare l'index Upstash
index = Index(
    url=os.getenv("UPSTASH_VECTOR_REST_URL"),
    token=os.getenv("UPSTASH_VECTOR_REST_TOKEN")
)


_FR_STOPWORDS = {
    "a",
    "au",
    "aux",
    "avec",
    "ce",
    "ces",
    "dans",
    "de",
    "des",
    "du",
    "elle",
    "en",
    "et",
    "eux",
    "il",
    "je",
    "la",
    "le",
    "les",
    "leur",
    "lui",
    "ma",
    "mais",
    "me",
    "meme",
    "mêmes",
    "mes",
    "moi",
    "mon",
    "ne",
    "nos",
    "notre",
    "nous",
    "on",
    "ou",
    "par",
    "pas",
    "pour",
    "qu",
    "que",
    "qui",
    "sa",
    "se",
    "ses",
    "son",
    "sur",
    "ta",
    "te",
    "tes",
    "toi",
    "ton",
    "tu",
    "un",
    "une",
    "vos",
    "votre",
    "vous",
}


def _keywords_from_query(query: str) -> list[str]:
    words = re.findall(r"[\wÀ-ÿ]+", (query or "").lower())
    keywords: list[str] = []
    for w in words:
        if len(w) < 4:
            continue
        if w in _FR_STOPWORDS:
            continue
        keywords.append(w)
    # dédoublonne en gardant l'ordre
    seen = set()
    ordered: list[str] = []
    for k in keywords:
        if k in seen:
            continue
        seen.add(k)
        ordered.append(k)
    return ordered[:6]


def _compress_retrieved_text(text: str, *, query: str = "", max_chars: int = 520) -> str:
    """Réduit le risque de recopie mot-à-mot.

    Objectif: fournir suffisamment de contexte factuel pour répondre,
    sans renvoyer des paragraphes complets ni des listes interminables.
    """

    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    # Retire les headings Markdown (souvent redondants avec le champ title)
    cleaned = re.sub(r"(?m)^#{1,6}\s+.*$", "", cleaned).strip()

    # Normalise les espaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Si possible, privilégie des phrases qui contiennent les mots-clés de la question.
    keywords = _keywords_from_query(query)
    if keywords:
        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        picked: list[str] = []
        for s in sentences:
            s_l = s.lower()
            if any(k in s_l for k in keywords):
                picked.append(s.strip())
            if len(" ".join(picked)) >= max_chars:
                break
        if picked:
            candidate = " ".join(picked)
            if len(candidate) > max_chars:
                candidate = candidate[:max_chars].rstrip() + " …"
            cleaned = candidate

    # Coupe les listes trop longues (souvent une suite de compétences/outils)
    comma_count = cleaned.count(",")
    if comma_count >= 10:
        parts = [p.strip() for p in cleaned.split(",") if p.strip()]
        if len(parts) > 5:
            cleaned = ", ".join(parts[:5]) + ", …"

    # Coupe à une longueur raisonnable, de préférence en fin de phrase.
    if len(cleaned) > max_chars:
        snippet = cleaned[:max_chars]
        cut = max(snippet.rfind("."), snippet.rfind("!"), snippet.rfind("?"))
        cleaned = (snippet[:cut + 1] if cut > 120 else snippet).rstrip() + " …"

    return cleaned

@function_tool(name_override="search_vector_db", description_override="Recherche dans la base vectorielle des informations sur le profil de Justin Berruyer.")
def search_vector_db(query: str) -> str:
    results = index.query(
        data=query,
        top_k=8,
        include_metadata=True,
        include_data=True,
    )
    if not results:
        return "Aucun résultat trouvé dans la base vectorielle pour cette question."

    payload: dict = {"query": query, "matches": []}
    for r in results:
        md = r.metadata or {}
        source = (md.get("source") or "").strip()
        chunk = md.get("chunk")
        title = (md.get("title") or "").strip()

        excerpt = _compress_retrieved_text(r.data or "", query=query)
        if not excerpt:
            continue

        payload["matches"].append(
            {
                "source": source,
                "chunk": chunk,
                "title": title,
                "excerpt": excerpt,
            }
        )

    if not payload["matches"]:
        return "Résultats trouvés, mais sans contenu exploitable."

    return json.dumps(payload, ensure_ascii=False, indent=2)

agent = Agent(
    name="portfolio-agent",
    instructions=(
        "Tu es un assistant portfolio (RAG) sur Justin Berruyer.\n"
        "Règles :\n"
        "- Si la question est à propos de Justin / de son parcours / de ses projets / compétences : appelle TOUJOURS d'abord `search_vector_db` avec la question.\n"
        "- Réponds ensuite UNIQUEMENT avec les faits présents dans la sortie de l'outil (pas d'invention).\n"
        "- Reformule systématiquement : ne recopie pas mot pour mot les extraits. Évite les longues listes (donne 3 à 5 exemples max).\n"
        "- Réponse courte et utile : 2 à 6 phrases, ou 3 à 6 puces si c'est plus clair.\n"
        "- Si l'outil n'apporte rien de pertinent : dis-le et propose une reformulation.\n"
        "- Si l'utilisateur demande 'qui es-tu' / 'ton rôle' : réponds sans appeler l'outil.\n"
        "- Si l'utilisateur parle à la 1ère personne ('qui suis-je', 'parle-moi de moi') et que ce n'est pas explicitement Justin : demande une clarification (toi vs Justin)."
    ),
    
    model="gpt-4.1-nano",
    model_settings=ModelSettings(temperature=0.2),
    tools=[search_vector_db],
)

# Exemple d'appel synchrone
if __name__ == "__main__":
    question = input("Pose une question à l'agent : ")
    result = Runner.run_sync(agent, question)
    print("Réponse de l'agent :", result)

