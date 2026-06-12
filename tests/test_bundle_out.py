import hashlib
import json
import zipfile
from io import BytesIO
from urllib.request import Request, urlopen

import pytest

from ask_chatgpt.bundle import (
    ASK_CHATGPT_BUNDLE_README,
    UploadBundleCaps,
    build_bundle,
    generate_prompt_instructions,
    upload_bundle,
)
from ask_chatgpt.driver import BrowserSession
from ask_chatgpt.errors import BundleIntegrityError, OversizedPayloadError, PathEscapeError, UploadUnsupportedError


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
    assert "Return exactly one patch bundle containing only changed/deleted paths and `manifest.json`" in readme
    for token in ("BEGIN_PATCH_BUNDLE", "END_PATCH_BUNDLE", "ZIP_BYTE_COUNT", "ZIP_SHA256", "MANIFEST_JSON"):
        assert token in readme


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


def test_prompt_instructions_text_uses_protocol_tokens():
    text = generate_prompt_instructions("Refactor the parser.", bundle_filename="bundle.zip")

    assert "I uploaded a zip project-context bundle named `bundle.zip`" in text
    assert "First read `ASK_CHATGPT_BUNDLE_README.md` inside the zip" in text
    assert "Refactor the parser." in text
    assert "PATCH_BUNDLE_DOWNLOAD_READY: patch-bundle.zip" in text
    assert "BEGIN_PATCH_BUNDLE" in text
    assert "END_PATCH_BUNDLE" in text


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


@pytest.mark.parametrize(
    ("mode", "expected_error"),
    [
        ("unsupported", UploadUnsupportedError),
        ("reject_size_type", OversizedPayloadError),
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
