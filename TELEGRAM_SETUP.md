# Telegram report setup

매일 생성되는 신고가 리포트를 텔레그램으로 보내려면 GitHub Secrets에 아래 값을 넣습니다.

## 1. 봇 만들기

1. 텔레그램에서 `@BotFather`를 엽니다.
2. `/newbot`을 입력합니다.
3. 봇 이름과 username을 정합니다.
4. 발급된 token을 `TELEGRAM_BOT_TOKEN`으로 사용합니다.

## 2. 보낼 방 준비

개인 채팅, 그룹, 채널 모두 가능합니다.

- 개인 채팅: 만든 봇에게 아무 메시지나 먼저 보냅니다.
- 그룹: 봇을 그룹에 초대합니다.
- 채널: 봇을 채널 관리자로 추가합니다.

## 3. chat_id 확인

브라우저에서 아래 주소를 엽니다. token 부분은 실제 봇 토큰으로 바꿉니다.

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates
```

응답 JSON에서 `chat` 안의 `id` 값을 찾습니다.

그룹 chat_id는 보통 `-100...`처럼 음수입니다.
공개 채널은 `@channelusername` 형태를 `TELEGRAM_CHAT_ID`로 쓸 수도 있습니다.

## 4. GitHub Secrets 등록

GitHub 저장소에서 아래로 이동합니다.

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

아래 3개를 추가합니다.

```text
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=발급받은_봇_토큰
TELEGRAM_CHAT_ID=보낼_채팅방_ID
```

## 5. 실행 시점

- 매일 06:00 KST 자동 실행에서는 텔레그램을 보냅니다.
- `Actions`에서 수동 실행해도 텔레그램을 보냅니다.
- 코드 `push`로 자동 실행될 때는 텔레그램을 보내지 않습니다.

