from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P


def iter_document_blocks(document):

    body = document.element.body

    for child in body.iterchildren():

        if isinstance(child, CT_P):
            yield Paragraph(child, document)

        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def load_docx_blocks(file_path):

    document = Document(file_path)

    blocks = []

    for block in iter_document_blocks(document):

        # Normal paragraph
        if isinstance(block, Paragraph):

            text = block.text.strip()

            if text:
                blocks.append(text)

        # Table
        elif isinstance(block, Table):

            for row in block.rows:

                cells = []

                for cell in row.cells:

                    text = cell.text.strip()

                    if text:
                        cells.append(text)

                if cells:

                    row_text = " | ".join(cells)

                    blocks.append(row_text)

    return blocks


def is_noise(text):

    text_lower = text.lower().strip()

    noise_starts = [
        "nastavnik/",
        "nastavnik /",
        "zadaća",
        "vrednovanje",
        "napomena,",
        "povezanost sa drugim predmetima"
    ]

    # We remove only relatively short administrative blocks.
    # Long blocks may still contain useful teaching material.
    if len(text) < 400:

        for prefix in noise_starts:

            if text_lower.startswith(prefix):
                return True

    return False


def create_chunks(
    blocks,
    chunk_size=650,
    overlap_blocks=1
):

    useful_blocks = [
        block
        for block in blocks
        if not is_noise(block)
    ]

    chunks = []

    current_blocks = []
    current_length = 0

    for block in useful_blocks:

        block_length = len(block)

        if (
            current_blocks
            and current_length + block_length > chunk_size
        ):

            chunk = "\n".join(current_blocks).strip()

            if chunk:
                chunks.append(chunk)

            # Keep one previous block as semantic overlap
            if overlap_blocks > 0:

                current_blocks = current_blocks[-overlap_blocks:]

                current_length = sum(
                    len(item)
                    for item in current_blocks
                )

            else:

                current_blocks = []
                current_length = 0

        current_blocks.append(block)

        current_length += block_length

    if current_blocks:

        chunk = "\n".join(current_blocks).strip()

        if chunk:
            chunks.append(chunk)

    return chunks


def load_knowledge_base(folder_path):

    folder = Path(folder_path)

    if not folder.exists():
        return []

    all_chunks = []

    for file_path in folder.glob("*.docx"):

        blocks = load_docx_blocks(file_path)

        chunks = create_chunks(blocks)

        for chunk in chunks:

            all_chunks.append({
                "text": chunk,
                "source": file_path.name
            })

    return all_chunks