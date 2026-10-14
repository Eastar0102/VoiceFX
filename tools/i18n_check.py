"""번역 점검: 코드에서 원문(한국어) 문장을 모두 찾아 언어별 번역 파일과 비교한다.

    python tools/i18n_check.py                 # 언어별 빠진/안 쓰는 번역 개수
    python tools/i18n_check.py --missing en    # 빠진 원문 목록 (JSON) — 번역해서 locales/en.json에 넣는다
    python tools/i18n_check.py --prune         # 안 쓰는 번역을 파일에서 지운다

원문 수집 위치
- Python: t("...") 호출, presets.py의 목소리·효과 이름/설명/슬라이더 이름, 기본 사운드 이름
- index.html: 화면 글자(텍스트·title·placeholder), data-i18n-html 문장, 스크립트의 T("...")와 한국어 문자열
"""
from __future__ import annotations

import ast
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from voicefx.i18n import LANGUAGES, LOCALES_DIR, SOURCE_LANG  # noqa: E402

HANGUL = re.compile(r"[가-힣]")


def python_keys() -> set[str]:
    keys = set()
    call = re.compile(r"""\bt\(\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')""")
    for f in (ROOT / "voicefx").glob("*.py"):
        for m in call.finditer(f.read_text(encoding="utf-8")):
            keys.add(ast.literal_eval(m.group(1)))
    from voicefx.presets import MODULES, PRESETS
    from voicefx.soundboard import DEFAULT_SOUNDS
    for p in PRESETS:
        keys.update([p.name, p.description])
        keys.update(q.label for q in p.panel_params)
    for m in MODULES:
        keys.update([m.label, m.description])
        keys.update(q.label for q in m.params)
    keys.update(name for _, name in DEFAULT_SOUNDS)
    return keys


class _TextCollector(HTMLParser):
    """화면 HTML의 텍스트 조각과 title/placeholder (data-i18n-html 요소 안쪽은 제외)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.keys, self.skip_depth, self.stack = set(), 0, []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for a in ("title", "placeholder"):
            if attrs.get(a) and HANGUL.search(attrs[a]):
                self.keys.add(attrs[a].strip())
        if tag in ("br", "input", "img", "meta", "hr"):
            return
        self.stack.append("data-i18n-html" in attrs)
        if self.stack[-1]:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in ("br", "input", "img", "meta", "hr") or not self.stack:
            return
        if self.stack.pop():
            self.skip_depth -= 1

    def handle_data(self, data):
        text = data.strip()
        if text and not self.skip_depth and HANGUL.search(text):
            self.keys.add(text)


def html_keys() -> set[str]:
    src = (ROOT / "voicefx" / "ui" / "index.html").read_text(encoding="utf-8")
    markup, script = src.split("<script>", 1)
    markup = re.sub(r"<style>.*?</style>", "", markup, flags=re.S)
    keys = set()
    # 태그가 섞인 문장: 브라우저 innerHTML과 같은 모양(공백 하나로)으로
    for m in re.finditer(r"<(\w+)[^>]*data-i18n-html[^>]*>(.*?)</\1>", markup, flags=re.S):
        keys.add(re.sub(r"\s+", " ", m.group(2)).strip())
    collector = _TextCollector()
    collector.feed(markup)
    keys |= collector.keys

    script = "\n".join(line for line in script.splitlines() if not line.strip().startswith("//"))
    script = re.sub(r"\s//[^\n\"'`]*$", "", script, flags=re.M)  # 줄 끝 주석
    for m in re.finditer(r'\bT\(\s*"((?:[^"\\]|\\.)*)"', script):
        keys.add(json.loads(f'"{m.group(1)}"'))
    script = re.sub(r'\bT\(\s*"(?:[^"\\]|\\.)*"', "T(", script)
    for m in re.finditer(r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'|`((?:[^`\\]|\\.)*)`', script):
        lit = next(g for g in m.groups() if g is not None)
        if not HANGUL.search(lit):
            continue
        for attr in re.findall(r'(?:title|placeholder)="([^"]*)"', lit):
            if HANGUL.search(attr):
                keys.add(attr.strip())
        lit = re.sub(r"\$\{[^}]*\}", "\x00", lit)  # 템플릿 값 자리
        for piece in re.split(r"<[^>]+>|\x00", lit):
            piece = piece.strip()
            if piece and HANGUL.search(piece):
                keys.add(piece)
    return keys


def all_keys() -> set[str]:
    return python_keys() | html_keys()


def load(lang: str) -> dict:
    path = LOCALES_DIR / f"{lang}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main():
    keys = all_keys()
    langs = [lang for lang in LANGUAGES if lang != SOURCE_LANG]
    if "--missing" in sys.argv:
        lang = sys.argv[sys.argv.index("--missing") + 1]
        table = load(lang)
        missing = sorted(k for k in keys if not table.get(k))
        print(json.dumps(missing, ensure_ascii=False, indent=1))
        return
    if "--prune" in sys.argv:
        for lang in langs:
            table = load(lang)
            kept = {k: v for k, v in table.items() if k in keys}
            (LOCALES_DIR / f"{lang}.json").write_text(json.dumps(kept, ensure_ascii=False, indent=1) + "\n",
                                                      encoding="utf-8")
            print(f"{lang}: {len(table) - len(kept)}개 정리")
        return
    print(f"원문 {len(keys)}개")
    ok = True
    for lang in langs:
        table = load(lang)
        missing = [k for k in keys if not table.get(k)]
        unused = [k for k in table if k not in keys]
        bad = [k for k in keys & table.keys()
               if set(re.findall(r"\{\w+\}", k)) != set(re.findall(r"\{\w+\}", table[k]))]
        print(f"{lang}: 빠짐 {len(missing)} / 안 씀 {len(unused)} / 자리표시({{}}) 불일치 {len(bad)}")
        for k in bad:
            print("   불일치:", k)
        ok &= not missing and not bad
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
