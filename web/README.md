# Instagram Reels Ranking Web Service

인스타그램 릴스 랭킹 및 통계 추적 웹 서비스입니다.

## 기능

- 조회수/좋아요 기준 랭킹 표시
- 릴스 카드 형태의 UI
- 클릭 시 통계 추적 히스토리 모달 표시
- 변화율 계산 및 표시

## 설정

### Node.js 설치 (필요한 경우)

macOS에서 Homebrew를 사용하여 설치:

```bash
brew install node
```

또는 [Node.js 공식 사이트](https://nodejs.org/)에서 LTS 버전을 다운로드하여 설치하세요.

설치 확인:
```bash
node --version
npm --version
```

### 환경 변수

`.env.local` 파일을 생성하고 다음 변수를 설정하세요:

```env
DB_HOST=ls-ecc3fe19a26beae8a5e6528c250e3ec4a1d7789a.cfeuyo6k6djb.ap-northeast-2.rds.amazonaws.com
DB_PORT=5432
DB_NAME=instagram_reels_scraper
DB_USER=dbmasteruser
DB_PASSWORD=OMDa{iNn6`Zymr&eKY_5<_Z9iNKu|KB|
DB_SSL=true
```

**참고**: AWS RDS 등 대부분의 클라우드 데이터베이스는 SSL 연결을 요구합니다. `DB_SSL=true`로 설정하거나 환경 변수를 생략하면 기본적으로 SSL이 활성화됩니다. 로컬 개발 환경에서만 `DB_SSL=false`로 설정하세요.

### 의존성 설치

```bash
cd web
npm install
# 또는
yarn install
```

### 개발 서버 실행

```bash
npm run dev
# 또는
yarn dev
```

브라우저에서 [http://localhost:3000](http://localhost:3000)을 열어 확인하세요.

## Vercel 배포

1. Vercel에 프로젝트를 연결합니다.
2. 환경 변수를 Vercel 대시보드에서 설정합니다.
3. 배포가 자동으로 진행됩니다.

### Vercel 환경 변수 설정

Vercel 대시보드 > Settings > Environment Variables에서 다음 변수를 추가하세요:

- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_SSL` (필요시)

