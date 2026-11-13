import os

from app.infrastructure.entrypoints.api.routers.documents import resolve_document_file


def _root(tmp_path):
    root = tmp_path / "documentos_uvg"
    (root / "carreras").mkdir(parents=True)
    (root / "a.pdf").write_bytes(b"%PDF a")
    (root / "carreras" / "b.pdf").write_bytes(b"%PDF b")
    (root / "notas.txt").write_text("x")
    (tmp_path / "secreto.pdf").write_bytes(b"%PDF secreto")
    return root


def test_resuelve_pdf_dentro_de_la_carpeta(tmp_path):
    root = _root(tmp_path)
    assert resolve_document_file(root, "a.pdf") == (root / "a.pdf").resolve()
    assert resolve_document_file(root, "carreras/b.pdf") == (root / "carreras" / "b.pdf").resolve()


def test_bloquea_path_traversal_rutas_absolutas_y_enlaces(tmp_path):
    root = _root(tmp_path)
    os.symlink(tmp_path / "secreto.pdf", root / "enlace.pdf")
    for name in ("../secreto.pdf", "carreras/../../secreto.pdf", str(tmp_path / "secreto.pdf"), "enlace.pdf"):
        assert resolve_document_file(root, name) is None, name


def test_solo_sirve_pdf_existentes(tmp_path):
    root = _root(tmp_path)
    assert resolve_document_file(root, "notas.txt") is None
    assert resolve_document_file(root, "no-existe.pdf") is None
