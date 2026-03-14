# 환경 변수 암호화 설정 요약

이 문서는 환경 변수 암호화 설정의 핵심 내용을 요약합니다.

## ✅ 완료된 설정

### 1. 자동 암호화 ✅

- **커밋 시 자동 암호화**: `.env` 파일을 커밋하면 자동으로 암호화되어 저장됩니다
- **Pre-commit hook**: 커밋 전에 암호화 여부를 자동으로 확인합니다
- **로컬에서는 평문**: 편집 시에는 평문으로 보이고, Git에 저장될 때만 암호화됩니다

### 2. 공유 키 지원 ✅

- **여러 프로젝트에서 동일한 키 사용 가능**
- 공유 키 위치:
  - macOS/Linux: `~/.git-crypt-shared-key`
  - Windows: `%USERPROFILE%\.git-crypt-shared-key`
- 신규 프로젝트 초기화 시 공유 키 자동 감지 및 사용

### 3. 신규 프로젝트 자동 설정 ✅

**초기화 스크립트 실행:**

```bash
# macOS/Linux
.workflow/init-new-project.sh <프로젝트-이름>

# Windows
.workflow\init-new-project.bat <프로젝트-이름>
```

**자동으로 설정되는 것들:**
- ✅ 맥도날드 워크플로우 디렉토리 구조
- ✅ git-crypt 환경 변수 암호화 설정
- ✅ .gitattributes 및 .gitignore 설정
- ✅ Git pre-commit hook (자동 암호화 확인)
- ✅ 공유 키 지원

### 4. 윈도우 지원 ✅

- Windows용 배치 스크립트 제공: `.workflow/init-new-project.bat`
- Git for Windows와 호환
- 동일한 기능 제공

## 📋 사용 방법

### 신규 프로젝트 시작

1. **프로젝트 디렉토리로 이동**
   ```bash
   cd ~/projects/my-new-project
   ```

2. **초기화 스크립트 실행**
   ```bash
   # macOS/Linux
   .workflow/init-new-project.sh my-new-project
   
   # Windows
   .workflow\init-new-project.bat my-new-project
   ```

3. **공유 키 사용 여부 선택**
   - 공유 키가 있으면 사용 여부를 물어봄
   - 없으면 새 키 생성 후 공유 키로 저장할지 물어봄

4. **.env 파일 생성 및 커밋**
   ```bash
   cp env.example .env
   # .env 편집
   git add -f .env .gitattributes
   git commit -m "Add encrypted .env"
   ```

### 기존 프로젝트에 공유 키 적용

```bash
# 1. 공유 키 생성 (첫 프로젝트에서)
git-crypt export-key ~/.git-crypt-shared-key

# 2. 다른 프로젝트에서 사용
cd /path/to/other-project
git-crypt unlock ~/.git-crypt-shared-key
```

### 다른 환경에서 클론

```bash
# 1. 저장소 클론
git clone <repository-url>
cd project-name

# 2. 공유 키로 복호화
git-crypt unlock ~/.git-crypt-shared-key

# 또는 프로젝트별 키
git-crypt unlock ~/git-crypt-backups/project-name-*.key
```

## 🔒 보안

### 자동 암호화 확인

Pre-commit hook이 자동으로 확인:
- `.env` 파일이 커밋될 때 암호화되었는지 확인
- 암호화되지 않았으면 커밋 거부

### 키 관리

- **공유 키 위치**: `~/.git-crypt-shared-key` (macOS/Linux) 또는 `%USERPROFILE%\.git-crypt-shared-key` (Windows)
- **백업 필수**: 키를 잃으면 복구 불가능
- **안전한 저장**: 1Password, Bitwarden 등에 저장

## 📚 관련 문서

- `.workflow/START_HERE.md` - 맥도날드 시스템 시작 가이드 (신규 프로젝트 초기화 포함)
- `.workflow/shared-key-guide.md` - 공유 키 사용 가이드
- `.git-crypt-setup.md` - git-crypt 기본 사용법
- `.workflow/env-secrets-management.md` - 환경 변수 암호화 방법 비교

## 🎯 핵심 포인트

1. **자동 암호화**: 커밋 시 자동으로 암호화됨
2. **공유 키**: 여러 프로젝트에서 동일한 키 사용 가능
3. **자동 설정**: 초기화 스크립트로 모든 설정 자동화
4. **크로스 플랫폼**: macOS, Linux, Windows 모두 지원

---

**이제 신규 프로젝트를 시작할 때 `.workflow/START_HERE.md`만 읽고 초기화 스크립트를 실행하면 모든 설정이 자동으로 완료됩니다!**

