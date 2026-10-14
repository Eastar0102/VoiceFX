"""보이스 프리셋.

목소리 = 효과 모듈 조합(recipe) + 각 값. 모듈은 정해진 순서로 이어 붙는다.
- 기본 목소리: recipe와 패널에 보여줄 핵심 슬라이더(quick)를 코드로 정의
- 내 목소리: 사용자가 모듈을 켜고 끄며 만든 것 (controller가 설정에 저장)
파라미터는 "모듈.값" 키로 "체인의 몇 번째 단계의 어떤 속성"을 가리키므로,
체인을 새로 만들지 않고도 실시간으로 값만 바꿀 수 있다 (engine.set_param).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pedalboard as pb

from .dsp import Gain, PitchShifter, RingModulator


@dataclass(frozen=True)
class ModParam:
    key: str
    label: str
    attr: str
    min: float
    max: float
    default: float
    step: float = 0.01
    unit: str = ""  # 화면 표시용: "반음", "Hz", "dB", "%", "초", "비트", ":1"
    stage: int = 0  # 모듈 안에서 몇 번째 단계인지 (EQ처럼 단계가 여러 개인 모듈)


@dataclass(frozen=True)
class Module:
    key: str
    label: str
    icon: str
    description: str
    make: Callable[[], list]
    params: list[ModParam]
    size: int = 1  # make()가 만드는 단계 수 (stage 계산용 — 매번 만들어 세지 않도록)


# 처리 순서대로 나열한다 (피치 → 대역 → 왜곡 → 공간 → 다이내믹스)
MODULES: list[Module] = [
    Module("pitch", "피치", "🎵", "목소리 높이와 음색(굵기)", lambda: [PitchShifter()], [
        ModParam("semitones", "목소리 높이", "semitones", -24, 24, 0, 0.5, "반음"),
        ModParam("formant", "음색 (굵기)", "formant", -12, 12, 0, 0.5, "반음"),
    ]),
    Module("highpass", "저음 자르기", "📉", "낮은 소리를 잘라 가볍게", lambda: [pb.HighpassFilter()], [
        ModParam("cutoff", "기준 주파수", "cutoff_frequency_hz", 20, 2000, 100, 10, "Hz"),
    ]),
    Module("eq", "EQ", "🎚️", "저음·중음·고음 크기 조절", lambda: [
        pb.LowShelfFilter(cutoff_frequency_hz=200), pb.PeakFilter(q=1.0), pb.HighShelfFilter(cutoff_frequency_hz=4000),
    ], [
        ModParam("low", "저음역", "gain_db", -15, 15, 0, 0.5, "dB", 0),
        ModParam("mid_freq", "중음역 위치", "cutoff_frequency_hz", 200, 5000, 1000, 10, "Hz", 1),
        ModParam("mid", "중음역", "gain_db", -15, 15, 0, 0.5, "dB", 1),
        ModParam("high", "고음역", "gain_db", -15, 15, 0, 0.5, "dB", 2),
    ], size=3),
    Module("ringmod", "링 모듈레이터", "🤖", "사인파를 곱해 금속성 기계음", lambda: [RingModulator()], [
        ModParam("freq", "금속 톤", "freq_hz", 10, 1000, 60, 1, "Hz"),
        ModParam("mix", "강도", "mix", 0, 1, 0.5, 0.01, "%"),
    ]),
    Module("distortion", "디스토션", "🔥", "소리를 찌그러뜨려 거칠게", lambda: [pb.Distortion()], [
        ModParam("drive", "거칠기", "drive_db", 0, 40, 12, 0.5, "dB"),
    ]),
    Module("bitcrush", "비트크러시", "👾", "음질을 낮춰 옛날 게임기 소리", lambda: [pb.Bitcrush()], [
        ModParam("bits", "음질 (비트)", "bit_depth", 2, 16, 8, 1, "비트"),
    ]),
    Module("lowpass", "고음 자르기", "📈", "높은 소리를 잘라 먹먹하게", lambda: [pb.LowpassFilter()], [
        ModParam("cutoff", "기준 주파수", "cutoff_frequency_hz", 300, 20000, 8000, 50, "Hz"),
    ]),
    Module("chorus", "코러스", "🌀", "여러 겹으로 울렁이는 소리", lambda: [pb.Chorus()], [
        ModParam("rate", "속도", "rate_hz", 0.1, 10, 1, 0.1, "Hz"),
        ModParam("depth", "깊이", "depth", 0, 1, 0.3, 0.01, "%"),
        ModParam("mix", "양", "mix", 0, 1, 0.5, 0.01, "%"),
    ]),
    Module("phaser", "페이저", "🌊", "쉭쉭 휘도는 소리", lambda: [pb.Phaser()], [
        ModParam("rate", "속도", "rate_hz", 0.1, 5, 0.5, 0.05, "Hz"),
        ModParam("depth", "깊이", "depth", 0, 1, 0.5, 0.01, "%"),
        ModParam("mix", "양", "mix", 0, 1, 0.5, 0.01, "%"),
    ]),
    Module("delay", "에코", "🔁", "메아리처럼 반복", lambda: [pb.Delay()], [
        ModParam("time", "간격", "delay_seconds", 0.01, 1.0, 0.25, 0.01, "초"),
        ModParam("feedback", "반복", "feedback", 0, 0.9, 0.3, 0.01, "%"),
        ModParam("mix", "양", "mix", 0, 1, 0.3, 0.01, "%"),
    ]),
    Module("reverb", "리버브", "🏛️", "방·동굴 같은 공간 울림", lambda: [pb.Reverb()], [
        ModParam("room", "공간 크기", "room_size", 0, 1, 0.5, 0.01, "%"),
        ModParam("damping", "울림 부드러움", "damping", 0, 1, 0.5, 0.01, "%"),
        ModParam("wet", "울림 양", "wet_level", 0, 1, 0.3, 0.01, "%"),
        ModParam("dry", "원음 양", "dry_level", 0, 1, 0.8, 0.01, "%"),
    ]),
    Module("compressor", "컴프레서", "🗜️", "큰 소리는 줄이고 작은 소리는 키워 고르게", lambda: [pb.Compressor()], [
        ModParam("threshold", "기준", "threshold_db", -60, 0, -20, 1, "dB"),
        ModParam("ratio", "압축 비율", "ratio", 1, 20, 4, 0.5, ":1"),
    ]),
]
MODULES_BY_KEY = {m.key: m for m in MODULES}
MODULE_ORDER = [m.key for m in MODULES]


@dataclass(frozen=True)
class Param:
    """체인 안의 실제 위치가 정해진 파라미터 (프리셋마다 켜진 모듈에 따라 stage가 달라진다)."""
    key: str  # "모듈.값" 또는 "volume"
    label: str
    stage: int
    attr: str
    min: float
    max: float
    default: float
    step: float
    unit: str
    module: str  # 모듈 키 ("" = 공통 볼륨)


@dataclass(frozen=True)
class Preset:
    key: str
    name: str
    recipe: dict  # {모듈 키: {값 키: 기본값}} — 켜진 모듈과 이 목소리의 기본값
    quick: tuple = ()  # 기본 목소리 패널에 보여줄 핵심 슬라이더: ("모듈.값", "표시 이름")
    icon: str = "🎙️"
    color: str = "#6b7280"  # 카드 그라디언트 기준색
    category: str = "효과"
    description: str = ""
    volume: float = 1.0
    custom: bool = False

    @property
    def modules(self) -> list[str]:
        return [k for k in MODULE_ORDER if k in self.recipe]

    @property
    def all_params(self) -> list[Param]:
        params, stage = [], 0
        for mkey in self.modules:
            mod = MODULES_BY_KEY[mkey]
            overrides = self.recipe.get(mkey) or {}
            for mp in mod.params:
                params.append(Param(f"{mkey}.{mp.key}", mp.label, stage + mp.stage, mp.attr, mp.min, mp.max,
                                    float(overrides.get(mp.key, mp.default)), mp.step, mp.unit, mkey))
            stage += mod.size
        # 모든 목소리 끝에 붙는 공통 볼륨 (효과마다 소리 크기가 달라서)
        params.append(Param("volume", "볼륨", stage, "gain", 0.0, 2.0, self.volume, 0.05, "%", ""))
        return params

    @property
    def panel_params(self) -> list[Param]:
        """패널에 보여줄 슬라이더: 기본 목소리는 핵심만, 내 목소리는 전부."""
        if self.custom:
            return self.all_params
        by_key = {p.key: p for p in self.all_params}
        picked = [Param(**{**by_key[k].__dict__, "label": label}) for k, label in self.quick if k in by_key]
        return [*picked, by_key["volume"]]

    def values(self, saved: dict | None = None) -> dict[str, float]:
        saved = saved or {}
        return {p.key: float(saved.get(p.key, p.default)) for p in self.all_params}

    def build(self, saved: dict | None = None) -> list:
        """호출할 때마다 새 상태의 체인을 만든다."""
        chain = [stage for mkey in self.modules for stage in MODULES_BY_KEY[mkey].make()] + [Gain(1.0)]
        values = self.values(saved)
        for p in self.all_params:
            setattr(chain[p.stage], p.attr, values[p.key])
        return chain

    def param(self, key: str) -> Param | None:
        return next((p for p in self.all_params if p.key == key), None)


PITCH = ("pitch.semitones", "목소리 높이")
FORMANT = ("pitch.formant", "음색 (굵기)")

PRESETS: list[Preset] = [
    Preset("clean", "원본", {}, (), "🎙️", "#64748b", "기본", "효과 없이 내 목소리 그대로"),

    # ---------- 기본 ----------
    Preset("female", "여성", {"pitch": {"semitones": 4, "formant": 3}, "eq": {"high": 2}},
           (PITCH, FORMANT), "👩", "#ec4899", "기본", "높고 가벼운 여성 목소리"),
    Preset("male", "남성", {"pitch": {"semitones": -4, "formant": -3}, "eq": {"low": 3}},
           (PITCH, FORMANT), "👨", "#2563eb", "기본", "낮고 굵은 남성 목소리"),
    Preset("deep", "저음", {"pitch": {"semitones": -5, "formant": -3}, "eq": {"low": 4}},
           (PITCH, FORMANT, ("eq.low", "저음 강조")), "🐻", "#a16207", "기본", "굵고 낮은 목소리"),
    Preset("dj", "라디오 DJ", {
        "highpass": {"cutoff": 60}, "eq": {"low": 5, "mid_freq": 3000, "mid": 2, "high": 2},
        "compressor": {"threshold": -22, "ratio": 5}},
        (("eq.low", "저음 울림"), ("compressor.threshold", "압축 기준")), "🎧", "#eab308", "기본", "방송처럼 꽉 찬 목소리"),

    # ---------- 캐릭터 ----------
    Preset("chipmunk", "다람쥐", {"pitch": {"semitones": 7, "formant": 6}, "eq": {"high": -3}},
           (PITCH, FORMANT, ("eq.high", "고음")), "🐿️", "#f59e0b", "캐릭터", "높고 빠른 귀여운 목소리"),
    Preset("baby", "아기", {"pitch": {"semitones": 8, "formant": 9}, "lowpass": {"cutoff": 9000}},
           (PITCH, FORMANT), "👶", "#f9a8d4", "캐릭터", "작고 여린 아기 목소리"),
    Preset("helium", "헬륨", {"pitch": {"semitones": 12, "formant": 12}},
           (PITCH, FORMANT), "🎈", "#38bdf8", "캐릭터", "헬륨 가스 마신 목소리"),
    Preset("giant", "거인", {
        "pitch": {"semitones": -7, "formant": -8}, "eq": {"low": 4},
        "reverb": {"room": 0.8, "wet": 0.25, "dry": 0.9}},
        (PITCH, FORMANT, ("reverb.wet", "울림")), "🗿", "#78716c", "캐릭터", "거대한 몸에서 울리는 목소리"),
    Preset("monster", "괴물", {
        "pitch": {"semitones": -9, "formant": -6}, "distortion": {"drive": 12},
        "reverb": {"room": 0.4, "wet": 0.2, "dry": 0.8}},
        (PITCH, FORMANT, ("distortion.drive", "거칠기"), ("reverb.wet", "울림")),
        "👹", "#dc2626", "캐릭터", "거칠고 낮은 괴물 목소리", volume=0.6),
    Preset("demon", "악마", {
        "pitch": {"semitones": -12, "formant": -8}, "distortion": {"drive": 20}, "lowpass": {"cutoff": 4000},
        "reverb": {"room": 0.7, "wet": 0.3, "dry": 0.7}},
        (PITCH, FORMANT, ("distortion.drive", "거칠기"), ("reverb.wet", "울림")),
        "😈", "#9f1239", "캐릭터", "지옥에서 온 저음", volume=0.5),
    Preset("villain", "우주 악당", {
        "pitch": {"semitones": -4, "formant": -4}, "highpass": {"cutoff": 120}, "distortion": {"drive": 6},
        "chorus": {"rate": 0.3, "depth": 0.15, "mix": 0.3}, "reverb": {"room": 0.2, "wet": 0.12, "dry": 0.9},
        "compressor": {"threshold": -25, "ratio": 6}},
        (PITCH, ("distortion.drive", "숨소리 거칠기"), ("chorus.mix", "헬멧 울림")),
        "🦹", "#334155", "캐릭터", "마스크 너머의 묵직한 목소리", volume=0.8),
    Preset("robot", "로봇", {
        "ringmod": {"freq": 60, "mix": 0.8}, "chorus": {"rate": 0.5, "depth": 0.2, "mix": 0.5},
        "delay": {"time": 0.012, "feedback": 0.5, "mix": 0.4}},
        (("ringmod.freq", "금속 톤"), ("ringmod.mix", "기계음 강도"), ("delay.feedback", "공명")),
        "🤖", "#0ea5e9", "캐릭터", "금속성 기계 음성"),
    Preset("alien", "외계인", {
        "pitch": {"semitones": 4, "formant": 4}, "ringmod": {"freq": 180, "mix": 0.4},
        "chorus": {"rate": 3, "depth": 0.5, "mix": 0.6}},
        (PITCH, FORMANT, ("chorus.rate", "울렁임 속도"), ("chorus.depth", "울렁임 깊이")),
        "👽", "#22c55e", "캐릭터", "울렁거리는 우주인 목소리"),
    Preset("ghost", "유령", {
        "pitch": {"semitones": 2, "formant": 2}, "lowpass": {"cutoff": 6000},
        "chorus": {"rate": 0.8, "depth": 0.7, "mix": 0.6}, "delay": {"time": 0.3, "feedback": 0.45, "mix": 0.35},
        "reverb": {"room": 0.95, "wet": 0.5, "dry": 0.6}},
        (PITCH, ("delay.feedback", "메아리"), ("reverb.wet", "울림")), "👻", "#818cf8", "캐릭터", "으스스하게 퍼지는 목소리"),

    # ---------- 효과 ----------
    Preset("radio", "무전기", {
        "highpass": {"cutoff": 500}, "distortion": {"drive": 18}, "bitcrush": {"bits": 8}, "lowpass": {"cutoff": 3000}},
        (("distortion.drive", "지직거림"), ("bitcrush.bits", "음질 (비트)"), ("lowpass.cutoff", "고음 한계")),
        "📻", "#84cc16", "효과", "지직거리는 무전 통신", volume=0.4),
    Preset("phone", "전화", {
        "highpass": {"cutoff": 300}, "lowpass": {"cutoff": 3400}, "compressor": {"threshold": -20, "ratio": 4}},
        (("highpass.cutoff", "저음 자르기"), ("lowpass.cutoff", "고음 자르기")), "☎️", "#8b5cf6", "효과", "전화기 너머 목소리"),
    Preset("megaphone", "확성기", {
        "highpass": {"cutoff": 700}, "distortion": {"drive": 22}, "lowpass": {"cutoff": 4500},
        "compressor": {"threshold": -25, "ratio": 8}},
        (("distortion.drive", "찢어짐"), ("highpass.cutoff", "저음 자르기")), "📢", "#f97316", "효과", "시위 현장 메가폰",
        volume=0.5),
    Preset("underwater", "수중", {
        "lowpass": {"cutoff": 700}, "chorus": {"rate": 0.4, "depth": 0.8, "mix": 0.7},
        "phaser": {"rate": 0.3, "depth": 0.8, "mix": 0.4}, "reverb": {"room": 0.6, "wet": 0.3, "dry": 0.8}},
        (("lowpass.cutoff", "물 깊이 (낮을수록 깊게)"), ("chorus.rate", "물결 속도")), "🫧", "#0369a1", "효과",
        "물속에서 말하는 소리", volume=1.3),
    Preset("cave", "동굴", {
        "delay": {"time": 0.22, "feedback": 0.35, "mix": 0.3},
        "reverb": {"room": 0.9, "damping": 0.3, "wet": 0.35, "dry": 0.7}},
        (("delay.time", "메아리 간격"), ("delay.feedback", "메아리 반복"), ("reverb.room", "공간 크기"),
         ("reverb.wet", "울림 양")), "🦇", "#475569", "효과", "울리는 동굴 메아리"),
    Preset("stadium", "경기장", {
        "highpass": {"cutoff": 150}, "delay": {"time": 0.38, "feedback": 0.25, "mix": 0.25},
        "reverb": {"room": 1.0, "damping": 0.2, "wet": 0.45, "dry": 0.8}},
        (("delay.time", "메아리 간격"), ("reverb.wet", "울림 양")), "🏟️", "#16a34a", "효과", "넓은 경기장 장내 방송"),
    Preset("retro", "8비트", {"pitch": {"semitones": 3, "formant": 3}, "bitcrush": {"bits": 5}, "lowpass": {"cutoff": 7000}},
           (("bitcrush.bits", "음질 (비트)"), PITCH), "🕹️", "#a855f7", "효과", "옛날 게임기 속 목소리", volume=0.7),
]

PRESETS_BY_KEY = {p.key: p for p in PRESETS}


def custom_preset(spec: dict) -> Preset:
    """설정에 저장된 내 목소리 → Preset. spec: {key, name, icon, color, description, modules: [모듈 키]}"""
    modules = [m for m in spec.get("modules", []) if m in MODULES_BY_KEY]
    return Preset(spec["key"], spec.get("name") or "내 목소리", {m: {} for m in modules}, (),
                  spec.get("icon") or "🎛️", spec.get("color") or "#7c5cff", "내 목소리",
                  spec.get("description") or "내가 만든 목소리", custom=True)
