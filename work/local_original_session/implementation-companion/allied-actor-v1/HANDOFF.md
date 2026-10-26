# Allied playable mage actor v1 — LOCAL appearance producer implemented; actor authority unavailable

## 追加 source 적용 후 최종 상태

`local_mage_dto.py`를 새 제품 후손으로 구현했다. 원 `list.spr` SHA a3e184ed의 실제 #734 wizard pc male / #1186 sorceress 자원을 명시 LOCAL class3 gender0/1 정책으로 고른다. #4804/4805는 같은 이름의 대안 자원이며 이 정책은734/1186으로 고정한다. 이는 원 서버 class/gender mapping을 복원했다는 주장이 아니다.

`LocalMageDtoProducer(sprite_source=absolute_path, world_codec=existing_model, policy=POLICY).prepare(character=record, actor_uid=issued_live_uid, self_info=complete_current_fields, actor=complete_player_fields)`는 **모든 required field가 이미 있는 입력**을 먼저 기존 스키마로 검사한다. 정본 character UID와 SelfInfo1, 별도 외부 live actor UID와 Actor2, 캐릭터 이름과 Actor9, Player dispatch Actor16=True를 확인한다. appearance f3와 기존 presence인 f69만 정책값으로 바꾸고 다른 필드·optional presence·SelfInfo는 보존한다. 입력 사전은 변경하지 않으며 결과는 immutable mapping이다. UID·RESOURCE·등록·current/generation 권위를 발급하지 않는다. `direct_world_for`/`actor_factory`에 아직 설치하지 않았다.

pure fixture 최소검사9 PASS: 두 gender×f69 presence 유무4종 실제 기존 codec roundtrip, required 누락·Monster·다른 live UID·다른 class 거부4종, 입력 불변1종. `verification.json` 참조. 테스트의 UID/scalar는 명시 fixture이며 실제 세션/actor 발급·렌더 성공이 아니다. 초기 SPR header 검사에서 sorceress 행의 실제 탭 때문에 실패한 것은 whitespace token 정규화로 수정 후 재확인했다.

**정정된 첫 미공급 접점:** 숫자 appearance는 이제 명시 LOCAL 정책으로 생산 가능하다. 다음 미공급은 동료의 **현재 canonical RESOURCE를 반영한 full SelfInfo/Player 필드 source + 실제 live actor 등록 결과(UID/generation/character lease/direct owner/world lifetime alias)**다. 이번 producer가 요구하는 구체 필드는 SelfInfo의 required 전 필드, Actor의 required 전 필드(특히 live UID2·실 character name9·Player16), 그리고 caller current의 출처이다. 기존 class0 self DTO를 동료의 현 RESOURCE로 복사하지 않는다. 단일 다음 source는 `CompanionActorPort.spawn`에 정당 등록된 allied Player instance/UID/generation과 같은 full DTO를 발급하는 실제 registration producer다. source locator는 supplied evidence에서 아직 미확인이다.

WRITER_RELEASED. 공용main/타기능/포트/저장/게임/큐 수정0. 아래는 추가 자원 단서를 받기 전 첫 대조 결과이며, appearance 미공급 표현은 위 최종 상태로 대체한다.

## 최초 source 대조 기록

2026-10-23. WRITER_RELEASED. 사용자 재개와 실제 법사 동료 소환 요구를 적용했다. 이 단위는 생산·등록·current·소멸만 소유하며 클릭/UI는 별도 담당이다. 새 REA, 공용 소스, 큐, 저장, 포트, 게임 실행 변경은 없다. 원 브랜치는 main이며 기존 다수 dirty/untracked 파일은 이 작업에 포함하지 않았다.

## 실제 결론

현재 supplied source에는 구체적인 `CompanionActorPort` 구현이 없다. v5 `companion_host.UnavailableActorPort.spawn`는 송신 전 `COMPANION_ALLIED_PLAYER_SPAWN_CONTRACT_UNAVAILABLE`로 거부한다. 이를 완성한 것처럼 보이게 만드는 새 adapter/stub/registry는 추가하지 않았다.

첫 불가능 접점은 `CompanionBootstrap.direct_world_for(record)` → `CompanionHost.prepare_direct_world`와 `CompanionActorPort.spawn(character, lease, owner)`의 입력 생산이다. 원 character class3/gender에 대한 출처 있는 숫자 appearance(f3, presence 있는 f69)와 full SelfInfo/Player Actor DTO를 발급할 producer가 없다. OWN224는 preview 이름이고 OWN226은 f3/f69 소비 경로이며 두 근거 모두 숫자 producer가 아니다.

**다음 필요한 단일 source:** 실제 class3/gender별 숫자 appearance와 full Player Actor DTO를 만드는 producer/catalog의 원문 또는 출처 있는 발급 출력 한 건. producer 파일/주소 locator는 현재 supplied evidence에 미확인이다. 이름을 추측하지 않는다. 이는 다음 최초 입력 요청이며 나머지 모든 계약을 묶어 한꺼번에 공급하라는 요구가 아니다.

## 최신 source 대조

- 현재 수용된 scoped-product-router-integration-v1 공용 Broker(05b93b8e)는 기존 self world codec과 `_send`/drain 경로를 유지한다. `LocalRealm._frames_for`는 선택된 profile UID/name/map0와 `validate_self_spawn(..., this_is_self=True)`를 요구한다. 두 번째 살아 있는 allied player 등록 결과나 UID/generation/lease alias를 발급하지 않는다.
- Book15 cohort의 실제 `selected_actor`는 spellbook/character-starter-inventory-v1/actor/selected_actor.py(a0ca1019). `fixed` INFO3=0/INFO5=0과 Actor f3=0의 명시 LOCAL class0/gender0만 받는다. 새 정상 CREATE/WORLD PASS가 class3 appearance 공급을 의미하지 않는다.
- character-growth-create-integration-v1/selected_actor.py 후손도 `InitialCharacterValues.character_class == 'royal'`와 같은 INFO3=0/5=0·appearance0를 유지한다. HPMP 초기값 확장은 법사 appearance source가 아니다.
- 최신 NPC UID issuer는 root cold Setup에서 NPC 범위 0x20000000..0x2000ffff를 실제 영속 발급하고 정확한 SourceRoster/NpcSpawn object의 bind/current를 확인한다. `issue_roster_cold`는 npc_client_recipe와 source_roster_combat에 명목 고정되어 있다. 이 경로를 Player로 재명명하거나 NPC UID를 동료 UID로 넘길 근거는 없다.
- v5 `CompanionActorPort.server_snapshot`은 saved character UID/live actor UID의 alias, actor generation, companion lease, direct owner/world lifetime와 실제 shared resource current를 요구한다. 원 self RESOURCE snapshot이나 controller의 이전 ActorSnapshot은 현재 actor 권위가 아니다.
- Remove drain만으로 `RemovalResult.absent=True`를 반환할 수 없다. 기존 계약상 동일 generation의 원 lookup 부재 또는 positive never-emitted와 이전 spawn/move 완료가 필요하다. 현재 해당 allied 등록 producer가 없으므로 독립 remove/current 구현을 만들 수 없다.

## 이어갈 지점

출처 있는 class3 입력이 공급되면 위 input boundary에서 이어간다. 실제 allied AddPlayer 등록의 UID·current generation과 owner/resource alias, 기존 decoder/router/send-drain의 송신과 원 lookup 제거·부재가 함께 확보되어야 정상 actor port를 완성할 수 있다. character UID를 live actor UID로 치환하거나 self Actor UID를 복사하거나 UID3을 예약하지 않는다. Move·Remove를 전송했다는 사실만으로 native lookup/pose 성공을 만들지 않는다.

원 companion v5 입력은 integration-1/companion-webpro-review-v5/extracted이며 모든 정확 부모 파일/해시와 source 접점은 evidence.json에 기록했다. 제품 변경 0, packet/native/game 시험 UNRUN. 필요한 source를 받은 뒤 해당 경로의 최소 확인만 진행하며 기존 NPC/CREATE 성공 검사는 재실행 gate로 만들지 않는다.
