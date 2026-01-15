import os
import re
from pathlib import Path

from dotenv import load_dotenv
from upstash_vector import Index, Vector

load_dotenv()


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Variable d'environnement manquante: {name}")
    return value


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


def batched(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def main() -> None:
    url = _require_env("UPSTASH_VECTOR_REST_URL")
    token = _require_env("UPSTASH_VECTOR_REST_TOKEN")

    index = Index(url=url, token=token)

    root = Path(__file__).resolve().parent
    data_dir = root / "data"

    md_files = sorted(data_dir.rglob("*.md")) if data_dir.exists() else []
    if not md_files:
        # fallback: indexe les .md à la racine (sauf README)
        md_files = sorted(
            p for p in root.glob("*.md") if p.name.lower() != "readme.md"
        )

    if not md_files:
        raise SystemExit("Aucun fichier .md trouvé (attendu dans data/)")

    to_upsert: list[Vector] = []
    for path in md_files:
        rel = path.relative_to(root).as_posix()
        content = path.read_text(encoding="utf-8")
        for chunk_i, (title, chunk_text) in enumerate(chunk_markdown(content)):
            # ID stable pour éviter les doublons au rerun
            safe_rel = rel.replace("/", "__")
            vector_id = f"{safe_rel}::{chunk_i}"
            to_upsert.append(
                Vector(
                    id=vector_id,
                    data=chunk_text,
                    metadata={"source": rel, "chunk": chunk_i, "title": title},
                )
            )

    total = len(to_upsert)
    print(f"Fichiers: {len(md_files)} | Chunks: {total}")

    batch_size = 50
    for batch in batched(to_upsert, batch_size):
        index.upsert(vectors=batch)

    info = index.info()
    print(f"Indexation terminée. vector_count={info.vector_count}, pending={info.pending_vector_count}")


if __name__ == "__main__":
    main()