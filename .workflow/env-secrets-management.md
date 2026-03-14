# 환경 변수 암호화 관리 방법 비교

이 문서는 `.env` 파일을 Git에 안전하게 올리는 여러 방법을 비교합니다.

## 📊 방법 비교표

| 방법 | 난이도 | 팀 협업 | 자동화 | 보안 | 추천도 |
|------|-------|---------|--------|------|--------|
| **SOPS** | 중 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **git-crypt** | 쉬움 | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **transcrypt** | 쉬움 | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **direnv + SOPS** | 중 | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **환경 변수 서비스** | 쉬움 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

## 1. SOPS (Secrets OPerationS)

### ✅ 장점
- **엔터프라이즈급**: Mozilla에서 개발, CNCF 프로젝트
- **유연한 암호화**: Age, PGP, AWS KMS, GCP KMS 등 다양한 방식 지원
- **부분 암호화**: YAML/JSON에서 값만 암호화, 키는 평문 (diff 가능)
- **자동화 친화적**: CI/CD에서 쉽게 사용 가능
- **멀티 키 지원**: 여러 키로 암호화 가능 (백업 용이)

### ❌ 단점
- **설정 복잡도**: 초기 설정이 다소 복잡
- **외부 도구 필요**: SOPS 바이너리 설치 필요
- **개인 프로젝트 과함**: 간단한 프로젝트에는 오버엔지니어링일 수 있음
- **키 관리**: Age 키나 PGP 키를 안전하게 보관해야 함

### 💡 적합한 경우
- 팀 프로젝트
- CI/CD 파이프라인 사용
- 여러 환경(dev/staging/prod) 관리
- 엔터프라이즈 환경

---

## 2. git-crypt (추천: 개인/소규모 팀)

### ✅ 장점
- **간단함**: 설정이 매우 간단
- **투명한 사용**: Git 명령어와 동일하게 사용
- **자동 복호화**: `git clone` 후 자동으로 복호화 (키가 있으면)
- **부분 암호화**: `.gitattributes`로 특정 파일만 암호화
- **PGP 기반**: 표준 PGP 사용

### ❌ 단점
- **키 분배**: 팀원에게 키를 안전하게 전달해야 함
- **전체 파일 암호화**: 파일 단위 암호화 (diff는 암호화된 형태)
- **키 손실 위험**: 키를 잃으면 복구 불가

### 💡 적합한 경우
- **개인 프로젝트** ⭐⭐⭐⭐⭐
- 소규모 팀 (2-5명)
- 간단한 설정이 필요한 경우

### 사용법 (간단 예시)
```bash
# 설치
brew install git-crypt

# 초기화
git-crypt init

# .gitattributes에 추가
echo ".env filter=git-crypt diff=git-crypt" >> .gitattributes

# 암호화
git-crypt lock

# 복호화 (키가 있으면 자동)
git-crypt unlock
```

---

## 3. transcrypt

### ✅ 장점
- **간단함**: git-crypt보다 더 간단
- **자동화**: 스크립트로 자동 설정
- **투명한 사용**: Git 명령어와 동일

### ❌ 단점
- **활발한 개발 중단**: 최근 업데이트 적음
- **기능 제한적**: git-crypt보다 기능이 적음

### 💡 적합한 경우
- 매우 간단한 개인 프로젝트

---

## 4. direnv + SOPS (추천: 개발 편의성)

### ✅ 장점
- **자동 로드**: 디렉토리 진입 시 자동으로 환경 변수 로드
- **SOPS 통합**: SOPS로 암호화된 파일 자동 복호화
- **개발 편의성**: `.envrc` 파일로 관리

### ❌ 단점
- **direnv 설치 필요**: 추가 도구 필요
- **설정 복잡도**: SOPS + direnv 설정 필요

### 💡 적합한 경우
- 로컬 개발 환경 최적화가 중요한 경우
- 여러 프로젝트를 오가는 경우

---

## 5. 환경 변수 서비스 (1Password, Bitwarden 등)

### ✅ 장점
- **전문 서비스**: 보안 전문 서비스 활용
- **팀 협업**: 권한 관리 용이
- **자동 동기화**: 여러 기기에서 동기화
- **감사 로그**: 접근 기록 추적

### ❌ 단점
- **유료**: 대부분 유료 서비스
- **외부 의존**: 서비스 장애 시 영향
- **Git 통합 없음**: Git에 올릴 수 없음

### 💡 적합한 경우
- 팀 프로젝트
- 예산이 있는 경우
- 엔터프라이즈 환경

---

## 🎯 프로젝트별 추천

### 개인 프로젝트 (현재 프로젝트)
**추천: git-crypt** ⭐⭐⭐⭐⭐

이유:
- 설정이 가장 간단
- Git과 자연스럽게 통합
- 개인 프로젝트에 충분한 보안
- 유지보수 부담 적음

### 소규모 팀 (2-5명)
**추천: git-crypt 또는 SOPS**

- git-crypt: 간단함 우선
- SOPS: 더 많은 기능 필요 시

### 대규모 팀/엔터프라이즈
**추천: SOPS + KMS**

- AWS KMS, GCP KMS 등과 통합
- 권한 관리 용이
- 감사 로그 가능

---

## ⚠️ 공통 주의사항

### 1. 키 관리
- **절대 Git에 올리지 말 것**: 암호화 키는 Git에 올리면 안 됨
- **백업 필수**: 키를 잃으면 복구 불가
- **안전한 저장**: 1Password, Bitwarden 등에 저장

### 2. .gitignore 설정
```gitignore
# 평문 .env는 무시
.env
.env.local

# 암호화된 파일은 커밋
!.env.encrypted
```

### 3. README에 사용법 문서화
- 복호화 방법
- 키 설정 방법
- 새 팀원 온보딩 가이드

---

## 🔄 마이그레이션 가이드

### git-crypt로 전환하는 경우

1. **git-crypt 설치**
```bash
brew install git-crypt
```

2. **저장소 초기화**
```bash
git-crypt init
```

3. **.gitattributes 설정**
```bash
echo ".env filter=git-crypt diff=git-crypt" >> .gitattributes
```

4. **.env 파일 추가 및 커밋**
```bash
git add .env .gitattributes
git commit -m "Add encrypted .env file"
```

5. **키 내보내기 (안전한 곳에 보관)**
```bash
git-crypt export-key ~/git-crypt-key-backup
```

---

## 📚 참고 자료

- [SOPS 공식 문서](https://github.com/getsops/sops)
- [git-crypt 공식 문서](https://github.com/AGWA/git-crypt)
- [transcrypt 공식 문서](https://github.com/elasticdog/transcrypt)
- [direnv 공식 문서](https://direnv.net/)

