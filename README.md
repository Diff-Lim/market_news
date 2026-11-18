# market_news — 산업별 주식 투자 브리핑

매일 아침 한국 장 시작 전에 **AI · 바이오·헬스 · 에너지 · 반도체 · 보안 · 로봇** 6개 산업의 최근 24시간 뉴스와 공시를 모아, 투자 관점으로 정리한 브리핑을 메일로 받는 저장소예요.

- 기사마다 **관련 종목(국내·미국·글로벌)**, **호재/악재**, **영향 기간(단기·중기·장기)**, **중요도(★1~3)**, **💡 투자 포인트**, **산업 특화 시그널**을 붙여요.
- 오늘의 투자 포인트, 핵심 뉴스, 오늘 언급된 종목표(직전 거래일 등락률), 관심종목 체크, **관련 공시(DART·SEC)**, 다가오는 일정, 요청 답변이 함께 들어가요.
- 미리보기: [`examples/sample_semiconductor.html`](examples/sample_semiconductor.html)

## 동작 구조 (노트북이 꺼져 있어도 돌아가요)

```
[Claude 예약 작업 — Anthropic 클라우드, 매일 06시대]
   prompts/routine-{산업}.md 수행
   → 뉴스 수집·분석 → data/{산업}/YYYYMMDD_HHMM.json 작성·검증 → git push
                                   │
                                   ▼
[GitHub Actions — publish.yml, 푸시되면 자동 실행]
   enrich_data.py   : 언급·관심 종목의 최근 공시(OpenDART, SEC EDGAR) + 등락률 보강
   generate_newsletter.py : HTML 생성 → newsletters/{산업}/ 에 커밋
   generate_newsletter.py --send : Gmail SMTP 로 메일 발송 (Secrets 사용)
```

- **수집·분석**은 Claude가 클라우드에서 해요. 내 컴퓨터가 꺼져 있어도 실행돼요.
- **메일 발송·공시 조회**는 GitHub Actions가 해요. 비밀번호·API 키는 GitHub Secrets에만 저장되고 저장소에는 남지 않아요.

## 처음 한 번만 설정

### 1. Claude GitHub 앱 권한
https://github.com/apps/claude/installations/select_target 에서 Diff-Lim 계정을 고르고 `market_news` 저장소 접근을 허용해요. 예약 작업이 데이터를 푸시하려면 이 권한이 필요해요.

### 2. GitHub Secrets 등록
저장소 → **Settings → Secrets and variables → Actions → New repository secret**

| 이름 | 값 | 필수 |
|---|---|---|
| `SMTP_USER` | 보내는 Gmail 주소 | ✅ |
| `SMTP_PASSWORD` | Gmail 앱 비밀번호 16자리 ([만들기](https://myaccount.google.com/apppasswords)) | ✅ |
| `RECIPIENTS` | 모든 산업을 받을 주소(줄바꿈 또는 쉼표 구분) | ✅ |
| `RECIPIENTS_AI` · `_BIO` · `_ENERGY` · `_SEMICONDUCTOR` · `_SECURITY` · `_ROBOT` | 그 산업만 추가로 받을 주소 | 선택 |
| `DART_API_KEY` | OpenDART 인증키 ([무료 발급](https://opendart.fss.or.kr/uss/umt/EgovMberInsertView.do)) — 국내 공시 자동 첨부 | 권장 |
| `SEC_USER_AGENT` | `market_news 내이메일@example.com` — SEC가 요구하는 연락처 | 권장 |
| `SMTP_SERVER`, `SMTP_PORT` | 기본값 smtp.gmail.com / 587 이면 생략 | 선택 |

### 3. Actions 쓰기 권한 확인
**Settings → Actions → General → Workflow permissions** 가 *Read and write permissions* 인지 확인해요. (Actions가 만든 HTML을 커밋해야 해요.)

### 4. 예약 작업
Claude 예약 작업 6개가 매일 아래 시각(KST)에 클라우드에서 실행돼요. 미국 장 마감 뒤, 한국 장 시작 전이에요.

| 산업 | 시각 | 프롬프트 |
|---|---|---|
| AI | 06:13 | `prompts/routine-ai.md` |
| 반도체 | 06:23 | `prompts/routine-semiconductor.md` |
| 바이오·헬스 | 06:33 | `prompts/routine-bio.md` |
| 에너지 | 06:43 | `prompts/routine-energy.md` |
| 보안 | 06:53 | `prompts/routine-security.md` |
| 로봇 | 07:03 | `prompts/routine-robot.md` |

시각을 바꾸거나 잠시 멈추려면 Claude 앱의 예약 작업 목록에서 고치면 돼요. 지금 바로 한 번 보고 싶으면 그 작업의 "지금 실행"을 눌러요.

## 원할 때 내용 추가하기

| 하고 싶은 것 | 방법 |
|---|---|
| 다음 호에 특정 질문·주제를 다뤄 달라 | `requests/inbox.md` 의 해당 산업(또는 `## 공통`) 아래에 `- [ ] 요청` 한 줄 추가. 다음 발행 때 "📮 요청하신 내용"에 답이 실리고 `[x]`로 바뀌어요 |
| 보유·관심 종목을 매일 챙겨 달라 | `config/watchlist.json` 의 `tickers` 에 추가(국내 6자리 코드 / 미국 티커 / 해외 현지 티커). 관련 뉴스는 "⭐ 내 관심종목 체크"에, 공시·등락률은 자동으로 붙어요 |
| 특정 키워드를 계속 추적 | `config/watchlist.json` 의 `keywords` 에 추가 |
| 산업별로 보는 지표를 바꾸고 싶다 | `config/industries.json` 의 `signal_fields`, 각 `prompts/routine-{산업}.md` 의 `[산업 투자 관점]` 수정 |
| 지금 당장 한 번 더 받기 | 예약 작업의 "지금 실행" (요청을 함께 주고 싶으면 inbox.md 에 먼저 적기) |
| 이미 만든 호를 다시 발송 | GitHub → Actions → publish → Run workflow 에 `data/ai/20261118_0613.json` 입력 |

GitHub 모바일 앱에서도 파일을 열어 연필(✏️) 버튼으로 바로 고칠 수 있어요.

## 폴더 구조

```
prompts/
  routine-common.md          # 수집·분석·저장·푸시 공통 절차 (절차는 여기만 고침)
  routine-{산업}.md          # 변수 + 산업 투자 관점(체크포인트·민감 이벤트·대표 종목)
  routine-template.md        # 새 산업 추가용
config/
  industries.json            # 산업별 제목·이모지·특화 시그널 항목
  watchlist.json             # 관심종목·키워드
requests/inbox.md            # 요청함
data/{산업}/                 # categories.json + 호별 데이터 JSON (Actions 가 enriched 추가)
newsletters/{산업}/          # Actions 가 만든 HTML
templates/newsletter.html    # 메일 디자인
scripts/
  validate_data.py           # 데이터 검증 (에이전트가 푸시 전에 실행)
  enrich_data.py             # 공시(DART·SEC)·등락률 보강 (Actions)
  generate_newsletter.py     # HTML 생성·발송
  email_sender.py            # SMTP 발송
.github/workflows/publish.yml
```

## 로컬에서 실행하고 싶을 때
```bash
pip install -r scripts/requirements.txt
python scripts/validate_data.py data/ai/20261118_0613.json
python scripts/generate_newsletter.py data/ai/20261118_0613.json -o /tmp/preview.html
```
로컬에서도 메일은 직접 보내지 않고, 푸시해서 Actions가 보내게 해요(중복 발송 방지).

## 유의사항
- 이 브리핑은 공개 뉴스·공시를 정리한 참고 자료이고 투자 권유가 아니에요.
- 등락률은 Yahoo Finance 비공식 API로 가져와요. 실패하면 "-"로 표시되고 나머지는 정상 발송돼요.
- 종목코드는 에이전트가 확인해서 넣지만, DART 조회에서 코드가 맞지 않으면 Actions 로그에 "DART 기업코드 없음"으로 남아요.
