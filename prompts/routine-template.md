[변수]
- {SUBJECT}: 산업명(예: 조선)
- {SUBJECT_ID}: 영문 소문자 id(예: shipbuilding)
- {OBJECT}: 이 브리핑으로 얻고 싶은 투자 판단 근거

[산업 투자 관점]
- 핵심 체크포인트: 이 산업 주가를 움직이는 지표·사건 4~7개
- 주가 민감 이벤트:
- 대표 커버리지(참고): KR / US / GLOBAL

[수행]
- `prompts/routine-common.md` 를 읽고, 그 안의 {SUBJECT}·{SUBJECT_ID}·{OBJECT} 를 위 [변수] 값으로 바꿔서 그대로 수행함

※ 새 산업을 추가할 때: 이 파일 복사 → `config/industries.json` 에 {SUBJECT_ID} 항목(title·emoji·signal_fields) 추가 →
  `AGENTS.md` 에 `### {SUBJECT}` 뉴스사이트 추가 → `.github/workflows/publish.yml` 의 RECIPIENTS_{ID} 줄 추가 → 예약 작업 등록
