from dotenv import load_dotenv
from upstash_vector import Index, Vector
from pathlib import Path
import re
from agents import Agent, ModelSettings, function_tool
from agents import Agent, Runner
import json



load_dotenv()

upsert_amount = 100


def get_index() -> Index:
    return Index.from_env()

def chunk_markdown(markdown: str) -> list[tuple[str, str]]:
    """Retourne une liste de (titre, contenu) à partir des headings Markdown."""
    text = markdown.strip()
    if not text:
        return []

    pattern = re.compile(r"(?m)^(#{1,3})\s+(.+)$")
    matches = list(pattern.finditer(text))
    if not matches:
        return [("", text)]

    chunks: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        title = m.group(2).strip()
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append((title, chunk_text))
    return chunks


def build_vectors(root: Path | None = None) -> list[Vector]:
    """ retourne une liste de vecteur à partir des fichiers markdown dans data/ """
    if root is None:
        root = Path(__file__).resolve().parent.parent

    data_dir = root / "data"
    vectors = [
        Vector(
            id=f"{fichier.relative_to(root).as_posix().replace('/', '__')}::{chunk_i}",
            data=chunk_text,
            metadata={
                "source": fichier.relative_to(root).as_posix(),
                "chunk": chunk_i,
                "title": title,
            },
        )
        for fichier in sorted(data_dir.glob("*.md"))
        for chunk_i, (title, chunk_text) in enumerate(
            chunk_markdown(fichier.read_text(encoding="utf-8"))
        )
    ]

    return vectors


def index_markdown(index: Index, root: Path | None = None) -> int:
    """ envoie vers upstash les vecteurs construits à partir des fichiers markdown"""
    vectors = build_vectors(root=root)
    if vectors:
        index.upsert(vectors=vectors)
    return len(vectors)


def build_agent(index: Index) -> Agent:
    """ a partir de la questions posée par l'utilisateur, retourne des données a partir de l'index upstash, puis 
    construit un agent pour répondre à la question en utilisant les données retournées.
    """

    @function_tool
    def recherche(query: str) -> str:
        """ recheche dans l'index upstash et retourne les résultats au format json """
        q = (query or "").strip()

        results = index.query(
            data=q,
            top_k=5,
            include_metadata=True,
            include_data=True,
        )

        if not results:
            return "Aucun résultat trouvé."

        payload = []
        for r in results:
            payload.append({
                "source": r.metadata.get("source"),
                "chunk": r.metadata.get("chunk"),
                "title": r.metadata.get("title"),
                "text": r.data,
            })

        return json.dumps(payload, ensure_ascii=False, indent=2)

    agent = Agent(
        name="agent portfolio",
        instructions="A partir des données d'un portfolio répond a des questions sur Justin Berruer.",
        model="gpt-4.1-nano",
        model_settings=ModelSettings(temperature=0.2),
        tools=[recherche],
    )

    return agent


def run_question(agent: Agent, question: str, last_response_id: str | None = None):
    """ pose une question à l'agent et retourne la réponse et l'id de la dernière réponse """
    result = Runner.run_sync(
        agent,
        question,
        previous_response_id=last_response_id,
        auto_previous_response_id=True,
    )

    answer = (getattr(result, "final_output", "") or "").strip()
    if not answer:
        answer = str(result)
    return answer, getattr(result, "last_response_id", None)


def main():
    index = get_index()
    index_markdown(index)
    agent = build_agent(index)

    question = input("Pose une question : ")
    answer, _ = run_question(agent, question)
    print("Réponse de l'agent :", answer)


if __name__ == "__main__":
    main()



