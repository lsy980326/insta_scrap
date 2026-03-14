@echo off
REM 신규 프로젝트 초기화 스크립트 (Windows)
REM 맥도날드식 워크플로우 + git-crypt 환경 변수 암호화 자동 설정

setlocal enabledelayedexpansion

echo 🚀 신규 프로젝트 초기화 스크립트
echo ==================================
echo.

REM 프로젝트 이름 확인
if "%~1"=="" (
    echo 사용법: %~nx0 ^<프로젝트-이름^>
    echo.
    echo 예시:
    echo   %~nx0 my-new-project
    exit /b 1
)

set PROJECT_NAME=%~1
set PROJECT_DIR=%CD%

echo 프로젝트 이름: %PROJECT_NAME%
echo 프로젝트 디렉토리: %PROJECT_DIR%
echo.

REM 1. Git 저장소 확인
if not exist ".git" (
    echo ⚠️  Git 저장소가 초기화되지 않았습니다.
    set /p INIT_GIT="Git 저장소를 초기화하시겠습니까? (y/n) "
    if /i "!INIT_GIT!"=="y" (
        git init
        echo ✅ Git 저장소 초기화 완료
    ) else (
        echo ❌ Git 저장소가 필요합니다.
        exit /b 1
    )
)

REM 2. git-crypt 설치 확인
where git-crypt >nul 2>&1
if errorlevel 1 (
    echo 📦 git-crypt가 설치되어 있지 않습니다.
    echo.
    echo Windows에서 git-crypt 설치 방법:
    echo 1. Git for Windows 설치 (권장): https://git-scm.com/download/win
    echo    - Git for Windows에 git-crypt가 포함되어 있습니다.
    echo.
    echo 2. 또는 수동 설치:
    echo    - https://github.com/AGWA/git-crypt/releases 에서 다운로드
    echo    - PATH에 추가
    echo.
    set /p CONTINUE="계속하시겠습니까? (y/n) "
    if /i not "!CONTINUE!"=="y" (
        exit /b 1
    )
) else (
    echo ✅ git-crypt가 이미 설치되어 있습니다.
)

REM 3. 공유 키 사용 여부 확인
set SHARED_KEY_PATH=%USERPROFILE%\.git-crypt-shared-key
set USE_SHARED_KEY=false

if exist "%SHARED_KEY_PATH%" (
    echo.
    set /p USE_SHARED="공유 키를 사용하시겠습니까? (%SHARED_KEY_PATH%) (y/n) "
    if /i "!USE_SHARED!"=="y" (
        set USE_SHARED_KEY=true
    )
)

REM 4. git-crypt 초기화
echo.
echo 🔑 git-crypt 초기화 중...

if "!USE_SHARED_KEY!"=="true" (
    REM 공유 키 사용
    echo 공유 키를 사용하여 초기화합니다...
    git-crypt unlock "%SHARED_KEY_PATH%"
    echo ✅ 공유 키로 초기화 완료
) else (
    REM 새 키 생성
    git-crypt init
    
    REM 키 백업
    set BACKUP_DIR=%USERPROFILE%\git-crypt-backups
    if not exist "!BACKUP_DIR!" mkdir "!BACKUP_DIR!"
    
    for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
    set BACKUP_FILE=!BACKUP_DIR!\%PROJECT_NAME%-!datetime:~0,8!-!datetime:~8,6!.key
    git-crypt export-key "!BACKUP_FILE!"
    
    echo ✅ git-crypt 초기화 완료
    echo 💾 백업 키 위치: !BACKUP_FILE!
    
    REM 공유 키로 저장할지 물어보기
    echo.
    set /p SAVE_SHARED="이 키를 공유 키로 저장하시겠습니까? (다른 프로젝트에서도 사용 가능) (y/n) "
    if /i "!SAVE_SHARED!"=="y" (
        copy "!BACKUP_FILE!" "%SHARED_KEY_PATH%" >nul
        echo ✅ 공유 키로 저장 완료: %SHARED_KEY_PATH%
    )
)

REM 5. .gitattributes 생성
echo.
echo 📝 .gitattributes 생성 중...

if not exist ".gitattributes" (
    (
        echo # git-crypt 설정
        echo # .env 파일을 git-crypt로 암호화
        echo .env filter=git-crypt diff=git-crypt
        echo .env.local filter=git-crypt diff=git-crypt
        echo *.env filter=git-crypt diff=git-crypt
    ) > .gitattributes
    echo ✅ .gitattributes 생성 완료
) else (
    echo ⚠️  .gitattributes 파일이 이미 존재합니다.
    findstr /C:"git-crypt" .gitattributes >nul 2>&1
    if errorlevel 1 (
        (
            echo.
            echo # git-crypt 설정
            echo .env filter=git-crypt diff=git-crypt
            echo .env.local filter=git-crypt diff=git-crypt
            echo *.env filter=git-crypt diff=git-crypt
        ) >> .gitattributes
        echo ✅ .gitattributes에 git-crypt 설정 추가 완료
    )
)

REM 6. .gitignore 확인
echo.
echo 📝 .gitignore 확인 중...

if not exist ".gitignore" (
    (
        echo # Environment variables
        echo .env
        echo .env.local
        echo *.env
        echo !.env.example
    ) > .gitignore
    echo ✅ .gitignore 생성 완료
) else (
    findstr /C:".env" .gitignore >nul 2>&1
    if errorlevel 1 (
        (
            echo.
            echo # Environment variables
            echo .env
            echo .env.local
            echo *.env
            echo !.env.example
        ) >> .gitignore
        echo ✅ .gitignore에 .env 설정 추가 완료
    ) else (
        echo ⚠️  .gitignore에 이미 .env 설정이 있습니다.
    )
)

REM 7. Git pre-commit hook 설정
echo.
echo 🔒 Git pre-commit hook 설정 중...

set HOOKS_DIR=.git\hooks
set PRE_COMMIT_HOOK=%HOOKS_DIR%\pre-commit

if not exist "%PRE_COMMIT_HOOK%" (
    (
        echo @echo off
        echo REM git-crypt 자동 암호화 확인
        echo.
        echo git diff --cached --name-only ^| findstr /C:".env$" ^>nul 2^>^&1
        echo if not errorlevel 1 (
        echo     git-crypt status -e ^| findstr /C:"encrypted: .env" ^>nul 2^>^&1
        echo     if errorlevel 1 (
        echo         echo ⚠️  경고: .env 파일이 암호화되지 않았습니다.
        echo         echo git-crypt가 제대로 설정되었는지 확인하세요.
        echo         exit /b 1
        echo     )
        echo )
    ) > "%PRE_COMMIT_HOOK%"
    echo ✅ Pre-commit hook 설정 완료
) else (
    echo ⚠️  Pre-commit hook이 이미 존재합니다.
)

REM 8. 맥도날드 워크플로우 디렉토리 생성
echo.
echo 📁 맥도날드 워크플로우 디렉토리 생성 중...

if not exist ".workflow" (
    mkdir .workflow
    echo ✅ .workflow 디렉토리 생성 완료
) else (
    echo ⚠️  .workflow 디렉토리가 이미 존재합니다.
)

REM 9. 완료 메시지
echo.
echo ========================================
echo ✅ 초기화 완료!
echo ========================================
echo.
echo 다음 단계:
echo.
echo 1. .env 파일 생성:
echo    copy env.example .env
echo.
echo 2. .env 파일 편집하여 실제 값 입력
echo.
echo 3. Git에 추가 및 커밋:
echo    git add -f .env .gitattributes .gitignore
echo    git commit -m "Initial commit with encrypted .env"
echo.
if "!USE_SHARED_KEY!"=="false" (
    echo 4. 백업 키를 안전한 곳에 보관하세요:
    if defined BACKUP_FILE (
        echo    !BACKUP_FILE!
    )
    echo.
)
echo 📚 참고:
echo    - 맥도날드 워크플로우 가이드: .workflow\START_HERE.md
echo    - git-crypt 사용법: .git-crypt-setup.md
echo.

endlocal

