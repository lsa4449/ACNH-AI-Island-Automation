# 구현 가능성 검토 및 오픈소스 분석

작성일: 2026-11-10 · 대상: Phase 1 착수 시점

표기: **[확인]** 공식 문서/저장소에서 직접 확인 · **[미확인]** 문서에서 확인하지 못함(가정 금지, 검증 필요)

## 1. 오픈소스 분석

| 항목 | NintendoSwitchAutomator (Kojiro20) | Pokémon Automation (Computer Control) |
|---|---|---|
| 구조·스택 | [확인] C 펌웨어 + LUFA 서브모듈. `Joystick.c`, `Descriptors.c`, `scripts/runner.c`. snowball-thrower / Switch-Fightstick 계열 포크 | [확인] 소스는 `PokemonAutomation/Arduino-Source` (`SerialPrograms/`, `Common/`), C++ 데스크톱 앱 + 마이크로컨트롤러 펌웨어(PABotBase2, C++) |
| Switch 모델 | [미확인] 명시 없음 | [확인] Switch 1, Switch 2 지원, Lite 불가(HDMI 출력 없음). [미확인] OLED는 별도 언급 없음 |
| MCU·펌웨어 | [확인] Arduino Micro(ATmega32u4), Teensy 2.0++, Arduino UNO R3. ESP32 계열 없음 | [확인] ESP32-S3(유선), ESP32/Pico W(무선), RP2040 계열. AVR 계열은 지원 종료 |
| Windows | [확인] 빌드용 안내만 존재(GnuWin Make + AVR 툴체인) | [확인] Windows 10 이상 x64가 주 플랫폼 |
| 입력 전송 | [확인] MCU가 USB 컨트롤러로 동작. 스크립트를 펌웨어에 넣고 보드 버튼으로 선택. PC 실시간 제어 없음 | [확인] PC → 시리얼(COM, "Serial: PABotBase2") → ESP32-S3 → USB로 유선 프로 컨트롤러 에뮬레이션 |
| Python 연동 | [확인] 없음(`bin2c.py`, `png2c.py`는 빌드 보조) | [미확인] Python API·공개 프로토콜 문서를 찾지 못함 |
| 캡처·영상 인식 | [확인] 없음 | [확인] 캡처보드 영상 입력 사용(최소 1080p30, 1080p60 권장). 인식 로직은 포켓몬 게임 전용 |
| 라이선스 | [확인] `LUFA_LICENSE` 파일 존재. [미확인] 저장소 자체 라이선스 전문 | [확인] Arduino-Source README: 소스는 MIT(일부 예외). 사이트: 개인 사용 무료, 영리 사용 금지 |
| 재사용 가능 | 직접 재사용 없음. 고정 매크로 구조 참고용 | ESP32-S3 펌웨어 바이너리, 하드웨어 구성/설치 절차, 캡처보드 요건 |
| 새로 개발 | 전부 | 모동숲 인식·좌표계·상태 머신·설계/계획 전체, Python 측 컨트롤러 어댑터 |

결론: NintendoSwitchAutomator는 AVR 전용 오프라인 매크로라 ESP32-S3 + PC 피드백 제어라는 본 프로젝트 구조와 맞지 않는다. 하드웨어 계층은 Pokémon Automation의 ESP32-S3 구성을 따른다.

### 기존 프로젝트 수정 vs 별도 Python 어댑터

| | PA 앱(C++)에 모동숲 프로그램 추가 | 별도 Python 어댑터 (추천) |
|---|---|---|
| 장점 | 검증된 입력·캡처 파이프라인 그대로 사용 | 요구 스택(Python/FastAPI/OpenCV) 유지, 테스트 쉬움, 업스트림 변경 영향 작음 |
| 단점 | 대형 C++ 코드베이스(6,700+ 커밋) 빌드·추적 부담, Python 스택 포기 | 시리얼 프로토콜을 직접 구현해야 함 |

추천: `ControllerAdapter` 뒤에 Python 어댑터를 둔다. 프로토콜 확보 방법은 Phase 2 첫 작업으로 결정한다.
1. (우선) Arduino-Source의 PABotBase2 클라이언트 코드를 읽고 필요한 최소 메시지만 Python(pyserial)으로 포팅. MIT 범위인지 파일별 확인 필요.
2. (대안) ESP32-S3용 자체 소형 펌웨어(USB HID + 단순 시리얼 명령). 후보 컴포넌트: Espressif 레지스트리의 `espp/switch_pro` — [미확인] 동작 검증 안 됨.
3. (후보) `shinyypig/pynscontroller` 등 Python 기반 프로젝트 — [미확인] 지원 보드·Windows 호환 미검토.

## 2. 하드웨어 연결 방식 (잠정 결정)

```
Switch OLED ─(독 HDMI)─> HDMI 캡처보드(UVC) ─USB─> Windows PC (OpenCV)
Switch 독 USB <─USB─ ESP32-S3 [USB/OTG 포트]
Windows PC  ─USB─> ESP32-S3 [COM/UART 포트]  (시리얼)
```

| 장비 | 요건 | PA 문서 기준 가격 | 상태 |
|---|---|---|---|
| ESP32-S3 개발보드 | [확인] USB 포트 2개짜리만 가능(USB/OTG → Switch, COM/UART → PC). 핀 없는 보드 권장 | 약 $10~15 | 구매 후보 |
| HDMI USB 캡처보드 | [확인] 1080p30 이상, 1080p60 권장. 저가형 대부분 동작, 초저가 4K60은 비권장 | 약 $10~20 | 구매 후보 |
| USB 데이터 케이블 2개 | [확인] 충전 전용 불가 | – | 구매 후보 |
| HDMI 패스스루 | TV로 동시에 볼 때만 필요 | – | 선택 |

- [확인] Switch 설정에서 "Pro 컨트롤러 유선 통신"을 켜야 한다. 플래시는 Espressif Flash Download Tool, 460800 baud.
- 예상 합계는 5만 원 안팎으로 20만 원 예산 안쪽이다. 단, **국내 판매가와 재고는 조사하지 않았다.**
- 구매 전 확인할 것: (1) OLED 독에서의 동작 사례 [미확인], (2) 보드 상품이 실제 2포트 S3인지, (3) 캡처보드의 실제 1080p 프레임레이트(표기와 다른 제품이 많음), (4) Python에서 쓸 프로토콜 확보 방법.
- 요구사항 문서의 예산 표기가 2장(20만~50만 원)과 6장(20만 원 이하)에서 다르다. 여기서는 더 엄격한 20만 원 이하를 기준으로 했다.

## 3. 기능별 구현 가능성

| 기능 | 판단 | 근거·위험 |
|---|---|---|
| AI 설계(JSON) + 규칙 검증 | 가능 (Phase 1 구현) | LLM 제안을 검증기가 걸러냄. 소형 로컬 모델의 좌표 품질은 낮을 수 있음 |
| 화면 캡처 + 버튼 전송 | 가능성 높음 | PA가 동일 구성으로 운용 중. Python 프로토콜 확보가 관건 |
| 캐릭터 위치 추정 | 어려움 | 카메라가 캐릭터를 따라가므로 화면만으로 절대 좌표를 알기 어렵다. 미니맵/지도 마커 활용안은 검증 필요 |
| 타일 단위 이동 | 중간 | 아날로그 이동은 오차 누적. 한 칸씩 이동 후 재관찰하는 폐루프 필수 |
| 꽃·묘목·가구·길 | 중간 | 메뉴 조작은 결정적이지만 인벤토리 상태 인식, 설치 결과 검증 필요 |
| 강·절벽 공사 | 중간~어려움 | 섬 크리에이터 권한 필요, 선행 순서와 경로 차단 문제 |
| 건물 이전·다리·경사로·날짜 경과 | 자동화 제외 | 주민 대화, 비용, 하루 경과가 필요 → 사용자 개입 작업으로 분류 |
| 섬 전체 무인 시공 | 현재 불가 | 아이템 보충, 주민·이벤트 끼어들기, 장시간 누적 오차. Phase 5의 목표이지 확보된 기능이 아님 |

## 4. Phase 1에서 단순화한 게임 규칙 (실기 검증 필요)

- 나무: 8방향 1칸 이내에 다른 나무·통과 불가 가구·물·절벽·건물이 없어야 한다고 가정.
- 꽃·나무는 잔디에만, 가구는 잔디·모래·길 위에 가능하다고 가정. 길은 잔디에만.
- 가구 크기는 시드 카탈로그 10종만 수록. 실제 크기 데이터는 커뮤니티 데이터셋으로 교체 예정.
- 한 칸 이동 250ms, 방향 전환 80ms, 설치 = A 버튼은 **자리표시자**이며 실측값이 아니다.

## 출처

- https://github.com/Kojiro20/NintendoSwitchAutomator
- https://pokemonautomation.github.io/
- https://pokemonautomation.github.io/SetupGuide/index.html
- https://pokemonautomation.github.io/SetupGuide/Controllers/Controller-ESP32-S3
- https://pokemonautomation.github.io/ControllerList.html
- https://pokemonautomation.github.io/FAQ.html
- https://github.com/PokemonAutomation/Arduino-Source
- https://github.com/PokemonAutomation/ComputerControl
