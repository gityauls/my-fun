# CLAUDE.md — my-fun

## 프로젝트 개요
개인용 MP3·라디오 플레이어다. 알송 매뉴얼에서 고른 기능만 작게 만든다. 완성도가 충분해지면 데스크톱 캘린더(`C:\desktop_calendar_v2`, PyQt5)에 부속 부품으로 붙인다. 비상업 취미 프로젝트다.

## 근거 문서
- 로드맵과 진행 현황: `docs/개발로드맵.md`
- 기능 메뉴판: `docs/alsong_features.md` (매뉴얼 쪽별 요약: `docs/alsong_manual.md`)
- 단계 설계: `docs/stageN_design.md`, 구현 계획: `docs/superpowers/plans/`

## 원칙
- 알송의 코드, 아이콘, 이미지, 문구, 이름을 쓰지 않는다. 기능 아이디어만 참고한다.
- REA 분석은 구현이 막혔을 때만 한다. 가져오는 것은 동작 원리뿐이다.
- 광고, 통계, 외부 전송을 넣지 않는다. 라디오와 자동 태그는 사용자가 누를 때만 접속한다.
- 화면은 PyQt5로만 만든다(캘린더와 같은 프로세스). PySide6를 import하지 않는다.
- Python 3.13과 3.14 모두에서 돌아가야 한다.
- `core/`, `engine/`, `controller.py`는 Qt를 import하지 않는다.
- 자동 테스트는 실제 소리 장치를 쓰지 않는다(`FakeSink`). 실제 소리는 사용자가 확인한다.
- 화면 문구는 한국어로 쓴다.
- 화면을 바꿀 때는 시안 이미지를 먼저 보여주고 승인을 받는다.
- 캘린더 프로젝트(`C:\desktop_calendar_v2`)는 6단계 전까지 읽기만 한다.
- git은 로컬에서만 쓴다. GitHub에 올리지 않는다.

## 실행과 테스트
```bash
run.bat                                  # 실행 (콘솔 없음)
.venv\Scripts\python.exe -m funplayer    # 실행 (콘솔 로그 보기)
.venv\Scripts\python.exe -m pytest       # 테스트 (offscreen)
```
- 가상환경: `.venv` (Python 3.14, PyQt5 5.15.11). 1단계 계획의 첫 작업에서 만든다.
- 설정: `%APPDATA%\my-fun\settings.json`
- 로그: `%APPDATA%\my-fun\logs\funplayer.log`

## Token Optimization Rules
1. Trust files already read — do not re-read unless changed
2. No speculative tool calls — only read what's actually needed
3. Parallelize independent tool calls in a single message
4. Route output > 20 lines to subagents
5. Never restate what the user already said

## 세션 관리
- 작업 중간 (같은 작업 이어서): /compact
- 작업 전환 (새 작업 시작): /clear
