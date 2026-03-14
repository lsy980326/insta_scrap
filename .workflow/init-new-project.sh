#!/bin/bash

# 신규 프로젝트 초기화 스크립트
# 맥도날드식 워크플로우 + git-crypt 환경 변수 암호화 자동 설정

set -e

echo "🚀 신규 프로젝트 초기화 스크립트"
echo "=================================="
echo ""

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 프로젝트 이름 확인
if [ -z "$1" ]; then
    echo -e "${YELLOW}사용법: $0 <프로젝트-이름>${NC}"
    echo ""
    echo "예시:"
    echo "  $0 my-new-project"
    exit 1
fi

PROJECT_NAME="$1"
PROJECT_DIR="$(pwd)"

echo -e "${BLUE}프로젝트 이름:${NC} $PROJECT_NAME"
echo -e "${BLUE}프로젝트 디렉토리:${NC} $PROJECT_DIR"
echo ""

# 1. Git 저장소 확인
if [ ! -d ".git" ]; then
    echo -e "${YELLOW}⚠️  Git 저장소가 초기화되지 않았습니다.${NC}"
    read -p "Git 저장소를 초기화하시겠습니까? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git init
        echo -e "${GREEN}✅ Git 저장소 초기화 완료${NC}"
    else
        echo -e "${RED}❌ Git 저장소가 필요합니다.${NC}"
        exit 1
    fi
fi

# 2. git-crypt 설치 확인
if ! command -v git-crypt &> /dev/null; then
    echo -e "${YELLOW}📦 git-crypt 설치 중...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v brew &> /dev/null; then
            brew install git-crypt
        else
            echo -e "${RED}❌ Homebrew가 설치되어 있지 않습니다.${NC}"
            echo "   Homebrew 설치: https://brew.sh"
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y git-crypt
        elif command -v yum &> /dev/null; then
            sudo yum install -y git-crypt
        else
            echo -e "${RED}❌ 패키지 매니저를 찾을 수 없습니다.${NC}"
            echo "   수동 설치: https://github.com/AGWA/git-crypt"
            exit 1
        fi
    else
        echo -e "${RED}❌ 지원하지 않는 OS입니다.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ git-crypt가 이미 설치되어 있습니다.${NC}"
fi

# 3. 공유 키 사용 여부 확인
SHARED_KEY_PATH="$HOME/.git-crypt-shared-key"
USE_SHARED_KEY=false

if [ -f "$SHARED_KEY_PATH" ]; then
    echo ""
    read -p "공유 키를 사용하시겠습니까? ($SHARED_KEY_PATH) (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        USE_SHARED_KEY=true
    fi
fi

# 4. git-crypt 초기화
echo ""
echo -e "${BLUE}🔑 git-crypt 초기화 중...${NC}"

if [ "$USE_SHARED_KEY" = true ]; then
    # 공유 키 사용
    echo -e "${YELLOW}공유 키를 사용하여 초기화합니다...${NC}"
    git-crypt unlock "$SHARED_KEY_PATH"
    echo -e "${GREEN}✅ 공유 키로 초기화 완료${NC}"
else
    # 새 키 생성
    git-crypt init
    
    # 키 백업
    BACKUP_DIR="$HOME/git-crypt-backups"
    mkdir -p "$BACKUP_DIR"
    BACKUP_FILE="$BACKUP_DIR/${PROJECT_NAME}-$(date +%Y%m%d-%H%M%S).key"
    git-crypt export-key "$BACKUP_FILE"
    
    echo -e "${GREEN}✅ git-crypt 초기화 완료${NC}"
    echo -e "${YELLOW}💾 백업 키 위치: $BACKUP_FILE${NC}"
    
    # 공유 키로 저장할지 물어보기
    echo ""
    read -p "이 키를 공유 키로 저장하시겠습니까? (다른 프로젝트에서도 사용 가능) (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp "$BACKUP_FILE" "$SHARED_KEY_PATH"
        echo -e "${GREEN}✅ 공유 키로 저장 완료: $SHARED_KEY_PATH${NC}"
    fi
fi

# 5. .gitattributes 생성
echo ""
echo -e "${BLUE}📝 .gitattributes 생성 중...${NC}"

if [ ! -f ".gitattributes" ]; then
    cat > .gitattributes << 'EOF'
# git-crypt 설정
# .env 파일을 git-crypt로 암호화
.env filter=git-crypt diff=git-crypt
.env.local filter=git-crypt diff=git-crypt
*.env filter=git-crypt diff=git-crypt
EOF
    echo -e "${GREEN}✅ .gitattributes 생성 완료${NC}"
else
    echo -e "${YELLOW}⚠️  .gitattributes 파일이 이미 존재합니다.${NC}"
    if ! grep -q "git-crypt" .gitattributes; then
        echo "" >> .gitattributes
        echo "# git-crypt 설정" >> .gitattributes
        echo ".env filter=git-crypt diff=git-crypt" >> .gitattributes
        echo ".env.local filter=git-crypt diff=git-crypt" >> .gitattributes
        echo "*.env filter=git-crypt diff=git-crypt" >> .gitattributes
        echo -e "${GREEN}✅ .gitattributes에 git-crypt 설정 추가 완료${NC}"
    fi
fi

# 6. .gitignore 확인
echo ""
echo -e "${BLUE}📝 .gitignore 확인 중...${NC}"

if [ ! -f ".gitignore" ]; then
    cat > .gitignore << 'EOF'
# Environment variables
.env
.env.local
*.env
!.env.example
EOF
    echo -e "${GREEN}✅ .gitignore 생성 완료${NC}"
else
    if ! grep -q "^\.env" .gitignore; then
        echo "" >> .gitignore
        echo "# Environment variables" >> .gitignore
        echo ".env" >> .gitignore
        echo ".env.local" >> .gitignore
        echo "*.env" >> .gitignore
        echo "!.env.example" >> .gitignore
        echo -e "${GREEN}✅ .gitignore에 .env 설정 추가 완료${NC}"
    else
        echo -e "${YELLOW}⚠️  .gitignore에 이미 .env 설정이 있습니다.${NC}"
    fi
fi

# 7. Git pre-commit hook 설정 (자동 암호화 확인)
echo ""
echo -e "${BLUE}🔒 Git pre-commit hook 설정 중...${NC}"

HOOKS_DIR=".git/hooks"
PRE_COMMIT_HOOK="$HOOKS_DIR/pre-commit"

if [ ! -f "$PRE_COMMIT_HOOK" ]; then
    cat > "$PRE_COMMIT_HOOK" << 'EOF'
#!/bin/bash
# git-crypt 자동 암호화 확인

# .env 파일이 staged 되어 있는지 확인
if git diff --cached --name-only | grep -q "\.env$"; then
    # git-crypt 상태 확인
    if ! git-crypt status -e | grep -q "encrypted: .env"; then
        echo "⚠️  경고: .env 파일이 암호화되지 않았습니다."
        echo "git-crypt가 제대로 설정되었는지 확인하세요."
        echo ""
        echo "해결 방법:"
        echo "  1. git-crypt status 로 상태 확인"
        echo "  2. .gitattributes 파일 확인"
        echo "  3. git-crypt unlock <키파일> 실행"
        exit 1
    fi
fi
EOF
    chmod +x "$PRE_COMMIT_HOOK"
    echo -e "${GREEN}✅ Pre-commit hook 설정 완료${NC}"
else
    echo -e "${YELLOW}⚠️  Pre-commit hook이 이미 존재합니다.${NC}"
fi

# 8. 맥도날드 워크플로우 디렉토리 생성
echo ""
echo -e "${BLUE}📁 맥도날드 워크플로우 디렉토리 생성 중...${NC}"

if [ ! -d ".workflow" ]; then
    mkdir -p .workflow
    echo -e "${GREEN}✅ .workflow 디렉토리 생성 완료${NC}"
else
    echo -e "${YELLOW}⚠️  .workflow 디렉토리가 이미 존재합니다.${NC}"
fi

# 9. 완료 메시지
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ 초기화 완료!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}다음 단계:${NC}"
echo ""
echo "1. .env 파일 생성:"
echo "   cp env.example .env"
echo ""
echo "2. .env 파일 편집하여 실제 값 입력"
echo ""
echo "3. Git에 추가 및 커밋:"
echo "   git add -f .env .gitattributes .gitignore"
echo "   git commit -m 'Initial commit with encrypted .env'"
echo ""
if [ "$USE_SHARED_KEY" = false ]; then
    echo -e "${YELLOW}4. 백업 키를 안전한 곳에 보관하세요:${NC}"
    if [ -f "$BACKUP_FILE" ]; then
        echo "   $BACKUP_FILE"
    fi
    echo ""
fi
echo -e "${BLUE}📚 참고:${NC}"
echo "   - 맥도날드 워크플로우 가이드: .workflow/START_HERE.md"
echo "   - git-crypt 사용법: .git-crypt-setup.md"
echo ""

