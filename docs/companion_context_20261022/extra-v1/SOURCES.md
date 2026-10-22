# 동료 구현 추가 원문 인덱스

공개 부모 a2959fb928ef88bfc4e5a0b1a17edf7905c61d14, docs/companion_context_20261022 원문36에 대한 최소 추가문맥이다. 현재390/393 선정 근거를 읽었으며 동료 구현/수정은 웹 Pro 소유다. 이 자료는 읽기용 사본이며 runtime cohort/빌드/실행/다중caster 완료를 뜻하지 않는다. 원문Python14개와 기존짧은core후손diff1개 외에 이 인덱스와 README만 작성했다.

원경로는 프로젝트 루트 기준이다. 아래 SHA는 선택한 원파일을 복사할 때 읽은 원바이트 SHA이며 사본 bytes는 편집/줄바꿈 정규화하지 않았다. 전체 closure/해시감사나 새검사체계가 아니다.

## 새 원문

| 사본 | 원경로 | SHA-256 / bytes | 선택 근거·부모차이 |
| --- | --- | --- | --- |
| [core/canonical_batch.py](core/canonical_batch.py) | work/local_original_session/implementation-3/skill-buff/buff-effective-stats-v2/canonical_batch.py | 2fd02106d855745248e31e6b2d1a63d1903754286b37056b41ae6147250db4c0 / 128269 | 390/393 issuer의 CORE_SHA exact2fd02106 및 core_path. 공개36에 누락. Binding/BrokerProvider/character RESOURCE key/단1 BatchStore CAS. |
| [core/hp_resource_document.py](core/hp_resource_document.py) | work/local_original_session/integration-1/buff-factory-join-v1/cohort/hp_resource_document.py | 4b691ab2a57ee6a3897ab738031cfa7f86b3994f0b4690755e948533a637c594 / 6885 | 390/393 동일4b691ab2. 공개36 누락. live Stage/raw Snapshot/current authority와 RESOURCE seed/change/phase. |
| [selected/broker.py](selected/broker.py) | work/local_original_session/integration-1/spell-light-catalog-serial379-v1/broker.py | 36a340950db7890f60e1603060e8dfb05043c6c88739e7b2ec65265e0a0a2090 / 346070 | 390/393 동일36a34095. 공개36 NPC387의6f4 broker와 다른 graph. 실제 LocalRealm/selected generation/RESOURCE·SKILL attach/send. |
| [selected/inventory.py](selected/inventory.py) | work/local_original_session/validation-minimal-refactor/source-init-v1/inventory.py | d7d62c069d7e0c6f2c5c1fd241f2209758c41b8ae8aae355d5ce00ec12c5d5ca / 60323 | 390/393 refactor source-init d7d6 실제 nominal inventory. 공개36에 이 파일 없음. core inventory row/service class-space. |
| [selected/inventory_store.py](selected/inventory_store.py) | work/local_original_session/validation-minimal-refactor/source-init-v1/inventory_store.py | 7dbf9725b9147031393c578342dcea3bfaee9a1f8bf0b1029af697f458e5f1e1 / 30525 | 390/393 실제7dbf9725. 공개36 NPC7557과 다름. 다중 CharacterStore rows/restore/rawCAS의 실제 Store. |
| [selected/hp_status.py](selected/hp_status.py) | work/local_original_session/implementation-3/skill-buff/buff-effective-stats-v2/hp_status.py | 8388776e5282d131dce820f60cd4f2d7be375781ca57fc759dcaeae7bb4f8f9d / 33697 | 390/393 실제8388776e. 공개36 NPC5a2/Combat e5c와 다름. RESOURCE raw-current Snapshot/world/update 수명. |
| [selected393/hp_resource_owner.py](selected393/hp_resource_owner.py) | work/local_original_session/implementation-3/skill-buff/spell-normal-learning-v1/buff-reference-exclusive-v1/hp_resource_owner.py | 756260f8aeb8e0963b7ee28a4c0e328b024cbbe3f22da563b77b143bbbe85225 / 67706 | 393756260f8는390 Light4440의 C 직접후손. 공개36 Combat46b/NPC256과 다름. require_exclusive/world_fields/plan_cast_locked만 추가; 타caster admission 완성 아님. |
| [selected393/skill_cost_delivery.py](selected393/skill_cost_delivery.py) | work/local_original_session/implementation-3/skill-buff/spell-normal-learning-v1/buff-reference-exclusive-v1/skill_cost_delivery.py | d8d320fdcf5a105b1a658ec240bc83f80dd739a76d38e70c300ea15cd169b32d / 19173 | 393d8d320fd는390 Light1395의 C 직접후손. 공개36 Combat9b48과 다름. typed remove/add view preflight/단1cost delivery/원퇴역. |
| [selected393/canonical_feature_bootstrap.py](selected393/canonical_feature_bootstrap.py) | work/local_original_session/integration-1/spell-reference-exclusive-serial393-v1/canonical_feature_bootstrap.py | 1ceeef0b629f4a32d3c69ffe8fbbdb454c8fefe7b6233d6a293f2e6dcc624b82 / 66255 | 3931ceeef0b. 공개36c06a→390bfd5 same-paused-owner cold 연결→393 literal12 guard. 실제 SourceModule/core/attach/cold 경계. |
| [selected393/runtime_input.py](selected393/runtime_input.py) | work/local_original_session/integration-1/spell-reference-exclusive-serial393-v1/runtime_input.py | 79b8278292e009ee0521c0260ce803f6cc32b455df1980530e40dc2484fd47f2 / 36228 | 39379b82782는390fccf 기반 실제 JOIN/core2fd/PausedRun issuer. 공개36 author135b 운영본과 다름. ELF witness/reference opt-in. |
| [wire/character_wire.py](wire/character_wire.py) | tools/local_character_wire_v2/wire.py | 466d3db45f1765f2cb3ce3e5a25917615ebd07326c428f29b66b80512d372cfc / 7096 | Realm/game session의 exact466d WIRE_SHA. 공개 parent와36에 없음. NUM/INFO/roster/ACK encoder. |
| [wire/self_info_model.py](wire/self_info_model.py) | tools/local_self_info_profile/model.py | aeccbd4d3f0384b173c51c8e8f0bc8dfe33a3823761359a8ef3ad6dd5b2d580f / 8472 | actor_hook.profiles SELF_SOURCE. 공개 parent와36에 없음. 명시4E38 DTO; 별도 동료HP writer를 제공하지 않음. |
| [wire/self_actor_profile.py](wire/self_actor_profile.py) | tools/local_self_actor_profile/profile.py | 57480631983cfe6884367a49e1c349a351c4a518e52eb47b1374b26f878246a9 / 7139 | 같은 ACTOR_SOURCE. 공개 parent와36에 없음. 명시 self/actor4E96 DTO 관계; 동료 official Playerable 필드 근거 아님. |
| [wire/world_model.py](wire/world_model.py) | tools/local_world_protocol/model.py | 2d1ebdec0c3fc7830702691d045d89c6dacfdbf706cbf5eb9670be20e3cd5f07 / 8014 | game session exact world2d1e 및 Actor DTO pure encoder. 공개 parent와36에 없음. scalar/schema/provenance 경계; contract/ledger 원문은 미포함. |

## 기존 공개36 참조 — 중복 사본 없음

| parent 문맥 | 원바이트 SHA-256 | 선정 근거 |
| --- | --- | --- |
| [npc387/inventory_aggregate.py](https://github.com/climsnkks-collab/singlelineage/blob/a2959fb928ef88bfc4e5a0b1a17edf7905c61d14/docs/companion_context_20261022/npc387/inventory_aggregate.py) | dc21e6a1c79210c1a5ecc6d848cfa84d9f3a9fc569cff3230db673f9af4ecff4 | 390/393 origin은 buff-factory-join-v1/cohort/inventory_aggregate.py지만 bytes동일. AggregateReadCapability.load/core class-space. |
| [npc387/equipment_store.py](https://github.com/climsnkks-collab/singlelineage/blob/a2959fb928ef88bfc4e5a0b1a17edf7905c61d14/docs/companion_context_20261022/npc387/equipment_store.py) | cce184e828da856f289bcdde91ceed5aef4cd8c01a891c8b513370b3935f5b06 | 390/393 같은equipment_store. |
| [npc387/skill_buff.py](https://github.com/climsnkks-collab/singlelineage/blob/a2959fb928ef88bfc4e5a0b1a17edf7905c61d14/docs/companion_context_20261022/npc387/skill_buff.py) | d18a2356f1c0663c72ae4290aaf43fed94c17994e8551412318bb78251d6dfde | 390/393 core.Rule/SKILL source동일. |
| [npc387/canonical_skill.py](https://github.com/climsnkks-collab/singlelineage/blob/a2959fb928ef88bfc4e5a0b1a17edf7905c61d14/docs/companion_context_20261022/npc387/canonical_skill.py) | c1ef77e41fba8cec73b81941cd8e03b7d42b7f601f7e149999ff932f2ef332ed | 390/393 동일. |
| [shared/npc.py](https://github.com/climsnkks-collab/singlelineage/blob/a2959fb928ef88bfc4e5a0b1a17edf7905c61d14/docs/companion_context_20261022/shared/npc.py) | eb893fbceb7854db27089eb8c36cfad2d6c6720b6ef18877c4aa4d14d68c853b | 기존4E96 NpcSpawn fields/준비/프레임; 적NPC를 법사로 이름만 바꾸는 근거 아님. |

## 공개 parent 일반 제품 source — 새 사본 없음

아래 필요한 지정 source만 exact parent blob과 현재 원바이트가 같음을 읽기 전용으로 확인했다. 공개 checkout의 줄바꿈 변환값을 source hash로 사용하지 않았다.

| parent 경로 | SHA-256 | 직접 역할 |
| --- | --- | --- |
| [tools/local_character_creation/realm.py](https://github.com/climsnkks-collab/singlelineage/blob/a2959fb928ef88bfc4e5a0b1a17edf7905c61d14/tools/local_character_creation/realm.py) | b594d067f844a5140fd8cab77e4a53f6eb2056fd4abdcd85ea3d421fdf14a80e | CharacterStore roster/create/select/snapshot、Creation/create_ack. |
| [tools/local_game_session/session.py](https://github.com/climsnkks-collab/singlelineage/blob/a2959fb928ef88bfc4e5a0b1a17edf7905c61d14/tools/local_game_session/session.py) | 81da91b9577e6033cb53738367605c56c1828efe7e3bc3e91c8aa6b15fbeff1e | Selection/Roster/Registry/select dispatch와 admitted writer. |
| [tools/local_native_login_self_actor_hook/hook.py](https://github.com/climsnkks-collab/singlelineage/blob/a2959fb928ef88bfc4e5a0b1a17edf7905c61d14/tools/local_native_login_self_actor_hook/hook.py) | be99acbe65266e28b19bbd8044f2e13c9e50c93b88ce7455ca6c9ccbca762266 | profiles/frames/frame/validate_selected의 SelfInfo/Actor 원준비. |
| [tools/local_original_session/movement.py](https://github.com/climsnkks-collab/singlelineage/blob/a2959fb928ef88bfc4e5a0b1a17edf7905c61d14/tools/local_original_session/movement.py) | 3c0332a71609e31f26fc0a7f1fbc9dfc9ef42363a5d215b9f01a3a08a66d6d61 | PositionStore/MovementService/4E2B/4EE0. 성공 selfMove는 echo 없음. |
| [tools/local_movement_session_route/route.py](https://github.com/climsnkks-collab/singlelineage/blob/a2959fb928ef88bfc4e5a0b1a17edf7905c61d14/tools/local_movement_session_route/route.py) | 8420ac30fcbb840585e1a99dd199d8729f2776f2fcdef8cc1a82182383deac2e | parse_payload/authority와 World/DirectionalEvidence; DTO생성은 live발급 아님. |
| [tools/local_original_session/npc_motion.py](https://github.com/climsnkks-collab/singlelineage/blob/a2959fb928ef88bfc4e5a0b1a17edf7905c61d14/tools/local_original_session/npc_motion.py) | 58ed66d9de5feba20a56bc631f404819eb4fb7ed644d884f6320effd045d5e4b | 4E2C NPC normal motion. 동료 player 포트 적용은 UNKNOWN. |
| [tools/local_original_session/npc_death.py](https://github.com/climsnkks-collab/singlelineage/blob/a2959fb928ef88bfc4e5a0b1a17edf7905c61d14/tools/local_original_session/npc_death.py) | 9175976a0e1371c48ff48f773c6493ae9202a37ffd59f46ce284a6e3aad571a9 | 4E39/4E40 frame/prepare_remove/attempt/drained. ordinary Monster 정책; generic companion release 미완성. |
| [tools/local_original_session/item_custody.py](https://github.com/climsnkks-collab/singlelineage/blob/a2959fb928ef88bfc4e5a0b1a17edf7905c61d14/tools/local_original_session/item_custody.py) | 83555ca0c927a0bd57f38cce9b759b1e1a94643d3a3f46e5d4fc695bf20f322d | 공용 inventory custody DTO/owner. |
| [tools/local_original_session/inventory_update.py](https://github.com/climsnkks-collab/singlelineage/blob/a2959fb928ef88bfc4e5a0b1a17edf7905c61d14/tools/local_original_session/inventory_update.py) | e86a7a280de663403f6b125bce93a73593678c1382664e1515315eb76f9120d1 | 390/393 선정 원 row update/prepare/commit. |

## source pin과 실제 caster 포트의 한계

canonical_batch.Binding은 UID만이 아니라 실제 writer/generation/operation_lock/generation_key/owned_scope다. BrokerProvider._selected_current/current는 원broker generation/현재선택/registry/task·thread/실획득scope/store·reader/transport 상태를 확인한다. 다른UID/new dataclass/가짜 currentTrue는 이 권한을 제공하지 않는다.

DocumentCapability.key(uid)는 RESOURCE를 character scope RESOURCE:<uid>, SKILL을 account characters-map으로 구분한다. 이것은 각저장캐릭터의 RESOURCE가 이미 발급·seed됐다는 뜻이 아니다. ResourceDocument.seed/staged/validate_change/validate_authority는 같은 live rawSnapshot/target UID/owner승인Stage/scope를 요구한다. 타caster HPMP를 self snapshot 복사나 rawsave변경으로 연결할 수 없다. companion RESOURCE load/update, 타caster current/lock, 원비용·회복 prepare→jointCAS→응답drain 연결은 여전히 OPEN이다.

390/393 issuer는 exact2fd core_path/CORE_SHA를 사용한다. AggregateReadCapability.load가 그 bytes에서 유일 core class-space를 만들고 bootstrap은 같은api를 broker/provider/batch/문서capability에 전달한다. SourceModule.check는 moduleobject/원경로/bytes SHA를 함께 검사하며 class/method/global/alias도 실제 소비와 맞아야 한다. 새hash만 대입하거나 이 사본을 import하는 것은 source 선정/현재 소유 권한 연결을 대신하지 않는다.

393 owner/cost는390 Light4440/1395의 후손이다. 공개36 Combat46b/9b48 및 NPC256과 역할이 달라 전면덮기하지 않는다. 구현자는 정확 target source/부모/diff와 caller/callee·정리 연결을 반환한다. 실제393 새ELF 입력도 미공급이며390 Light1 성공은 동료나 타인 시전 성공이 아니다.

## 일반 player DTO/emitter와 UNKNOWN

CharacterStore는 생성/선택 정본이고 실제 LocalRealm은 broker36a 안에 있다. LocalRealm._frames_for는 position.uid==profile_uid/name==profile_name/map0 및 validate_self_spawn(this_is_self=True)를 요구하고 MAP/SELF4E38/ACTOR4E96를 만든다. UID만 바꾼 원격 일반player emitter가 이미 있다는 근거가 아니다.

기존 shared/npc의4E96, npc_motion의4E2C, npc_death의4E40는 원 자체 source지만 명시NPC/ordinaryMonster 정책/owner/send/drain 수명이다. knownheader/opcode만으로 playable법사의 actorclass/공식 전체필드/동행·해제/아군시전 소비를 추정하지 않는다. 새동료 actor producer, casterUID의 실제 소유, 플레이·소환 동시활성 방지, remoteMove/Remove consumer 및 native 계약은 확인된 범위 밖에서 UNKNOWN이다.

DTO Python이 참조하는 private contract/ledger/pins 원문은 미포함이다. source문맥만으로 모든 dependency를 충족하거나 Factory/Native/UI를 실행할 수 있다고 주장하지 않는다. 미확인client/native는 별도 REA216 요약후속으로 받으며 이자료에 임의보충하지 않았다.

## 보존과 마감

원본바이너리/사용자저장/전체로그/REA원문/credentials 복사0. 제품·공용·ACTIVE·390/393·private상태변경0. import/compile/테스트/Factory/프로필/게임0. branch/commit/push/게시0이며 최종같은문맥branch 게시는root 소유다. 발행 시 원바이트보존(-text)은 root가 해당추가폴더에 적용한다.

WRITER_RELEASED

## 386-v4 선정 차이 — 390/393 공용선정으로 확대하지 않음

390/393의 canonical core는 위 원문2fd02106d855745248e31e6b2d1a63d1903754286b37056b41ae6147250db4c0이다. 반면386-v4 runtime_input.py의 CORE_SHA/core_path는 실제 private386-v2 후손을 선택한다.

- 실제386-v4 selected core 원경로: work/local_original_session/integration-1/combat-pve-serial386-v2/cohort/canonical_batch.py
- 실제 원바이트 SHA-256: 8fe77db9fb92cd1073857442b7891f68f1ba3a2449e2547864d171f6eea2f582
- [원2fd→386-v4선정8fe 기존 exact delta](core/canonical_batch.386-v4-vs2fd.diff), 원경로: work/local_original_session/integration-1/combat-pve-serial386-v2/cohort/canonical_batch.py.parent.diff
- delta 원바이트 SHA-256: f25057ebd31be1a1443d67d0b38ccc0058a73f13374562229b91ddc8e7e02135 / 602 bytes. 두 번째 core전체원문 사본은 추가하지 않았다.
- 직접 delta는 ZERO_EQUIPMENT_SOURCE_SHA256의87c93ec3→a520ce31 source pin 한literal이다. 이 작은 차이도 원source/class-space 선택과 실제 후손판정에서 누락하지 않는다.
- 386-v4 hp_resource_owner 실제 selected source: C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\integration-1\combat-pve-serial386-v2\cohort\hp_resource_owner.py, SHA-256 46b3379a1c13af1dab0e34d05967b4d4f9d2404179cbfffb2dcbb0f27dd152f8.
- 393 owner756260f8과386 owner46b3379a는 서로 다른 기능 source다. 이 묶음의 최신393을 전체 canonical/combat의 최종선정으로 오인하거나 그 파일을386 위에 전면덮기하지 않는다. 첫 Pro review a3108f87의 정확 대상 후손을 유지한다.

이 후속은 source 선택표·기존짧은delta만 추가했으며 동료제품수정/30tests재생/Factory/프로필/게임0이다.
