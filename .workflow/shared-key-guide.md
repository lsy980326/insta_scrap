# 공유 키 사용 가이드

여러 프로젝트에서 동일한 git-crypt 키를 사용하여 환경 변수를 암호화/복호화하는 방법입니다.

## 🎯 공유 키의 장점

- **일관성**: 모든 프로젝트에서 동일한 키 사용
- **편의성**: 키 관리가 간단함
- **자동화**: 신규 프로젝트 초기화 시 자동으로 키 적용 가능

## 📋 공유 키 설정 방법

### 1. 첫 번째 프로젝트에서 공유 키 생성

```bash
# 프로젝트에서 git-crypt 초기화 후
git-crypt export-key ~/.git-crypt-shared-key

# 또는 Windows
git-crypt export-key %USERPROFILE%\.git-crypt-shared-key
```

### 2. 공유 키 위치

- **macOS/Linux**: `~/.git-crypt-shared-key`
- **Windows**: `%USERPROFILE%\.git-crypt-shared-key`

### 3. 신규 프로젝트에서 공유 키 사용

#### 방법 1: 초기화 스크립트 사용 (권장)

```bash
# macOS/Linux
.workflow/init-new-project.sh my-project

# Windows
.workflow\init-new-project.bat my-project
```

스크립트가 공유 키를 자동으로 감지하고 사용 여부를 물어봅니다.

#### 방법 2: 수동 설정

```bash
# 1. Git 저장소 초기화
git init

# 2. 공유 키로 git-crypt 초기화
git-crypt unlock ~/.git-crypt-shared-key

# 3. .gitattributes 설정
echo ".env filter=git-crypt diff=git-crypt" >> .gitattributes
```

## 🔒 보안 주의사항

### ✅ 해야 할 것

1. **공유 키를 안전한 곳에 저장**
   - 1Password, Bitwarden 등 비밀번호 관리자
   - 암호화된 볼륨
   - 안전한 클라우드 스토리지 (암호화된 상태)

2. **키 파일 권한 설정** (macOS/Linux)
   ```bash
   chmod 600 ~/.git-crypt-shared-key
   ```

3. **키 백업**
   - 여러 곳에 백업
   - 키를 잃으면 모든 프로젝트의 암호화된 파일 복구 불가

### ❌ 하지 말아야 할 것

1. **Git에 키 파일 올리기**: 절대 금지!
2. **평문으로 공유**: 안전한 채널 사용
3. **공개 저장소에 키 노출**: 주의

## 🔄 기존 프로젝트에 공유 키 적용

### 기존 프로젝트의 키를 공유 키로 변경

```bash
# 1. 기존 키 내보내기
git-crypt export-key ~/.git-crypt-shared-key

# 2. 다른 프로젝트에서 사용
cd /path/to/other-project
git-crypt unlock ~/.git-crypt-shared-key
```

### 여러 프로젝트를 하나의 키로 통합

1. **주 프로젝트 선택**: 가장 중요한 프로젝트의 키를 공유 키로 사용
2. **다른 프로젝트 마이그레이션**:
   ```bash
   # 기존 프로젝트에서 키 내보내기
   git-crypt export-key /tmp/old-key.key
   
   # 새 공유 키로 재암호화
   git-crypt unlock ~/.git-crypt-shared-key
   git add -f .env
   git commit -m "Migrate to shared key"
   ```

## 💡 사용 예시

### 시나리오 1: 신규 프로젝트 시작

```bash
# 1. 프로젝트 디렉토리로 이동
cd ~/projects/my-new-project

# 2. 초기화 스크립트 실행
.workflow/init-new-project.sh my-new-project

# 3. 공유 키 사용 여부에 "y" 입력
# 4. .env 파일 생성 및 커밋
cp env.example .env
# .env 편집
git add -f .env .gitattributes
git commit -m "Add encrypted .env"
```

### 시나리오 2: 다른 기기에서 클론

```bash
# 1. 저장소 클론
git clone <repository-url>
cd project-name

# 2. 공유 키로 복호화
git-crypt unlock ~/.git-crypt-shared-key

# 3. .env 파일이 자동으로 복호화됨
```

## 🔧 문제 해결

### 공유 키가 작동하지 않는 경우

```bash
# 1. 키 파일 존재 확인
ls -la ~/.git-crypt-shared-key

# 2. 키 파일 권한 확인 (macOS/Linux)
chmod 600 ~/.git-crypt-shared-key

# 3. git-crypt 상태 확인
git-crypt status

# 4. 수동으로 unlock
git-crypt unlock ~/.git-crypt-shared-key
```

### 여러 키 관리

여러 공유 키를 사용하려면:

```bash
# 프로젝트별로 다른 키 사용
git-crypt unlock ~/.git-crypt-key-project1
# 또는
git-crypt unlock ~/.git-crypt-key-project2
```

## 📚 참고 자료

- [git-crypt 공식 문서](https://github.com/AGWA/git-crypt)
- `.git-crypt-setup.md` - git-crypt 기본 사용법
- `.workflow/init-new-project.sh` - 신규 프로젝트 초기화 스크립트

---

**중요**: 공유 키를 안전하게 보관하세요. 키를 잃으면 모든 프로젝트의 암호화된 파일을 복구할 수 없습니다!

