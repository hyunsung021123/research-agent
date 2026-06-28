# AI Research Agent — v1 (문헌 수집·요약)

매일 arXiv 신규 논문을 수집해서, 키워드로 1차 거른 뒤, Claude로 관련도 평가·요약하여
마크다운 다이제스트로 떨궈주는 로컬 도구. 하이브리드 운영(매일 자동 수집 + 대화는 별도)의
**수집·요약 파이프라인** 부분이다.

## 동작 구조

```
arXiv 수집 → 키워드 사전필터 → Claude 평가·요약(논문당 1회) → 다이제스트 + 코퍼스 저장
   (전체)       (LLM 비용 통제)     (관련도/요약/기법/연결)        (digests/, data/corpus.jsonl)
```

- **사전필터**가 LLM 호출 대상을 키워드 매칭 논문으로 줄여 비용과 노이즈를 통제한다.
- **평가·요약**은 초록에 명시된 내용만 쓰도록 강제(환각 통제). 연결/착안점에서 모델의
  추론은 `추측:` 으로 명시된다.
- **중복 방지**: 한 번 본 논문 id는 `data/state.json`에 기록되어 다음 실행에서 건너뛴다.
- **코퍼스**(`data/corpus.jsonl`)는 평가된 논문을 누적 저장 — v2 벡터 검색 층의 입력.

## 설치

```bash
cd research_agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp config.example.yaml config.yaml      # 본인 연구에 맞게 수정
export ANTHROPIC_API_KEY="sk-ant-..."   # 또는 .env 사용
```

## 실행

```bash
# LLM 호출 없이, 무엇이 평가 대상인지 미리보기 (키워드 튜닝용 — API 비용 0)
python run.py --dry-run

# 실제 실행: 수집 → 요약 → digests/YYYY-MM-DD.md 생성
python run.py

# 이번 실행만 14일치 거슬러 조회
python run.py --lookback 14
```

처음 한두 번은 `--dry-run`으로 `config.yaml`의 `keywords`와 `categories`를 조정하길 권한다.
사전필터가 너무 빡빡하면(관련 논문 누락) 키워드를 넓히고, 너무 헐겁거나
`max_summarize` 상한에 자주 걸리면 좁혀라.

## 튜닝 포인트 (config.yaml)

- `profile.description` — **관련도 판정의 기준**. 구체적일수록 평가가 정확하다.
- `arxiv.keywords` — 1차 필터의 핵심 노브. 부분일치, 넉넉하게.
- `llm.model` — 평소 `claude-sonnet-4-6`, 깊은 요약 필요 시 `claude-opus-4-8`.
- `llm.relevance_threshold` — 다이제스트에 실릴 최소 관련도(0-10).
- `llm.max_summarize` — 1회 실행당 LLM 호출 상한(비용 가드).

## 매일 자동 수집 (하이브리드)

24시간 서버는 필요 없다. 로컬에서 하루 1회 스케줄만 걸면 된다. 단, **컴퓨터가 켜져
있을 때만** 돈다 — 꺼져 있거나 절전 중이면 그 시각엔 안 돈다.

**Windows — 작업 스케줄러.** `run_agent.bat` 의 키/경로를 채운 뒤, 관리자 cmd 에서:

```bat
REM 매일 오전 9시
schtasks /create /tn "ResearchAgent" /tr "C:\경로\research_agent\run_agent.bat" /sc daily /st 09:00
REM 매주 월요일 오전 9시
schtasks /create /tn "ResearchAgent" /tr "C:\경로\research_agent\run_agent.bat" /sc weekly /d MON /st 09:00
```

해제 `schtasks /delete /tn "ResearchAgent" /f` · 즉시 테스트 `schtasks /run /tn "ResearchAgent"`.
절전 중 놓친 회차를 깨어날 때 실행하려면 작업 스케줄러 GUI 에서 해당 작업 > 설정 >
"예약 시간 놓친 경우 가능한 한 빨리 작업 시작"을 체크.

**macOS — launchd.** `schedule/com.researchagent.daily.plist` 템플릿을 쓴다.
cron 과 달리, 예약 시각에 노트북이 잠들어 있었으면 **깨어날 때 놓친 1회를 실행**한다.
파일 안의 `__PATH__`/`__PYTHON__`/키를 채운 뒤:

```bash
cp schedule/com.researchagent.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.researchagent.daily.plist
```

- 시간 변경: plist 의 `Hour`/`Minute` 수정 (예: 아침 9시 = 9 / 0).
- 매주 월요일만: `StartCalendarInterval` 안에 `<key>Weekday</key><integer>1</integer>` 추가
  (0=일 … 6=토).

**cron 으로도 가능** (잠들어 있던 회차는 건너뜀):

```cron
0 9 * * *   cd /절대경로/research_agent && /절대경로/.venv/bin/python run.py >> data/run.log 2>&1   # 매일 9시
0 9 * * 1   ...                                                                                      # 매주 월 9시
```

`ANTHROPIC_API_KEY` 는 plist 의 `EnvironmentVariables` 에 넣거나, cron 이면 래퍼
스크립트에서 `export` 한다.

> 노트북이 자주 닫혀 있어 예약이 자주 빗나간다면, 작은 상시 VPS 로 옮기는 게 가장
> 확실하다(아래 "휴대폰" 참고). 그 경우 스케줄·대시보드 호스팅이 한 번에 해결된다.

## 대시보드 (브라우저 탭 UI)

`run.py` 는 매 실행 끝에 `dashboard.html` 을 갱신한다. 브라우저로 열면 관련도순 정렬,
검색, 최소 관련도 필터, "탐색 발견만" 보기, 초록 토글이 되는 독립 페이지가 뜬다
(서버 불필요, LaTeX 는 MathJax 로 렌더). 코퍼스만 따로 다시 그리려면:

```bash
python build_dashboard.py            # 전체
python build_dashboard.py --min 5    # 관련도 5+ 만
```

## 휴대폰에서 보기

대시보드는 단일 HTML 파일이라 **보기**는 폰으로 쉽게 옮긴다. 다만 **생성**(파이썬
파이프라인 실행)은 컴퓨터나 서버가 필요하다. 세 가지 방법:

1. **클라우드 폴더 동기화 (가장 쉬움, 무료).** `dashboard.html` 을 iCloud Drive /
   Google Drive / Dropbox 폴더에 두고(또는 `--out` 으로 그 경로 지정), 폰 앱·브라우저로
   연다. 컴퓨터가 돌 때마다 갱신되고 폰엔 동기화된 최신본이 보인다. 읽기 전용.
2. **상시 VPS 호스팅 (월 몇 달러).** 작은 리눅스 서버에 이 도구를 올려 cron 으로 돌리고
   `dashboard.html` 을 정적 호스팅하면, 노트북 상태와 무관하게 폰에서 URL 로 항상 최신본을
   본다. "노트북이 잠들어 예약이 빗나가는" 문제도 동시에 해결된다.
3. **GitHub Pages 등 정적 호스팅.** 매 실행 후 `dashboard.html` 을 푸시하면 공개 URL 로
   접근. (단 내용이 공개되니 민감하면 1·2 를 권장.)

네이티브 모바일 앱은 이 프로젝트 범위 밖이다 — 위 1~3 으로 충분히 폰에서 본다.

## 키워드 자기학습 (반자동)

키워드는 **제안 기반**으로 진화한다. 자동으로 config를 덮어쓰지 않고(드리프트 방지),
판별력 있는 후보를 검수 파일로 내놓아 사람이 승인한다.

```bash
python learn_keywords.py                 # data/keyword_review.md 생성 (LLM 호출 0)
python learn_keywords.py --llm-refine     # Claude로 후보 정제(호출 1회)
```

원리: 좋은 키워드는 "고관련 논문에 자주, 저관련 논문에 드물게" 나오는 항이다. 단순
빈출어가 아니라 고/저관련을 **가르는** 항(precision)만 고른다. 또한 매칭은 많은데 평균
관련도가 낮은 기존 키워드는 **제거 후보**로 플래깅한다.

### 필터 버블 주의 — 탐색(explore_sample)

키워드 매칭 논문만 보고 키워드를 늘리면, 이미 잡는 영역만 깊어질 뿐 **놓치는 논문은
영영 못 찾는다**(필터 버블). 이를 깨려면 `config.yaml`의 `arxiv.explore_sample`을 켜라.
매 실행마다 키워드 비매칭 논문 중 일부를 저가 모델(`explore_model`, 기본 Haiku)로
빠르게 평가한다. 거기서 높게 나온 논문은

1. 다이제스트에 "💡 탐색 발견"으로 바로 표시되고(놓칠 뻔한 논문 회수),
2. 코퍼스에 쌓여 `learn_keywords.py`가 **진짜 새 키워드**를 발견하는 연료가 된다.

권장: `explore_sample: 12` 정도로 시작. 비용은 Haiku 호출 12회/실행 수준.

## 파일 구조

```
research_agent/
├── run.py                  # 수집→요약→대시보드 파이프라인 CLI
├── learn_keywords.py       # 키워드 자기학습(제안) CLI
├── build_dashboard.py      # 코퍼스 → dashboard.html 생성 CLI
├── config.example.yaml     # 설정 템플릿(복사해서 config.yaml로)
├── requirements.txt
├── schedule/
│   └── com.researchagent.daily.plist   # macOS launchd 스케줄 템플릿
├── agent/
│   ├── config.py           # 설정 로딩
│   ├── arxiv_source.py     # arXiv 수집
│   ├── prefilter.py        # 키워드 1차 필터
│   ├── summarize.py        # Claude 평가·요약(환각 통제)
│   ├── keyword_learner.py  # 판별력 기반 키워드 제안 + 과대 키워드 플래깅
│   ├── corpus.py           # 상태·코퍼스 저장
│   ├── digest.py           # 마크다운 다이제스트 렌더링
│   └── dashboard.py        # 상호작용 HTML 대시보드 렌더링
├── data/                   # state.json, corpus.jsonl, keyword_review.md (자동 생성)
├── digests/                # 날짜별 마크다운 다이제스트 (자동 생성)
└── dashboard.html          # 브라우저용 대시보드 (자동 생성)
```

## 알려진 한계 (v1)

- 키워드 사전필터는 **재현율 한계**가 있다. 키워드로 표현되지 않은 관련 논문은 놓칠 수 있다.
  v2의 시드 논문 기반 의미검색(벡터 스토어)으로 보완 예정.
- 관련도·요약은 **초록만** 본다. 본문 전체 분석은 후속 단계.
- `seed_authors`는 설정에만 있고 v1 파이프라인에서는 아직 사용하지 않는다(확장 지점).
