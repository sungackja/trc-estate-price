# Tiger Estate Price

서울 아파트 실거래가를 SQLite DB에 저장하고, 단지명 + 전용면적 기준 신고가 거래를 보여주는 초기 웹사이트입니다.

## 1. Install

```bash
pip install -r requirements.txt
```

## 2. Environment

`.env` 파일에 공공데이터포털 API 키를 넣습니다.

```bash
MOLIT_API_KEY=your_molit_api_key_here
```

`.env` 파일은 GitHub에 올리지 않습니다.

## 3. Collect Data

작게 테스트하려면 강남구 한 달만 수집합니다.

```bash
python collector.py --start 202403 --end 202403 --gu 11680
```

최근 8년치 서울 25개 구 전체를 수집하려면 아래처럼 실행합니다.

```bash
python collector.py
```

## 4. Run Website

```bash
python app.py
```

브라우저에서 `http://127.0.0.1:8000`을 엽니다.

## 5. Show Record Highs In Terminal

```bash
python show_records.py --limit 30
```

강남구만 보려면 아래처럼 실행합니다.

```bash
python show_records.py --gu 11680 --limit 30
```

## 6. Build Daily Image Site

아래 명령은 `public/index.html`과 `public/today-record-highs.svg`를 만듭니다.

```bash
python build_static_site.py
```

GitHub Pages에 올리면 이 `public` 폴더가 무료 정적 사이트가 됩니다.
