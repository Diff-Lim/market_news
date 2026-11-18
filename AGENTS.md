# market_news — 산업별 주식 투자 브리핑

매일 아침 6개 산업(AI, 바이오·헬스, 에너지, 반도체, 보안, 로봇)의 최근 24시간 뉴스와 관련 공시를 모아, **투자 관점**(관련 종목, 호재/악재, 영향 기간, 산업 특화 시그널)으로 정리해 메일로 보내요.

- 정기 실행: `prompts/routine-{산업}.md` (절차는 `prompts/routine-common.md` 하나에 있음)
- 발송: 데이터 JSON을 GitHub에 푸시하면 **GitHub Actions**(`.github/workflows/publish.yml`)가 공시·시세를 보강하고, HTML을 만들어 메일을 보내요. 에이전트는 메일을 직접 보내지 않아요.

## 공통 소스 (모든 산업)

### 국내 경제·증권
- 한국경제: https://www.hankyung.com
- 매일경제: https://www.mk.co.kr
- 이데일리: https://www.edaily.co.kr
- 머니투데이: https://www.mt.co.kr
- 연합뉴스 경제: https://www.yna.co.kr/economy

### 해외 경제·증권
- Reuters: https://www.reuters.com
- CNBC: https://www.cnbc.com
- MarketWatch: https://www.marketwatch.com
- Yahoo Finance: https://finance.yahoo.com
- Nikkei Asia: https://asia.nikkei.com

### 공시
- DART 전자공시(국내): https://dart.fss.or.kr  (OpenDART 커넥터가 있으면 커넥터 우선)
- KIND 한국거래소 공시: https://kind.krx.co.kr
- SEC EDGAR(미국): https://www.sec.gov/edgar/search/

## 산업별 뉴스사이트

### AI
- 국내:
  - AI Times: https://www.aitimes.com
  - 지디넷코리아: https://zdnet.co.kr
  - 전자신문: https://www.etnews.com
- 해외:
  - TechCrunch: https://techcrunch.com/category/artificial-intelligence
  - VentureBeat: https://venturebeat.com/category/ai/
  - The Information: https://www.theinformation.com
  - CNBC Tech: https://www.cnbc.com/technology/

### 바이오·헬스
- 국내:
  - 히트뉴스: https://www.hitnews.co.kr
  - 더바이오: https://www.thebionews.net
  - 바이오스펙테이터: https://www.biospectator.com
  - 팜이데일리: https://pharm.edaily.co.kr
- 해외:
  - STAT News: https://www.statnews.com
  - BioPharma Dive: https://www.biopharmadive.com
  - Fierce Biotech: https://www.fiercebiotech.com
  - Endpoints News: https://endpts.com
  - FDA 보도자료: https://www.fda.gov/news-events/fda-newsroom/press-announcements

### 에너지
- 국내:
  - 에너지경제: https://www.ekn.kr
  - 전기신문: https://www.electimes.com
  - 이투뉴스: https://www.e2news.com
- 해외:
  - Utility Dive: https://www.utilitydive.com
  - Canary Media: https://www.canarymedia.com
  - Energy-Storage.news: https://www.energy-storage.news
  - World Nuclear News: https://www.world-nuclear-news.org
  - OilPrice.com: https://oilprice.com

### 반도체
- 국내:
  - 디일렉: https://www.thelec.kr
  - 전자신문 반도체: https://www.etnews.com/news/section.html?id1=06
  - 디지털데일리: https://www.ddaily.co.kr
- 해외:
  - SemiEngineering: https://semiengineering.com
  - DIGITIMES: https://www.digitimes.com
  - EE Times: https://www.eetimes.com
  - TrendForce: https://www.trendforce.com/news/

### 보안
- 국내:
  - 보안뉴스: https://www.boannews.com
  - 데일리시큐: https://www.dailysecu.com
  - 데이터넷: https://www.datanet.co.kr
- 해외:
  - The Record: https://therecord.media
  - SecurityWeek: https://www.securityweek.com
  - BleepingComputer: https://www.bleepingcomputer.com
  - The Hacker News: https://thehackernews.com

### 로봇
- 국내:
  - 로봇신문: https://www.irobotnews.com
  - 헬로티: https://www.hellot.net
  - 전자신문: https://www.etnews.com
- 해외:
  - The Robot Report: https://www.therobotreport.com
  - IEEE Spectrum Robotics: https://spectrum.ieee.org/topic/robotics/
  - TechCrunch Robotics: https://techcrunch.com/category/robotics/

## Lessons Learned
(운영하면서 생긴 규칙을 여기에 한 줄씩 추가)
