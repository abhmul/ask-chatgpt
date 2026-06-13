import hashlib
import json
import zipfile
from io import BytesIO
from types import SimpleNamespace
from urllib.request import Request, urlopen

import pytest

import ask_chatgpt.bundle as bundle_module
from ask_chatgpt.bundle import (
    ASK_CHATGPT_BUNDLE_README,
    UploadBundleCaps,
    build_bundle,
    generate_catalogue_readme,
    generate_prompt_instructions,
    upload_bundle,
)
from ask_chatgpt.driver import BrowserSession
from ask_chatgpt.errors import BundleIntegrityError, OversizedPayloadError, PathEscapeError, UploadUnsupportedError
from ask_chatgpt.selector_map import SelectorMap


def _script(mock_chatgpt, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        mock_chatgpt.base_url + "/__script__",
        data=body,
        headers={"content-type": "application/json", "accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _make_project(root):
    (root / "src").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "src" / "alpha.py").write_text("print('alpha')\n", encoding="utf-8")
    (root / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")


def _zip_names(bundle):
    with zipfile.ZipFile(BytesIO(bundle.content)) as archive:
        return archive.namelist()


_FORBIDDEN_MODEL_FALLBACK_TERMS = (
    "base64",
    "base64url",
    "begin_patch_bundle",
    "end_patch_bundle",
    "fenced",
    "marker block",
    "5-line block",
    "paste",
)


def _assert_model_text_requests_downloadable_zip_without_fallback_terms(text: str) -> None:
    lowered = text.lower()
    for term in _FORBIDDEN_MODEL_FALLBACK_TERMS:
        assert term not in lowered
    assert "downloadable `.zip` file" in text
    assert "download link" in lowered


class _FakeUploadLocator:
    def __init__(self, *, count: int = 1, visible: bool = True, on_set_input_files=None) -> None:
        self._count = count
        self._visible = visible
        self._on_set_input_files = on_set_input_files

    def count(self) -> int:
        return self._count

    @property
    def first(self):
        return self

    def set_input_files(self, files, **kwargs) -> None:
        if self._on_set_input_files is not None:
            self._on_set_input_files(files, kwargs)

    def get_attribute(self, _name: str, **_kwargs) -> str | None:
        return None

    def is_visible(self, **_kwargs) -> bool:
        return self._visible


class _FakeRealUploadPage:
    def __init__(self, *, chip_visible: bool) -> None:
        self.uploads: list[tuple[object, dict]] = []
        self.wait_timeouts: list[int] = []
        self._chip_visible = chip_visible

    def locator(self, selector: str):
        if selector == "#upload":
            return _FakeUploadLocator(on_set_input_files=self._record_upload)
        if selector == bundle_module._UPLOAD_STATUS_SELECTOR:
            return _FakeUploadLocator(count=0)
        if selector == 'text="real-chip.zip"':
            return _FakeUploadLocator(count=1 if self._chip_visible else 0, visible=self._chip_visible)
        raise AssertionError(f"unexpected selector: {selector}")

    def get_by_text(self, text: str, *, exact: bool = False):
        assert text == "real-chip.zip"
        assert exact is True
        return _FakeUploadLocator(count=1 if self._chip_visible else 0, visible=self._chip_visible)

    def wait_for_timeout(self, timeout_ms: int) -> None:
        self.wait_timeouts.append(timeout_ms)

    def _record_upload(self, files, kwargs) -> None:
        self.uploads.append((files, kwargs))


def _fake_real_upload_session(page: _FakeRealUploadPage):
    return SimpleNamespace(
        channel="real",
        page=page,
        selectors=SelectorMap(channel="unit", selectors={"upload_input": "#upload"}, attributes={}),
    )


def test_catalogue_readme_contains_required_protocol_content_and_is_deterministic(tmp_path):
    root = tmp_path / "sample-project"
    root.mkdir()
    _make_project(root)

    first = build_bundle(files=["src/alpha.py"], dirs=["docs"], root=root)
    second = build_bundle(files=["src/alpha.py"], dirs=["docs"], root=root)

    assert first.content == second.content
    assert first.readme == second.readme
    with zipfile.ZipFile(BytesIO(first.content)) as archive:
        readme = archive.read(ASK_CHATGPT_BUNDLE_README).decode("utf-8")

    src_bytes = (root / "src" / "alpha.py").read_bytes()
    docs_bytes = (root / "docs" / "guide.md").read_bytes()
    assert "# ask-chatgpt bundle instructions" in readme
    assert "Project root display name: `sample-project`" in readme
    assert "Every project file path below is repo-root-relative" in readme
    assert "Never use absolute paths, drive letters, leading `/`, backslashes, empty path segments, or `..`" in readme
    assert f"| `src/alpha.py` | `src/alpha.py` | text | {len(src_bytes)} | `{hashlib.sha256(src_bytes).hexdigest()}` |" in readme
    assert f"| `docs/guide.md` | `docs/guide.md` | text | {len(docs_bytes)} | `{hashlib.sha256(docs_bytes).hexdigest()}` |" in readme
    assert "Create exactly one actual downloadable `.zip` file" in readme
    assert "provide the download link to that file" in readme
    assert "with no wrapping directory" in readme
    assert "A top-level `manifest.json` is optional for added or modified files" in readme
    assert '"status": "deleted"' in readme
    assert "Patch caps: zip < 25 MiB, each file < 5 MiB, and at most 1000 files" in readme
    _assert_model_text_requests_downloadable_zip_without_fallback_terms(readme)
    assert "MANIFEST_JSON:" not in readme


def test_zip_layout_is_root_relative_sorted_and_has_no_dot_prefixes(tmp_path):
    root = tmp_path / "sample-project"
    root.mkdir()
    _make_project(root)

    bundle = build_bundle(files=["src/alpha.py"], dirs=["docs"], root=root)

    assert _zip_names(bundle) == [ASK_CHATGPT_BUNDLE_README, "docs/guide.md", "src/alpha.py"]
    assert all(not name.startswith("./") for name in _zip_names(bundle))
    with zipfile.ZipFile(BytesIO(bundle.content)) as archive:
        assert archive.read("src/alpha.py") == b"print('alpha')\n"
        assert archive.read("docs/guide.md") == b"# Guide\n"


def test_path_rule_rejections_are_build_time_errors(tmp_path):
    root = tmp_path / "sample-project"
    root.mkdir()
    _make_project(root)

    with pytest.raises(PathEscapeError, match="absolute"):
        build_bundle(files=[root / "src" / "alpha.py"], root=root)
    with pytest.raises(PathEscapeError, match="traversal"):
        build_bundle(files=["../outside.txt"], root=root)

    (root / ASK_CHATGPT_BUNDLE_README).write_text("caller file", encoding="utf-8")
    with pytest.raises(PathEscapeError, match="reserved"):
        build_bundle(files=[ASK_CHATGPT_BUNDLE_README], root=root)

    with pytest.raises(PathEscapeError, match="duplicate"):
        build_bundle(files=["src/alpha.py"], dirs=["src"], root=root)


def test_size_type_guard_rejects_oversized_and_disallowed_entries(tmp_path):
    root = tmp_path / "sample-project"
    root.mkdir()
    (root / "big.bin").write_bytes(b"1234")
    (root / "directory-as-file").mkdir()
    caps = UploadBundleCaps(max_file_bytes=3, max_total_file_bytes=100, max_zip_bytes=1000, max_file_count=10)

    with pytest.raises(OversizedPayloadError, match="UPLOAD_BUNDLE_MAX_FILE_BYTES"):
        build_bundle(files=["big.bin"], root=root, caps=caps)
    with pytest.raises(OversizedPayloadError, match="regular file"):
        build_bundle(files=["directory-as-file"], root=root)


def test_model_facing_bundle_outputs_request_downloadable_zip_without_parser_fallback_terms():
    prompt = generate_prompt_instructions("Refactor the parser.", bundle_filename="bundle.zip")
    catalogue = generate_catalogue_readme(
        (),
        project_root_name="sample-project",
        bundle_id="bundle-id",
        created_at_iso8601="2026-06-13T00:00:00Z",
    )

    for text in (prompt, catalogue):
        _assert_model_text_requests_downloadable_zip_without_fallback_terms(text)


def test_prompt_instructions_text_requests_downloadable_zip():
    text = generate_prompt_instructions("Refactor the parser.", bundle_filename="bundle.zip")

    assert "I uploaded a zip project-context bundle named `bundle.zip`" in text
    assert "First read `ASK_CHATGPT_BUNDLE_README.md` inside the zip" in text
    assert "Refactor the parser." in text
    assert "PATCH_BUNDLE_DOWNLOAD_READY" not in text
    assert "create exactly one actual downloadable `.zip` file" in text
    assert "provide the download link to that file" in text
    assert "The `.zip` must contain only changed or added file payloads" in text
    assert "A top-level `manifest.json` is optional for added or modified files" in text
    assert '"status": "deleted"' in text
    assert "Return exactly one downloadable `.zip` file per response" in text


def test_upload_happy_path_records_bundle_metadata(mock_chatgpt, tmp_path):
    root = tmp_path / "sample-project"
    root.mkdir()
    _make_project(root)
    bundle = build_bundle(files=["src/alpha.py"], dirs=["docs"], root=root)
    mock_chatgpt.reset()
    _script(mock_chatgpt, {"upload_mode": "ok"})

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        session.open_or_create_conversation(None)
        confirmation = upload_bundle(session, bundle, timeout_s=5.0)

    inspected = mock_chatgpt.inspect()
    assert inspected["last_upload"] == {
        "filename": bundle.filename,
        "size": len(bundle.content),
        "sha256": hashlib.sha256(bundle.content).hexdigest(),
        "content_type": "application/zip",
        "status": "ok",
    }
    assert confirmation.status == "ok"
    assert confirmation.sha256 == inspected["last_upload"]["sha256"]


def test_real_upload_confirms_with_visible_filename_chip_when_mock_status_is_absent(monkeypatch):
    monkeypatch.setattr(bundle_module, "_REAL_UPLOAD_CHIP_TIMEOUT_S", 0.1)
    page = _FakeRealUploadPage(chip_visible=True)

    confirmation = upload_bundle(_fake_real_upload_session(page), b"zip bytes", filename="real-chip.zip", timeout_s=0.01)

    assert confirmation.status == "ok"
    assert confirmation.filename == "real-chip.zip"
    assert page.uploads


def test_real_upload_without_status_or_filename_chip_times_out(monkeypatch):
    monkeypatch.setattr(bundle_module, "_REAL_UPLOAD_CHIP_TIMEOUT_S", 0.01)
    page = _FakeRealUploadPage(chip_visible=False)

    with pytest.raises(UploadUnsupportedError, match="upload did not confirm before timeout"):
        upload_bundle(_fake_real_upload_session(page), b"zip bytes", filename="real-chip.zip", timeout_s=0.01)


@pytest.mark.parametrize(
    ("mode", "expected_error"),
    [
        ("unsupported", UploadUnsupportedError),
        ("reject_size_type", UploadUnsupportedError),
        ("corrupt", BundleIntegrityError),
    ],
)
def test_upload_failures_map_to_named_errors(mock_chatgpt, tmp_path, mode, expected_error):
    root = tmp_path / "sample-project"
    root.mkdir()
    _make_project(root)
    bundle = build_bundle(files=["src/alpha.py"], root=root)
    mock_chatgpt.reset()
    _script(mock_chatgpt, {"upload_mode": mode})

    with BrowserSession(channel="mock", base_url=mock_chatgpt.base_url) as session:
        session.open_or_create_conversation(None)
        with pytest.raises(expected_error):
            upload_bundle(session, bundle, timeout_s=5.0)

    if mode != "unsupported":
        assert mock_chatgpt.inspect()["last_upload"]["status"] in {"rejected", "corrupt"}


def test_upload_local_preflight_cap_rejects_before_ui_interaction():
    caps = UploadBundleCaps(max_file_bytes=10, max_total_file_bytes=10, max_zip_bytes=1, max_file_count=10)

    with pytest.raises(OversizedPayloadError, match="UPLOAD_BUNDLE_MAX_ZIP_BYTES"):
        upload_bundle(object(), b"oversized", caps=caps)
