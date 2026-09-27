"""Tests for ``core/images.py``: template image path containment + content probe.

D5: a template's ``source_path`` resolves relative to the template file.
Absolute paths, ``..`` components and symlinks escaping the template dir are
rejected. ``probe_image`` decides the format from the bytes, never the
extension, so a secret named ``photo.jpg`` can't be embedded into SVG output.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image

from holiday_card.core.images import (
    MAX_IMAGE_PIXELS,
    ImageSourceError,
    ProbedImage,
    probe_image,
    resolve_template_image_path,
)

FIXTURE_IMAGE = Path(__file__).parent.parent / "fixtures" / "sample_photo.jpg"


@pytest.fixture
def template_dir(tmp_path: Path) -> Path:
    d = tmp_path / "templates" / "christmas"
    (d / "sub").mkdir(parents=True)
    shutil.copy(FIXTURE_IMAGE, d / "sample_photo.jpg")
    Image.new("RGB", (4, 3), "red").save(d / "sub" / "p.png")
    return d


class TestResolveTemplateImagePath:
    def test_accepts_sibling_file(self, template_dir: Path) -> None:
        resolved = resolve_template_image_path("sample_photo.jpg", template_dir)
        assert resolved == (template_dir / "sample_photo.jpg").resolve()
        assert resolved.is_absolute()

    def test_accepts_subdirectory_file(self, template_dir: Path) -> None:
        resolved = resolve_template_image_path("sub/p.png", template_dir)
        assert resolved == (template_dir / "sub" / "p.png").resolve()

    def test_rejects_absolute_path(self, template_dir: Path) -> None:
        with pytest.raises(ImageSourceError, match="absolute"):
            resolve_template_image_path(
                str(template_dir / "sample_photo.jpg"), template_dir
            )

    @pytest.mark.parametrize("source", ["../x.jpg", "a/../../x.jpg", "sub/../p.png"])
    def test_rejects_dotdot_components(self, template_dir: Path, source: str) -> None:
        with pytest.raises(ImageSourceError, match=r"\.\."):
            resolve_template_image_path(source, template_dir)

    def test_rejects_symlink_escaping_template_dir(
        self, template_dir: Path, tmp_path: Path
    ) -> None:
        secret = tmp_path / "secret.env"
        secret.write_text("AWS_SECRET_ACCESS_KEY=hunter2")
        (template_dir / "link.jpg").symlink_to(secret)
        with pytest.raises(ImageSourceError, match="outside"):
            resolve_template_image_path("link.jpg", template_dir)

    def test_rejects_empty_path(self, template_dir: Path) -> None:
        with pytest.raises(ImageSourceError):
            resolve_template_image_path("", template_dir)


class TestProbeImage:
    def test_fixture_is_400px_jpeg(self) -> None:
        probed = probe_image(FIXTURE_IMAGE)
        assert probed == ProbedImage(
            path=FIXTURE_IMAGE.resolve(), format="jpeg", width_px=400, height_px=400
        )

    def test_png_is_detected(self, template_dir: Path) -> None:
        probed = probe_image(template_dir / "sub" / "p.png")
        assert (probed.format, probed.width_px, probed.height_px) == ("png", 4, 3)

    def test_rejects_text_file_named_jpg(self, tmp_path: Path) -> None:
        fake = tmp_path / "secret.jpg"
        fake.write_text("AWS_SECRET_ACCESS_KEY=hunter2")
        with pytest.raises(ImageSourceError, match="secret.jpg"):
            probe_image(fake)

    def test_rejects_gif(self, tmp_path: Path) -> None:
        gif = tmp_path / "anim.gif"
        Image.new("RGB", (4, 4), "blue").save(gif, format="GIF")
        with pytest.raises(ImageSourceError, match="GIF"):
            probe_image(gif)

    def test_rejects_gif_renamed_png(self, tmp_path: Path) -> None:
        gif = tmp_path / "anim.png"
        Image.new("RGB", (4, 4), "blue").save(gif, format="GIF")
        with pytest.raises(ImageSourceError, match="GIF"):
            probe_image(gif)

    def test_rejects_truncated_jpeg(self, tmp_path: Path) -> None:
        truncated = tmp_path / "cut.jpg"
        truncated.write_bytes(FIXTURE_IMAGE.read_bytes()[:600])
        with pytest.raises(ImageSourceError, match="cut.jpg"):
            probe_image(truncated)

    def test_rejects_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ImageSourceError, match="nope.png"):
            probe_image(tmp_path / "nope.png")

    def test_rejects_images_above_pixel_limit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        big = tmp_path / "big.png"
        Image.new("RGB", (20, 10), "white").save(big)
        monkeypatch.setattr("holiday_card.core.images.MAX_IMAGE_PIXELS", 199)
        with pytest.raises(ImageSourceError, match="megapixel"):
            probe_image(big)

    def test_pixel_limit_is_50_megapixels(self) -> None:
        assert MAX_IMAGE_PIXELS == 50_000_000

    def test_rejects_decompression_bomb_cleanly(self, tmp_path: Path) -> None:
        # 225 MP: above Pillow's own 2x bomb limit, so ``Image.open`` raises.
        bomb = tmp_path / "bomb.png"
        Image.new("1", (15_000, 15_000)).save(bomb)
        with pytest.raises(ImageSourceError, match="bomb.png"):
            probe_image(bomb)
