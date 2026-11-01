# 동료 전용 ATS 창 — DLL·서버 계약 (2026-10-30)

방식 B: 원본 ATS 레이아웃(CSB)만 불러온 동료 전용 창 `SLCompATS`(DLL `companion5_ats_window.hpp`, 스위치 `COMPANION_ATS_WINDOW=1`). 원본 ATS 전역 모델(644B0)·4ED6/4ED7·원본 Save(8F6450/104EA0)는 이 창에서 절대 쓰지 않는다. 과거 1단계(열기·닫기·ESC·기사 창과 동시 표시·기사 설정 불변)는 runs/glfw28-ats_window_open-claude-20261030에서 통과했다. 현재 정책은 두 ATS 창의 상호 배타 표시다. 동료 창 열기는 보이는 기사 창을 원본 Close로 닫고, 기사 창 열기는 동료 창을 닫으며 미저장 draft를 버린다. 동료 창은 원본 ATS 기본 위치를 우선하고 동료 가방·펫과 겹칠 때만 옮긴다. 공간 부족으로 열기를 거절하지 않는다.

## 원칙

- 원본 ATS 설정 blob(`companion_ats`, ats_config_codec 형식)은 **서버만** 해석·작성한다. DLL은 protobuf를 다루지 않는다.
- 서버 → DLL: 풀어 놓은 **보기용 JSON**. DLL → 서버: **고친 값만** 담은 JSON. 서버는 저장된 blob에 고친 값만 덮어쓰고 나머지 필드(모르는 필드·순서 포함)는 보존한다(`ats_config_codec`에 apply 함수 추가, 기존 `build_ats`는 시험용이라 제품 저장에 쓰지 않는다).
- 기사 `self_config`/`self_ats`와 계정 sidecar는 이 경로에서 읽기만 한다.

## 흐름

1. 펫 창 4행 클릭 → DLL이 창을 띄우고 기존 companion 신호로 `ats-window-open {actor_uid, member_id}`를 보낸다.
2. 서버가 소유·현재 동료를 확인하고 보기용 JSON을 DLL에 공급한다(기존 companion 요청 파일 공개 방식에 필드를 추가하거나, 같은 폴더의 별도 JSON 파일 경로를 요청에 담는다. 512바이트 신호 버퍼에 blob을 넣지 않는다).
   확정 공급 방식: `companion_bridge_publish`의 `ats-window-view {member_id, ats_epoch: edit_epoch, view_file}` / `ats-window-result {member_id, ats_epoch: edit_epoch, result_file}` 요청이 기존 bridge 폴더 basename `companion-ats-view-<epoch>-<time_ns>.json` / `companion-ats-result-<epoch>-<time_ns>.json`을 가리킨다. 결과 JSON은 `schema: companion-ats-result-v1`, `member_id`, `edit_epoch`, `status`, `reason`과 성공 시 저장 후 `view`를 담는다. DLL 신호 args는 open `(member_id)`, save `(member_id, edit_epoch, companion-ats-delta-<양의 seq>.json)`, actor는 현재 동료 low32 UID이며 delta는 같은 폴더 내부에서 `member_id`·`edit_epoch`와 변경 키만 읽는다. host 요청 직렬화가 위 command/field를 공급한다.
   host 요청 JSON 실제 키: 공통 `schema,pid,birth,candidate_sha256,seq,command,actor_uid,actor_generation,owner_uid,member_id,hold,lawful_known,lawful,event_seq,ats_epoch` 뒤에 `command="ats-window-view"`는 `view_file`, `command="ats-window-result"`는 `result_file` basename 한 개를 붙인다.
3. DLL이 보기용 JSON으로 칸·숫자를 채운다. 아이템 칸은 **동료 가방** 아이템 metadata(기존 동료 가방 모델, `B03780`/`B042D0` 경로)로 그린다. 해당 템플릿이 동료 가방에 없으면 빈 칸이 아니라 "없음" 표시(아이콘은 템플릿 아이콘, 흐리게) — 1차는 아이콘만 그려도 된다.
4. 사용자가 동료 가방에서 칸으로 끌어 놓기·수치 입력·칸 비우기(우클릭 또는 원본과 같은 동작)를 하면 DLL 안의 draft만 바뀐다.
5. Save 클릭 → `ats-window-save {member_id, edit_epoch}` + 고친 값 JSON 파일. 서버가 저장하고 결과(`OK`/거절 사유)를 돌려주면 DLL이 "저장되었습니다" 안내(기존 4EEA 알림 방식은 서버가 보냄). 닫기 전에 저장 안 하면 draft는 버린다.
6. Reset = 마지막으로 서버가 준 보기용 JSON으로 되돌림. Play·변신 버튼은 동료 창에서 숨기거나 no-op.

## 보기용 JSON (서버 → DLL)

```json
{
  "schema": "companion-ats-view-v1",
  "member_id": 2, "edit_epoch": 7, "name": "SoloMage",
  "hp_slots":  [{"template": 14, "name": "빨간 물약"}, null],
  "mp_slots":  [null, null],
  "hp_percent": 50, "mp_percent": 80,
  "function_slots": [{"template": 17, "name": "초록 물약"}, null, null, null, null, null],
  "buff_slots": [],
  "options": {"scan_tiles": 4, "hunt_steps": 0, "idle_seconds": 0}
}
```

- 칸 개수는 원본과 같다(HP 2, MP 2, 기능 6). `null` = 빈 칸.
- `buff_slots`·전투(순차·조건) 탭의 마법 칸은 3단계(동료 마법 끌어올 곳 결정) 전까지 보기만(서버가 주는 값 표시), 편집 불가.
- 옵션 키는 `ats_config_codec.decode_options` 결과의 의미 있는 것만. 모르는 키는 보내지 않는다.

## 저장 JSON (DLL → 서버)

보기용 JSON과 같은 키 중 **바뀐 키만** (`hp_slots` 등 배열은 통째로). `member_id`, `edit_epoch` 필수. 서버는 `edit_epoch`가 현재 창 것이 아니면 거절(오래된 저장).

## 시험

- 서버: 보기 JSON 생성, 고친 값 적용 후 다른 필드 보존(실제 저장 blob으로), 기사 설정 불변, 오래된 epoch 거절, 동료 AI 정책이 저장값을 따름.
- DLL/시나리오: `ats_window_open` — 동료 창 열기 → 기사 창 열기(동료 닫힘) → 동료 창 열기(기사 닫힘) → 각 창 Close·ESC → 기사 `self_config/self_ats` 불변. `ats_window_edit` — 창 열기 → 칸·숫자 표시 캡처 → 동료 가방 물약을 HP 2번 칸으로 끌기 → HP% 입력 → Save → 서버 `companion_ats` 변경·기사 설정 불변 → 닫고 다시 열어 표시 유지.

## 3단계 — 동료 마법 끌어오기 (사용자 결정 2026-10-30: 선택지 a)

동료 전용 마법창을 띄운다: 원본 `Spell/SpellLayout.csb`·`Slot/SpellSlot.csb`를 동료 가방·동료 ATS 창과 같은 방식(별도 이름 등록, 원본 factory·SELF 모델 구독 없이)으로 띄우고, **동료가 실제로 배운 마법**만 보여 준다. 사용자는 이 창에서 동료 ATS 창의 버프 칸·전투(순차/조건) 칸으로 끌어 놓는다. 원본 마법창 시전 callback은 연결하지 않는다(동료 마법창에서 클릭으로 시전하지 않음).
- 마법 아이콘 metadata는 동료 학습목록으로 만든다. 기사 SpellSubsystem(AE360, `B079B0`, `42C934→5B48A0`)을 거치지 않는다(근거·주의: scratchpad w76 조사 결과, UI_FINDINGS.md:111).
- 서버 보기 JSON에 `learned_spells: [{"spell_row": <클라 내부 spell row ID>, "name": ..., "icon": ...}]`를 추가하고, `buff_slots`·전투 칸 저장은 kind1(`SlotShortcut f1=1, f4=spell row`) 형식으로 서버가 blob에 적용한다. 클라 spell row ID와 서버 learned/cast ID의 대응은 서버가 근거로 확정해 변환한다(UNKNOWN이면 보고).
- 공유 창 시절 4E60 마법 목록 바꿔치기는 이 창 경로에서 쓰지 않는다.
- 서버 매핑 근거: `world_magic.PlayerMagic`의 learned/cast key(`data/m3/player_spells.json`의 `classic_key.value`) 80개는 고정 클라 `work/all_table_semantics/spell_token/spell-ui-joins.json`의 `spell_id`·`named_UI_configuration.id`, `work/source_game_data/native-dump-v1.jsonl`의 `spell.id`와 각각 일치하며 이름·정수 `icon` 누락이 없다. `icon`은 클라 UI 설정값이며 `row+48`에서 실제 renderer까지의 소비는 UNKNOWN이다.
- `learned_spells`는 `character_learned_spells` 훅의 현재 동료 학습 집합으로만 만들고, 매핑되지 않은 키는 `learned_spells_unknown`에 따로 남긴다. 저장 직전에 같은 훅을 다시 읽어 미학습 `spell_row`를 거절한다. 동료 AI의 실제 시전 지원은 현재 힐·실드·에너지 볼트 3종이다.
- 저장 JSON의 `buff_slots`는 기존 칸 개수의 전체 배열(`null` 또는 `{spell_row,name?,icon?}`), `battle_slots`는 기존 순서의 전체 `{kind,index,slot,condition?,value?}` 배열이다. 기존 아이템·미해석 칸은 보기값 그대로 읽기 전용이다. 서버는 kind1 `f1/f4`만 바꾸고 표시용 `name/icon`, 원문의 다른 필드·순서·조건식은 보존한다. 기존 저장에 없는 마법 칸의 생성은 UNKNOWN이며 조건값 0은 현재 AI 실행 조건이 아니다.
