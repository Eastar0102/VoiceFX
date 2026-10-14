"""Windows 기본 녹음 장치 조회/변경.

Voicemod처럼 실행 중에는 가상 케이블을 기본 마이크로 바꿔서, 입력 장치가 "Default"로
되어 있는 Discord/게임이 설정 변경 없이 바로 변조된 목소리를 쓰게 한다.
기본 장치 변경은 문서화되지 않은 IPolicyConfig COM 인터페이스를 사용한다(Windows 7+).
"""
from __future__ import annotations

from ctypes import c_int, c_wchar_p

import comtypes
from comtypes import COMMETHOD, GUID, HRESULT, IUnknown
from pycaw.pycaw import AudioUtilities

E_CAPTURE = 1
E_ALL = 2
DEVICE_STATE_ACTIVE = 1
DEVICE_STATE_DISABLED = 2
ROLES = (0, 1, 2)  # eConsole, eMultimedia, eCommunications

CLSID_POLICY_CONFIG = GUID("{870af99c-171d-4f9e-af0d-e63df40c2bc9}")


class IPolicyConfig(IUnknown):
    _iid_ = GUID("{f8679f50-850a-41cf-9c72-430f290290c8}")
    # vtable 순서만 맞으면 되므로 쓰지 않는 메서드는 인자 없이 자리만 채운다
    _methods_ = [COMMETHOD([], HRESULT, name) for name in (
        "GetMixFormat", "GetDeviceFormat", "ResetDeviceFormat", "SetDeviceFormat",
        "GetProcessingPeriod", "SetProcessingPeriod", "GetShareMode", "SetShareMode",
        "GetPropertyValue", "SetPropertyValue",
    )] + [
        COMMETHOD([], HRESULT, "SetDefaultEndpoint",
                  (["in"], c_wchar_p, "device_id"), (["in"], c_int, "role")),
        # 소리 설정의 "사용/사용 안 함"과 같은 동작
        COMMETHOD([], HRESULT, "SetEndpointVisibility",
                  (["in"], c_wchar_p, "device_id"), (["in"], c_int, "visible")),
    ]


def _enumerator():
    comtypes.CoInitialize()
    return AudioUtilities.GetDeviceEnumerator()


def get_default_capture_id(role: int = 0) -> str | None:
    try:
        return _enumerator().GetDefaultAudioEndpoint(E_CAPTURE, role).GetId()
    except comtypes.COMError:
        return None


def get_default_capture_name() -> str | None:
    dev_id = get_default_capture_id()
    return next((name for i, name in list_capture_endpoints() if i == dev_id), None)


def list_capture_endpoints() -> list[tuple[str, str]]:
    """활성 녹음 장치 (id, 이름) 목록."""
    coll = _enumerator().EnumAudioEndpoints(E_CAPTURE, DEVICE_STATE_ACTIVE)
    result = []
    for i in range(coll.GetCount()):
        dev = coll.Item(i)
        result.append((dev.GetId(), AudioUtilities.CreateDevice(dev).FriendlyName))
    return result


def find_capture_endpoint(name_part: str) -> str | None:
    return next((i for i, name in list_capture_endpoints() if name_part.lower() in name.lower()), None)


def list_disabled_endpoints() -> list[tuple[str, str]]:
    """'사용 안 함' 상태인 재생/녹음 장치 (id, 이름) 목록."""
    coll = _enumerator().EnumAudioEndpoints(E_ALL, DEVICE_STATE_DISABLED)
    result = []
    for i in range(coll.GetCount()):
        dev = coll.Item(i)
        result.append((dev.GetId(), AudioUtilities.CreateDevice(dev).FriendlyName or ""))
    return result


def _policy():
    comtypes.CoInitialize()
    return comtypes.CoCreateInstance(CLSID_POLICY_CONFIG, IPolicyConfig, comtypes.CLSCTX_ALL)


def set_default_capture(device_id: str) -> None:
    policy = _policy()
    for role in ROLES:
        policy.SetDefaultEndpoint(device_id, role)


def set_endpoint_enabled(device_id: str, enabled: bool) -> None:
    _policy().SetEndpointVisibility(device_id, 1 if enabled else 0)
