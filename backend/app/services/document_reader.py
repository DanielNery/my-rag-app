from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import NotRequired, TypedDict

import fitz
import pytesseract
from docx import Document
from langgraph.graph import END, START, StateGraph
from PIL import Image
from pypdf import PdfReader


class ReaderState(TypedDict):
    filename: str
    suffix: str
    content: bytes
    method: NotRequired[str]
    text: NotRequired[str]


def read_text_file(content: bytes) -> str:
    """Lê um arquivo de texto e retorna o texto bruto.

    Args:
        content (bytes): Conteúdo do arquivo de texto.

    Returns:
        str: Texto bruto do arquivo de texto.
    """
    for encoding in ("utf-8", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue

    return content.decode("utf-8", errors="ignore")


def read_docx(content: bytes) -> str:
    """Lê um arquivo de documento Word e retorna o texto bruto.

    Args:
        content (bytes): Conteúdo do arquivo de documento Word.

    Returns:
        str: Texto bruto do arquivo de documento Word.
    """
    with NamedTemporaryFile(suffix=".docx") as temp_file:
        temp_file.write(content)
        temp_file.flush()
        document = Document(temp_file.name)

    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def read_pdf_with_pypdf(content: bytes) -> str:
    """Lê um arquivo PDF com a biblioteca pypdf e retorna o texto bruto.

    Args:
        content (bytes): Conteúdo do arquivo PDF.

    Returns:
        str: Texto bruto do arquivo PDF.
    """
    with NamedTemporaryFile(suffix=".pdf") as temp_file:
        temp_file.write(content)
        temp_file.flush()
        reader = PdfReader(temp_file.name)
        return "\n".join(page.extract_text() or "" for page in reader.pages)


def read_pdf_with_pymupdf(content: bytes) -> str:
    """Lê um arquivo PDF com a biblioteca pymupdf e retorna o texto bruto.

    Args:
        content (bytes): Conteúdo do arquivo PDF.

    Returns:
        str: Texto bruto do arquivo PDF.
    """
    with fitz.open(stream=content, filetype="pdf") as document:
        return "\n".join(page.get_text("text") for page in document)


def read_pdf_with_ocr(content: bytes) -> str:
    """Lê um arquivo PDF com a biblioteca pytesseract e retorna o texto bruto.

    Args:
        content (bytes): Conteúdo do arquivo PDF.

    Returns:
        str: Texto bruto do arquivo PDF.
    """
    page_texts: list[str] = []

    with fitz.open(stream=content, filetype="pdf") as document:
        for page in document:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
            page_texts.append(pytesseract.image_to_string(image, lang="por+eng"))

    return "\n".join(page_texts)


def choose_reader(state: ReaderState) -> ReaderState:
    """Escolhe o leitor de documento apropriado com base na extensão do arquivo.

    Args:
        state (ReaderState): Estado contendo o nome do arquivo e a extensão.

    Returns:
        ReaderState: Estado atualizado com o método de leitura escolhido.
    """
    suffix = state["suffix"]
    method = "text"

    if suffix == ".pdf":
        method = "pdf_pypdf"
    elif suffix == ".docx":
        method = "docx"
    elif suffix in {".txt", ".md"}:
        method = "text"

    return {**state, "method": method}


def read_document(state: ReaderState) -> ReaderState:
    """Lê um documento e retorna o texto bruto.

    Args:
        state (ReaderState): Estado contendo o método de leitura e o conteúdo do documento.

    Returns:
        ReaderState: Estado atualizado com o texto bruto do documento.
    """
    method = state["method"]
    content = state["content"]

    match method:
        case "pdf_pypdf":
            text = read_pdf_with_pypdf(content)
        case "docx":
            text = read_docx(content)
        case _:
            text = read_text_file(content)
   

    return {**state, "text": text}


def validate_reader_output(state: ReaderState) -> str:
    """Valida o resultado da leitura de um documento e retorna o nome do próximo estado da máquina de estados.

    Args:
        state (ReaderState): Estado contendo o método de leitura e o conteúdo do documento.

    Returns:
        str: Nome do próximo estado da máquina de estados.
    """
    if state["suffix"] == ".pdf" and len((state.get("text") or "").strip()) < 80:
        return "pdf_fallback"

    return "done"


def read_pdf_fallback(state: ReaderState) -> ReaderState:
    """Lê um arquivo PDF com a biblioteca pymupdf e o OCR e retorna o texto bruto.

    Args:
        state (ReaderState): Estado contendo o nome do arquivo, a extensão e o conteúdo do documento.

    Returns:
        ReaderState: Estado atualizado com o método de leitura e o texto bruto do documento.
    """
    content = state["content"]

    try:
        text = read_pdf_with_pymupdf(content)
        if len(text.strip()) >= 80:
            return {**state, "method": "pdf_pymupdf", "text": text}
    except Exception:
        pass

    try:
        return {**state, "method": "pdf_ocr", "text": read_pdf_with_ocr(content)}
    except Exception as error:
        previous_text = state.get("text") or ""
        return {
            **state,
            "method": "pdf_ocr_unavailable",
            "text": previous_text or f"Nao foi possivel extrair texto do PDF: {error}",
        }


def build_reader_graph():
    """Constrói o grafo de leitura de documentos.

    Returns:
        StateGraph: Grafo de leitura de documentos compilado.
    """
    graph = StateGraph(ReaderState)

    # Escolher o leitor de documento apropriado com base na extensão do arquivo.
    graph.add_node("choose_reader", choose_reader)


    graph.add_node("read_document", read_document)
    graph.add_node("pdf_fallback", read_pdf_fallback)
    graph.add_edge(START, "choose_reader")
    graph.add_edge("choose_reader", "read_document")
    graph.add_conditional_edges(
        "read_document",
        validate_reader_output,
        {
            "pdf_fallback": "pdf_fallback",
            "done": END,
        },
    )
    graph.add_edge("pdf_fallback", END)
    return graph.compile()


reader_agent = build_reader_graph()


def extract_document_text(filename: str, content: bytes) -> tuple[str, str]:
    """Extrai o texto bruto de um documento e retorna o método de leitura usado.

    Args:
        filename (str): Nome do arquivo.
        content (bytes): Conteúdo do arquivo.

    Returns:
        tuple[str, str]: Texto bruto do documento e o método de leitura usado.
    """
    suffix = Path(filename).suffix.lower()
    result = reader_agent.invoke(
        {
            "filename": filename,
            "suffix": suffix,
            "content": content,
        }
    )

    return result.get("text", ""), result.get("method", "unknown")
