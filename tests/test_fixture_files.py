import base64
import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

from playwright.sync_api import expect, sync_playwright

from tests.fixtures.mock_chatgpt.server import build_mock_patch_zip


SELECTOR_MAP_PATH = Path("src/ask_chatgpt/selector_maps/mock.json")


def _selectors() -> dict[str, str]:
    return json.loads(SELECTOR_MAP_PATH.read_text(encoding="utf-8"))["selectors"]


def _post_script(mock_chatgpt, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        mock_chatgpt.base_url + "/__script__",
        data=body,
        headers={"content-type": "application/json", "accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _conversation_url(mock_chatgpt, ref: str) -> str:
    return mock_chatgpt.base_url + "/c/" + quote(ref)


def _drive_scripted_turn(page, mock_chatgpt, selectors: dict[str, str], payload: dict, prompt: str = "bundle prompt"):
    mock_chatgpt.reset()
    _post_script(mock_chatgpt, payload)
    page.goto(mock_chatgpt.base_url, wait_until="load")
    page.locator(selectors["new_chat_button"]).click()
    expect(page.locator(selectors["ready_root"])).to_be_visible(timeout=5000)
    page.locator(selectors["composer"]).fill(prompt)
    page.locator(selectors["send_button"]).click()
    completed = page.locator(selectors["assistant_message"]).filter(has=page.locator(selectors["completion_marker"]))
    expect(completed).to_have_count(1, timeout=5000)
    return completed.last


def _validate_patch_zip(path: Path) -> dict:
    assert zipfile.is_zipfile(path)
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        assert manifest["total_byte_count"] == sum(item["size"] for item in manifest["files"])
        for item in manifest["files"]:
            data = archive.read(item["path"])
            assert len(data) == item["size"]
            assert hashlib.sha256(data).hexdigest() == item["sha256"]
    return manifest


def _parse_fenced_bundle(text: str) -> dict:
    assert "BEGIN_PATCH_BUNDLE" in text
    assert "END_PATCH_BUNDLE" in text
    block = text.split("BEGIN_PATCH_BUNDLE", 1)[1].split("END_PATCH_BUNDLE", 1)[0]
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    zip_byte_count_line = next(line for line in lines if line.startswith("ZIP_BYTE_COUNT"))
    zip_sha_line = next(line for line in lines if line.startswith("ZIP_SHA256"))
    base64_line = next(line for line in lines if line.startswith("BASE64URL"))
    assert all(not line.startswith("MANIFEST_JSON") for line in lines)
    assert ":" not in zip_byte_count_line.split()[0]
    assert ":" not in zip_sha_line.split()[0]
    encoded = base64_line.split(maxsplit=1)[1]
    padding = "=" * (-len(encoded) % 4)
    decoded = base64.urlsafe_b64decode((encoded + padding).encode("ascii"))
    return {
        "zip_byte_count": int(zip_byte_count_line.split(maxsplit=1)[1]),
        "zip_sha256": zip_sha_line.split(maxsplit=1)[1],
        "zip_bytes": decoded,
    }


def test_download_artifact_ok_serves_real_zip_with_attachment_header(mock_chatgpt, tmp_path):
    selectors = _selectors()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            latest = _drive_scripted_turn(page, mock_chatgpt, selectors, {"text": "download ok", "download_mode": "ok"})
            artifact = latest.locator(selectors["download_artifact"])
            expect(artifact).to_have_count(1)
            href = artifact.get_attribute("href")
            assert href

            with page.expect_download() as download_info:
                artifact.click()
            download = download_info.value
            target = tmp_path / download.suggested_filename
            download.save_as(str(target))

            assert download.suggested_filename.endswith(".zip")
            manifest = _validate_patch_zip(target)
            expected_zip, expected_manifest = build_mock_patch_zip()
            assert manifest == expected_manifest
            assert hashlib.sha256(target.read_bytes()).hexdigest() == hashlib.sha256(expected_zip).hexdigest()

            with urlopen(urljoin(mock_chatgpt.base_url, href), timeout=5) as response:
                assert response.headers["Content-Disposition"].startswith("attachment; filename=")
                assert response.headers["Content-Type"] == "application/zip"
            context.close()
        finally:
            browser.close()


def test_download_artifact_variants_are_scriptable_and_detectable(mock_chatgpt, tmp_path):
    selectors = _selectors()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()

            for mode in ("missing", "unsupported"):
                latest = _drive_scripted_turn(page, mock_chatgpt, selectors, {"text": f"download {mode}", "download_mode": mode})
                expect(latest.locator(selectors["download_artifact"])).to_have_count(0)
                if mode == "unsupported":
                    expect(latest.locator('[data-testid="download-unsupported"]')).to_be_visible()

            for mode in ("corrupt", "truncated"):
                latest = _drive_scripted_turn(page, mock_chatgpt, selectors, {"text": f"download {mode}", "download_mode": mode})
                artifact = latest.locator(selectors["download_artifact"])
                expect(artifact).to_have_count(1)
                with page.expect_download() as download_info:
                    artifact.click()
                download = download_info.value
                target = tmp_path / f"{mode}-{download.suggested_filename}"
                download.save_as(str(target))
                assert not zipfile.is_zipfile(target)

            latest = _drive_scripted_turn(page, mock_chatgpt, selectors, {"text": "download delayed", "download_mode": "delayed"})
            expect(latest.locator(selectors["download_artifact"])).to_have_count(0)
            page.reload(wait_until="load")
            delayed_latest = page.locator(selectors["assistant_message"]).filter(has=page.locator(selectors["completion_marker"])).last
            expect(delayed_latest.locator(selectors["download_artifact"])).to_have_count(1)

            latest = _drive_scripted_turn(page, mock_chatgpt, selectors, {"text": "download collision", "download_mode": "collision"})
            collision_links = latest.locator(selectors["download_artifact"])
            expect(collision_links).to_have_count(2)
            filenames = [collision_links.nth(index).get_attribute("data-filename") for index in range(2)]
            assert filenames[0] == filenames[1]

            mock_chatgpt.reset()
            _post_script(mock_chatgpt, {"text": "older download", "download_mode": "ok"})
            page.goto(mock_chatgpt.base_url, wait_until="load")
            page.locator(selectors["new_chat_button"]).click()
            page.locator(selectors["composer"]).fill("older prompt")
            page.locator(selectors["send_button"]).click()
            completed = page.locator(selectors["assistant_message"]).filter(has=page.locator(selectors["completion_marker"]))
            expect(completed).to_have_count(1, timeout=5000)
            older_turn = completed.last
            older_turn_id = older_turn.get_attribute("data-turn-id")
            ref = page.locator(selectors["ready_root"]).get_attribute("data-conversation-ref")
            assert ref and older_turn_id

            _post_script(mock_chatgpt, {"text": "latest wrong older", "conversation_ref": ref, "download_mode": "wrong_older"})
            page.locator(selectors["composer"]).fill("latest prompt")
            page.locator(selectors["send_button"]).click()
            completed = page.locator(selectors["assistant_message"]).filter(has=page.locator(selectors["completion_marker"]))
            expect(completed).to_have_count(2, timeout=5000)
            latest_wrong = completed.last
            wrong_link = latest_wrong.locator(selectors["download_artifact"])
            expect(wrong_link).to_have_count(1)
            assert wrong_link.get_attribute("data-source-turn-id") == older_turn_id
            assert wrong_link.get_attribute("data-source-turn-id") != latest_wrong.get_attribute("data-turn-id")
            context.close()
        finally:
            browser.close()


def test_fenced_base64url_patch_bundle_ok_and_variants(mock_chatgpt):
    selectors = _selectors()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            latest = _drive_scripted_turn(page, mock_chatgpt, selectors, {"text": "fenced ok", "fenced_mode": "ok"})
            text = latest.locator(selectors["message_body"]).inner_text()
            bundle = _parse_fenced_bundle(text)
            expected_zip, _expected_manifest = build_mock_patch_zip(embed_manifest=False)
            assert bundle["zip_bytes"] == expected_zip
            assert bundle["zip_byte_count"] == len(bundle["zip_bytes"])
            assert bundle["zip_sha256"] == hashlib.sha256(bundle["zip_bytes"]).hexdigest()
            assert zipfile.is_zipfile(BytesIO(bundle["zip_bytes"]))
            with zipfile.ZipFile(BytesIO(bundle["zip_bytes"])) as archive:
                assert "manifest.json" not in archive.namelist()

            latest = _drive_scripted_turn(page, mock_chatgpt, selectors, {"text": "fenced missing end", "fenced_mode": "missing_end"})
            missing_end_text = latest.locator(selectors["message_body"]).inner_text()
            assert "BEGIN_PATCH_BUNDLE" in missing_end_text
            assert "END_PATCH_BUNDLE" not in missing_end_text

            latest = _drive_scripted_turn(page, mock_chatgpt, selectors, {"text": "fenced bad hash", "fenced_mode": "bad_hash"})
            bad_hash = _parse_fenced_bundle(latest.locator(selectors["message_body"]).inner_text())
            assert bad_hash["zip_sha256"] != hashlib.sha256(bad_hash["zip_bytes"]).hexdigest()

            latest = _drive_scripted_turn(page, mock_chatgpt, selectors, {"text": "fenced oversized", "fenced_mode": "oversized"})
            oversized = _parse_fenced_bundle(latest.locator(selectors["message_body"]).inner_text())
            assert oversized["zip_byte_count"] > 64

            latest = _drive_scripted_turn(
                page,
                mock_chatgpt,
                selectors,
                {"text": "fenced changed and unchanged", "fenced_mode": "changed_and_unchanged"},
            )
            mixed = _parse_fenced_bundle(latest.locator(selectors["message_body"]).inner_text())
            with zipfile.ZipFile(BytesIO(mixed["zip_bytes"])) as archive:
                names = set(archive.namelist())
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            statuses = {item["status"] for item in manifest["files"]}
            assert statuses == {"changed", "unchanged"}
            for item in manifest["files"]:
                if item["status"] == "changed":
                    assert item["path"] in names
                else:
                    assert item["path"] not in names
        finally:
            browser.close()


def test_upload_input_records_tmp_path_file_metadata_and_variants(mock_chatgpt, tmp_path):
    selectors = _selectors()
    upload_path = tmp_path / "synthetic-upload.zip"
    zip_bytes, _manifest = build_mock_patch_zip()
    upload_path.write_bytes(zip_bytes)
    expected_sha = hashlib.sha256(zip_bytes).hexdigest()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            _post_script(mock_chatgpt, {"upload_mode": "ok"})
            page.goto(mock_chatgpt.base_url, wait_until="load")
            page.locator(selectors["upload_input"]).set_input_files(str(upload_path))
            expect(page.locator('[data-testid="mock-upload-status"]')).to_have_attribute("data-upload-status", "ok", timeout=5000)
            inspected = mock_chatgpt.inspect()
            assert inspected["last_upload"] == {
                "filename": upload_path.name,
                "size": upload_path.stat().st_size,
                "sha256": expected_sha,
                "content_type": "application/zip",
                "status": "ok",
            }

            _post_script(mock_chatgpt, {"upload_mode": "unsupported"})
            page.goto(mock_chatgpt.base_url, wait_until="load")
            expect(page.locator(selectors["upload_input"])).to_have_count(0)
            expect(page.locator('[data-testid="upload-unsupported"]')).to_be_visible()

            _post_script(mock_chatgpt, {"upload_mode": "reject_size_type"})
            page.goto(mock_chatgpt.base_url, wait_until="load")
            page.locator(selectors["upload_input"]).set_input_files(str(upload_path))
            status = page.locator('[data-testid="mock-upload-status"]')
            expect(status).to_have_attribute("data-upload-status", "rejected", timeout=5000)
            expect(status).to_have_attribute("data-reason", "file size/type rejected by mock")
            assert mock_chatgpt.inspect()["last_upload"]["status"] == "rejected"

            _post_script(mock_chatgpt, {"upload_mode": "corrupt"})
            page.goto(mock_chatgpt.base_url, wait_until="load")
            page.locator(selectors["upload_input"]).set_input_files(str(upload_path))
            expect(page.locator('[data-testid="mock-upload-status"]')).to_have_attribute("data-upload-status", "corrupt", timeout=5000)
            corrupt_record = mock_chatgpt.inspect()["last_upload"]
            assert corrupt_record["status"] == "corrupt"
            assert corrupt_record["original_sha256"] == expected_sha
            assert corrupt_record["sha256"] != expected_sha
        finally:
            browser.close()
