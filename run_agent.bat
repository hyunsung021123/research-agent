@echo off
REM ============================================================
REM  research_agent 일일 실행 (Windows 작업 스케줄러용)
REM
REM  1) 아래 키를 본인 키로 바꾸세요.
REM  2) 가상환경(.venv)을 쓰면 PYTHON 줄의 주석을 바꿔 .venv 쪽을 쓰세요.
REM  3) 작업 스케줄러 등록 (관리자 cmd):
REM       매일 오전 9시:
REM         schtasks /create /tn "ResearchAgent" /tr "%~dp0run_agent.bat" /sc daily /st 09:00
REM       매주 월요일 오전 9시:
REM         schtasks /create /tn "ResearchAgent" /tr "%~dp0run_agent.bat" /sc weekly /d MON /st 09:00
REM     해제:  schtasks /delete /tn "ResearchAgent" /f
REM     즉시 실행 테스트:  schtasks /run /tn "ResearchAgent"
REM
REM  주의: PC가 켜져 있을 때만 실행됩니다. 절전 중 놓친 작업을 깨어날 때
REM        실행하려면 작업 스케줄러 GUI에서 해당 작업 > 설정 >
REM        "예약 시간 놓친 경우 가능한 한 빨리 작업 시작"을 체크하세요.
REM ============================================================

cd /d "%~dp0"
set ANTHROPIC_API_KEY=sk-ant-여기에-본인키

REM 가상환경 미사용(시스템 python):
python run.py >> data\run.log 2>&1
REM 가상환경(.venv) 사용 시 위 줄 대신:
REM ".venv\Scripts\python.exe" run.py >> data\run.log 2>&1
