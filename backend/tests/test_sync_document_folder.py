from pathlib import Path

from app.application.use_cases.sync_document_folder import SyncDocumentFolderUseCase
from app.domain.entities.document import DocumentStatus
from tests.fakes import FakePipeline, InMemoryDocumentRepository, RecordingVectorStore


def _use_case():
    repository, store, pipeline = InMemoryDocumentRepository(), RecordingVectorStore(), FakePipeline()
    return SyncDocumentFolderUseCase(repository, store, pipeline), repository, store, pipeline


async def test_carpeta_vacia_o_inexistente_no_falla(tmp_path: Path):
    use_case, repository, _, _ = _use_case()
    report = await use_case.execute(tmp_path / "no-existe")
    assert report.outcomes == [] and repository.documents == {}
    report = await use_case.execute(tmp_path)
    assert report.outcomes == []


async def test_indexa_pdf_nuevos_incluidas_subcarpetas_e_ignora_otros_archivos(tmp_path: Path):
    (tmp_path / "carreras").mkdir()
    (tmp_path / "a.pdf").write_bytes(b"%PDF a")
    (tmp_path / "carreras" / "b.PDF").write_bytes(b"%PDF b")
    (tmp_path / "calendario.xlsx").write_bytes(b"xlsx")
    (tmp_path / ".DS_Store").write_bytes(b"x")
    use_case, repository, _, _ = _use_case()

    report = await use_case.execute(tmp_path)

    assert sorted(o.filename for o in report.outcomes) == ["a.pdf", "carreras/b.PDF"]
    assert all(o.action == "indexed" and o.chunk_count == 3 for o in report.outcomes)
    assert report.skipped_files == ["calendario.xlsx"]
    assert {d.status for d in repository.documents.values()} == {DocumentStatus.INDEXED}


async def test_segunda_pasada_sin_cambios_no_reindexa(tmp_path: Path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF a")
    use_case, _, _, pipeline = _use_case()
    await use_case.execute(tmp_path)
    report = await use_case.execute(tmp_path)
    assert [o.action for o in report.outcomes] == ["unchanged"]
    assert pipeline.processed == ["a.pdf"]


async def test_pdf_modificado_se_reindexa_y_borra_sus_fragmentos_previos(tmp_path: Path):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF version 1")
    use_case, repository, store, _ = _use_case()
    await use_case.execute(tmp_path)
    document_id = next(iter(repository.documents))

    pdf.write_bytes(b"%PDF version 2")
    report = await use_case.execute(tmp_path)

    assert [o.action for o in report.outcomes] == ["reindexed"]
    assert document_id in store.deleted
    assert len(repository.documents) == 1


async def test_pdf_eliminado_sale_del_indice(tmp_path: Path):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF a")
    use_case, repository, store, _ = _use_case()
    await use_case.execute(tmp_path)
    document_id = next(iter(repository.documents))

    pdf.unlink()
    report = await use_case.execute(tmp_path)

    assert [o.action for o in report.outcomes] == ["removed"]
    assert repository.documents == {} and document_id in store.deleted


async def test_pdf_sin_texto_queda_con_error_sin_detener_el_resto(tmp_path: Path):
    (tmp_path / "escaneado.pdf").write_bytes(b"%PDF img")
    (tmp_path / "bueno.pdf").write_bytes(b"%PDF ok")
    use_case, repository, _, _ = _use_case()

    report = await use_case.execute(tmp_path)

    actions = {o.filename: o.action for o in report.outcomes}
    assert actions == {"escaneado.pdf": "error", "bueno.pdf": "indexed"}
    failed = next(d for d in repository.documents.values() if d.filename == "escaneado.pdf")
    assert failed.status is DocumentStatus.ERROR and "texto" in (failed.error_message or "")


async def test_force_reindexa_todo(tmp_path: Path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF a")
    use_case, _, _, _ = _use_case()
    await use_case.execute(tmp_path)
    report = await use_case.execute(tmp_path, force=True)
    assert [o.action for o in report.outcomes] == ["reindexed"]


async def test_documento_registrado_pero_ausente_del_indice_se_reindexa(tmp_path: Path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF a")
    use_case, _, _, _ = _use_case()
    await use_case.execute(tmp_path)
    report = await use_case.execute(tmp_path, indexed_ids=set())  # p. ej. volumen de Chroma borrado
    assert [o.action for o in report.outcomes] == ["reindexed"]
