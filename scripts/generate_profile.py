#!/usr/bin/env python3
"""Generate Ismat Babirli's light and dark GitHub profile cards."""

from __future__ import annotations

import base64
import io
import json
import os
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "profile.json"
API_ROOT = "https://api.github.com"

THEMES = {
    "dark": {
        "background": "#0d1117",
        "portrait_background": "#161b22",
        "border": "#30363d",
        "text": "#f0f6fc",
        "muted": "#8b949e",
        "accent": "#ffa657",
        "value": "#79c0ff",
        "success": "#3fb950",
        "ascii": "#c9d1d9",
    },
    "light": {
        "background": "#ffffff",
        "portrait_background": "#f6f8fa",
        "border": "#d0d7de",
        "text": "#24292f",
        "muted": "#57606a",
        "accent": "#bc4c00",
        "value": "#0969da",
        "success": "#1a7f37",
        "ascii": "#24292f",
    },
}


def api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{API_ROOT}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ismatBabirli-profile-readme",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        return json.load(response)


def github_stats(username: str) -> dict[str, int]:
    user = api_get(f"/users/{username}")
    repos: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = api_get(
            f"/users/{username}/repos",
            {"type": "owner", "per_page": 100, "page": page},
        )
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return {
        "followers": int(user.get("followers", 0)),
        "stars": sum(int(repo.get("stargazers_count", 0)) for repo in repos),
    }


def download_avatar(url: str) -> Image.Image:
    request = Request(url, headers={"User-Agent": "ismatBabirli-profile-readme"})
    with urlopen(request, timeout=30) as response:
        return Image.open(io.BytesIO(response.read())).convert("RGB")


def ascii_portrait(
    image: Image.Image,
    crop: list[float],
    *,
    light_theme: bool,
) -> str:
    """Return a PNG data URI containing a true-color ASCII character mosaic."""
    columns, rows = 50, 44
    image_width, image_height = image.size
    left, top, right, bottom = crop
    portrait = image.crop(
        (
            round(image_width * left),
            round(image_height * top),
            round(image_width * right),
            round(image_height * bottom),
        )
    ).convert("RGB")
    portrait = ImageEnhance.Color(portrait).enhance(0.9)
    portrait = ImageEnhance.Contrast(portrait).enhance(1.08)
    portrait = ImageEnhance.Brightness(portrait).enhance(1.1)
    portrait = portrait.filter(
        ImageFilter.UnsharpMask(radius=1.1, percent=125, threshold=2)
    )
    portrait = portrait.resize((columns, rows), Image.Resampling.LANCZOS)

    font = ImageFont.load_default(size=9)
    cell_width, cell_height = 7, 11
    canvas = Image.new(
        "RGBA",
        (columns * cell_width, rows * cell_height),
        (0, 0, 0, 0),
    )
    draw = ImageDraw.Draw(canvas)
    pixels = portrait.load()

    for y in range(rows):
        for x in range(columns):
            red, green, blue = pixels[x, y]
            normalized_x = (x - columns * 0.5) / (columns * 0.57)
            normalized_y = (y - rows * 0.5) / (rows * 0.64)
            distance = (normalized_x**2 + normalized_y**2) ** 0.5
            if distance <= 0.84:
                alpha = 255
            elif distance >= 1.08:
                alpha = 0
            else:
                alpha = round(255 * (1.08 - distance) / 0.24)

            # Lift deep tones slightly on the dark card so the real hair,
            # beard, and eye contours remain visible against the panel.
            if not light_theme:
                red = min(255, round(34 + red * 0.88))
                green = min(255, round(34 + green * 0.88))
                blue = min(255, round(34 + blue * 0.88))

            draw.text(
                (x * cell_width, y * cell_height),
                "@",
                font=font,
                fill=(red, green, blue, alpha),
            )

    output = io.BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def kv_line(y: int, key: str, value: str, dots: int = 18) -> str:
    return (
        f'<text x="520" y="{y}" class="body">'
        f'<tspan class="key">{escape(key)}</tspan>'
        f'<tspan class="muted"> {"." * dots} </tspan>'
        f'<tspan class="value">{escape(value)}</tspan>'
        "</text>"
    )


def section(y: int, label: str) -> str:
    return (
        f'<text x="520" y="{y}" class="section">'
        f'<tspan class="prompt">›</tspan> {escape(label.upper())}'
        "</text>"
    )


def render_svg(
    theme_name: str,
    config: dict[str, Any],
    stats: dict[str, int],
    portrait: str,
) -> str:
    theme = THEMES[theme_name]
    identity = config["identity"]
    environment = config["environment"]
    contacts = config["contacts"]
    configured_stats = config["stats"]

    final_stats = {
        name: configured_stats.get(name)
        if configured_stats.get(name) is not None
        else stats.get(name, 0)
        for name in ("repositories", "contributed", "contributions", "followers", "stars")
    }
    final_stats = {
        name: f"{int(value):,}" for name, value in final_stats.items()
    }

    lines = [
        section(124, "identity"),
        kv_line(154, "role", identity["role"], 12),
        kv_line(182, "company", identity["company"], 9),
        kv_line(210, "location", identity["location"], 8),
        kv_line(238, "uptime", identity["uptime"], 10),
        section(282, "environment"),
        kv_line(312, "os", environment["os"], 14),
        kv_line(340, "editors", environment["editors"], 9),
        kv_line(368, "languages", environment["languages"], 7),
        kv_line(396, "infra", environment["infrastructure"], 11),
        kv_line(424, "interests", environment["interests"], 7),
        section(468, "contact"),
        kv_line(498, "x", contacts["x"], 15),
        kv_line(526, "linkedin", contacts["linkedin"], 8),
        section(570, "github"),
        (
            '<text x="520" y="600" class="body">'
            '<tspan class="key">repos</tspan><tspan class="muted"> ..... </tspan>'
            f'<tspan class="value">{final_stats["repositories"]}</tspan>'
            '<tspan class="muted">  |  </tspan>'
            '<tspan class="key">contributed</tspan><tspan class="muted"> ... </tspan>'
            f'<tspan class="value">{final_stats["contributed"]}</tspan>'
            "</text>"
        ),
        (
            '<text x="520" y="628" class="body">'
            '<tspan class="key">contributions</tspan><tspan class="muted"> ... </tspan>'
            f'<tspan class="success">{final_stats["contributions"]}</tspan>'
            '<tspan class="muted">  |  </tspan>'
            '<tspan class="key">followers</tspan><tspan class="muted"> ... </tspan>'
            f'<tspan class="value">{final_stats["followers"]}</tspan>'
            '<tspan class="muted">  |  </tspan>'
            '<tspan class="key">stars</tspan><tspan class="muted"> ... </tspan>'
            f'<tspan class="value">{final_stats["stars"]}</tspan>'
            "</text>"
        ),
    ]

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1180" height="660" viewBox="0 0 1180 660" role="img" aria-labelledby="title description">
  <title id="title">Ismat Babirli — Senior Software Engineer</title>
  <desc id="description">A terminal-style GitHub profile card with an ASCII portrait, professional details, interests, contacts, and GitHub statistics.</desc>
  <style>
    text {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; }}
    .chrome {{ font-size: 13px; fill: {theme["muted"]}; letter-spacing: .4px; }}
    .headline {{ font-size: 25px; font-weight: 700; fill: {theme["text"]}; }}
    .section {{ font-size: 14px; font-weight: 700; fill: {theme["muted"]}; letter-spacing: 1.8px; }}
    .body {{ font-size: 16px; fill: {theme["text"]}; white-space: pre; }}
    .key {{ fill: {theme["accent"]}; }}
    .value {{ fill: {theme["value"]}; }}
    .success {{ fill: {theme["success"]}; }}
    .muted {{ fill: {theme["muted"]}; }}
    .prompt {{ fill: {theme["success"]}; }}
  </style>
  <rect x="1" y="1" width="1178" height="658" rx="20" fill="{theme["background"]}" stroke="{theme["border"]}" stroke-width="2"/>
  <path d="M1 68H1179" stroke="{theme["border"]}"/>
  <circle cx="32" cy="34" r="7" fill="#ff5f57"/>
  <circle cx="56" cy="34" r="7" fill="#febc2e"/>
  <circle cx="80" cy="34" r="7" fill="#28c840"/>
  <text x="104" y="39" class="chrome">profile://ismatBabirli</text>
  <rect x="24" y="88" width="424" height="546" rx="15" fill="{theme["portrait_background"]}" stroke="{theme["border"]}"/>
  <image x="46" y="98" width="380" height="526" href="{portrait}" preserveAspectRatio="xMidYMid meet"/>
  <path d="M480 92V634" stroke="{theme["border"]}" stroke-dasharray="3 7"/>
  <text x="520" y="92" class="headline">{escape(config["headline"])}</text>
  <text x="1138" y="91" text-anchor="end" class="chrome">~/profile</text>
  {''.join(lines)}
</svg>
'''


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    username = config["github_username"]
    stats = github_stats(username)
    avatar = download_avatar(config["avatar_url"])

    for theme_name in THEMES:
        portrait = ascii_portrait(
            avatar,
            config["avatar_crop"],
            light_theme=theme_name == "light",
        )
        svg = render_svg(theme_name, config, stats, portrait)
        (ROOT / f"{theme_name}_mode.svg").write_text(svg, encoding="utf-8")

    print(
        "Generated light_mode.svg and dark_mode.svg "
        f"(followers: {stats['followers']}, stars: {stats['stars']})"
    )


if __name__ == "__main__":
    main()
