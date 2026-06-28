# AI Research Agent — v2

매일 arXiv 신규 논문을 수집해, **연구 문제별 키워드 필터**로 거르고, Claude 로 관련도
평가·요약하여 **대시보드(웹 UI)** 와 **푸시 알림**으로 전달하는 도구. GitHub Actions +
Pages 로 올리면 **PC 가 꺼져 있어도 클라우드에서 자동 실행**되고, 폰·태블릿·PC 어디서나
URL 하나로 본다.

```
arXiv 수집 → 문제별 키워드 필터 → Claude 평가·요약 → 대시보드 + 알림 + 키워드 자동최적화
```

---

## 1. 빠른 시작 (로컬)

```bash
cd research_agent
python -m pip install -r requirements.txt        # 'python -m pip' 권장
cp config.example.yaml config.yaml               # 문제·키워드 수정
set ANTHROPIC_API_KEY=sk-ant-...                 # Windows cmd ($env:... 는 PowerShell)
python run.py --dry-run                           # API 비용 0, 평가 대상 미리보기
python run.py                                      # 수집→요약→docs/index.html 생성
```

`docs/index.html` 을 브라우저로 열면 대시보드가 뜬다.

## 2. 연구 문제 여러 개 (핵심)

`config.yaml` 의 `problems:` 에 문제를 원하는 만큼 둔다. 각 문제는 자기 `keywords` 와
`description` 을 갖는다. 논문은 **가장 잘 맞는 한 문제에 배정**되어 그 문제 기준으로
평가되고, 대시보드에서 문제별로 필터된다.

```yaml
problems:
  - id: "mcmullen"
    name: "McMullen's problem (d=5)"
    description: "convex position, acyclic reorientation, ..."
    keywords: ["mcmullen", "convex position", "oriented matroid", ...]
  - id: "matching-fields"
    name: "Polyhedral matching fields"
    description: "tropical, non-regular triangulation, realizability, ..."
    keywords: ["matching field", "tropical", "triangulation", ...]
```

## 3. 키워드 자동 최적화

각 문제의 키워드는 누적 데이터로 **스스로 개선**된다.

- 매 실행마다 문제별로 "고관련에 자주·저관련에 드물게" 나오는 **판별력 높은 후보**를
  뽑아 `data/keyword_review.md` 에 적는다(과대 키워드는 제거 후보로 플래깅).
- `learn.auto_apply: true` 로 두면 임계를 넘는 키워드를 **자동 적용**한다. 단 사람의
  `config.yaml` 은 안 건드리고 기계 소유 파일 `data/learned_keywords.json` 에 추가한다
  (로드 시 합쳐 씀). 그 파일만 비우면 초기화된다.
- 따로 돌리려면: `python learn_keywords.py` (LLM 호출 0).

키워드에 안 걸린 논문도 매 실행 일부를 저가 모델로 **탐색**(`arxiv.explore_sample`)해서,
놓친 논문을 회수하고 새 키워드 발견의 연료로 쓴다(대시보드에 "탐색 발견" 표시).

## 4. 완전 자동화 + 다기기 접속 (GitHub Actions + Pages) — 권장

PC 를 켜둘 필요 없이 클라우드에서 매일 돌고, 폰·태블릿·PC 어디서나 URL 로 본다.

1. **GitHub 저장소 생성** 후 이 폴더를 올린다 (이미 git 초기화+첫 커밋 돼 있음):
   ```bash
   git remote add origin https://github.com/<너>/research-agent.git
   git push -u origin main
   ```
2. **Secret 등록**: Settings → Secrets and variables → Actions → New secret →
   이름 `ANTHROPIC_API_KEY`, 값은 콘솔 키. (키는 절대 코드에 넣지 않는다.)
3. **Actions 켜기**: Actions 탭에서 활성화. `daily-research-digest` 가 매일 00:00 UTC
   (=09:00 KST) 자동 실행, "Run workflow" 로 즉시 실행도 됨. 시간 변경은
   `.github/workflows/daily.yml` 의 cron.
4. **Pages 켜기**: Settings → Pages → Source = `main` 브랜치 `/docs` 폴더. 잠시 후
   `https://<너>.github.io/research-agent/` 에서 대시보드가 열린다. 폰에서 그 URL 을
   홈 화면에 추가하면 앱처럼 쓴다("아침 뉴스"처럼).

워크플로는 결과(코퍼스·상태·대시보드)를 저장소에 다시 커밋해 상태를 유지한다.

> 무료 Pages 는 **공개 저장소**가 필요하다. 내용은 공개 arXiv 기반이라 민감도는 낮지만
> 연구 방향이 노출된다. 비공개로 하려면 Pages 유료 플랜이나 "휴대폰에서 보기"의
> 클라우드 동기화 방식을 쓴다. 또 GitHub 는 저장소가 60일 무활동이면 예약을
> 비활성화하고(커밋이 계속 생기면 보통 무관), cron 시각은 다소 지연될 수 있다.

## 5. 푸시 알림 (ntfy)

계정 없이 폰으로 푸시를 받는다.

1. 폰에 **ntfy 앱** 설치 → 추측 어려운 토픽 구독(예: `ra-choihs-x7k2q`).
2. `config.yaml` 의 `notify.enabled: true`, `ntfy_topic` 설정.
3. 실행 시 임계(`min_relevance`) 이상 새 논문이 있으면 상위 5편이 푸시로 온다.

다른 채널(텔레그램·이메일·웹푸시)은 `agent/notify.py` 에 함수를 추가해 확장한다.

## 6. 문제·키워드 편집

`config.yaml` 의 `problems:` 를 편집한다. 어디서나 하려면 **GitHub 의 config.yaml 을
웹에서 열어 편집·커밋**하면 폰에서도 된다. 다음 실행이 바로 반영. (전용 편집 UI 는
다음 단계 — 정적 Pages 는 쓰기가 안 되어 작은 백엔드나 GitHub API 연동이 필요하다.)

## 7. 코드 업데이트 (zip 재설치 없이)

git 으로 옮긴 뒤부터는 변경 파일만 교체하고 `git add/commit/push`. Actions 가 자동
재배포한다. 문제 생기면 `git revert` 로 롤백. 가상환경·config·secret 은 그대로 유지된다.

## 8. 로컬 스케줄 (Actions 대신 PC 에서)

PC 가 켜져 있을 때만 돈다.
- **Windows**: `run_agent.bat` 채운 뒤
  `schtasks /create /tn "ResearchAgent" /tr "C:\경로\run_agent.bat" /sc daily /st 09:00`
- **macOS**: `schedule/com.researchagent.daily.plist` + `launchctl load`.

## 파일 구조

```
research_agent/
├── run.py                  # 수집→평가→대시보드→알림→키워드최적화
├── learn_keywords.py       # 문제별 키워드 제안(검수용)
├── build_dashboard.py      # 코퍼스 → docs/index.html
├── run_agent.bat           # Windows 스케줄용
├── config.example.yaml     # 설정 템플릿
├── requirements.txt
├── .github/workflows/daily.yml   # 클라우드 자동 실행
├── schedule/               # macOS launchd 템플릿
├── agent/
│   ├── config.py           # 다중 문제 설정 + v1 자동변환 + 학습키워드 병합
│   ├── arxiv_source.py     # arXiv 수집
│   ├── prefilter.py        # 문제별 키워드 배정
│   ├── summarize.py        # Claude 평가·요약(환각 통제)
│   ├── keyword_learner.py  # 판별력 기반 키워드 학습
│   ├── notify.py           # ntfy 푸시(확장 지점)
│   ├── corpus.py           # 상태·코퍼스
│   ├── digest.py           # 마크다운 다이제스트
│   └── dashboard.py        # 웹 대시보드(문제 필터)
├── data/                   # corpus.jsonl, state.json, learned_keywords.json (자동)
├── digests/                # 날짜별 마크다운 (자동)
└── docs/index.html         # 대시보드 = Pages 가 서빙 (자동)
```
